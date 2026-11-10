"""Agente conversacional de NEXO.

El agente combina un motor determinista de intenciones con el catálogo real
de lugares. Puede buscar por cercanía, recordar el último lugar consultado,
sugerir recorridos y devolver acciones que el frontend ejecuta en el mapa.

No inventa distancias ni recorridos: las distancias son geodésicas y los
tiempos de recorrido son estimaciones claramente etiquetadas.
"""

from __future__ import annotations

import math
import re
from datetime import time as datetime_time
from uuid import UUID

from django.db.models import Count

from places.geo import distance_km, valid_coordinates
from places.models import Category, Place
from routes.models import Route

from . import nlp
from .content import LEGENDS, RECOMMENDED_IDS
from .engine import nearby


AGENT_NAME = "NEXO"
AGENT_ROLE = "guía turístico inteligente"
DEFAULT_RADIUS_KM = 5.0
MAX_RADIUS_KM = 100.0
MAX_NEARBY_RESULTS = 10
MAX_ITINERARY_STOPS = 5
VISIT_MINUTES_PER_STOP = 45
AVERAGE_SPEED_KMH = 45.0


class AgentError(Exception):
    """Error de negocio que la vista transforma en una respuesta HTTP."""

    status_code = 400

    def __init__(self, detail):
        self.detail = detail
        super().__init__(str(detail))


class PlaceNotFound(AgentError):
    status_code = 404


def format_duration(duration: datetime_time | None) -> str:
    if not duration:
        return "Duración no registrada"

    minutes = duration.hour * 60 + duration.minute
    if duration.second:
        minutes += duration.second / 60

    if minutes <= 0:
        return "Duración no registrada"

    hours, remaining = divmod(round(minutes), 60)

    if hours and remaining:
        return f"{hours} h {remaining} min"
    if hours:
        return f"{hours} h"
    return f"{remaining} min"


def _clamp_radius(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return DEFAULT_RADIUS_KM

    if not math.isfinite(number):
        return DEFAULT_RADIUS_KM

    return min(MAX_RADIUS_KM, max(0.5, number))


class NexoAgent:
    def __init__(self, session, request, data: dict | None = None):
        self.session = session
        self.request = request
        self.data = data or {}

        self.places = list(
            Place.objects.select_related(
                "category",
                "municipality",
                "route",
            ).order_by("name", "pk")
        )
        self.by_id = {str(place.pk): place for place in self.places}
        self.categories = list(Category.objects.order_by("name"))
        self.category_names = [category.name for category in self.categories]
        self.municipality_names = sorted({
            place.municipality.name
            for place in self.places
            if place.municipality_id
        })

        self.message = str(self.data.get("message") or "").strip()
        self.legacy_intent = str(self.data.get("intent") or "").strip()
        self.is_legacy = bool(self.legacy_intent and self.legacy_intent != "menu")
        self.context = self.data.get("context") or {}

        self.radius = self._resolve_radius()
        self.latitude = self.data.get("latitude")
        self.longitude = self.data.get("longitude")
        self.last_place = self._resolve_initial_place()

    # ------------------------------------------------------------------
    # Entrada principal
    # ------------------------------------------------------------------

    def respond(self) -> dict:
        if not self.is_legacy and not self.message:
            return self._greeting()

        if self.is_legacy:
            return self._legacy_response()

        return self._conversation_response()

    def _legacy_response(self) -> dict:
        intent = self.legacy_intent

        if intent == "nearby":
            return self._nearby_response(legacy=True)
        if intent == "popular":
            return self._popular_response()
        if intent == "itinerary":
            return self._itinerary_response(legacy=True)
        if intent == "filter":
            return self._filter_response(legacy=True)
        if intent == "favorites":
            return self._favorites_response()
        if intent in {"history", "legends", "logistics", "directions"}:
            return self._place_response(intent, legacy=True)

        raise AgentError({"intent": "Selecciona una consulta válida."})

    def _conversation_response(self) -> dict:
        text = self.message
        normalized = nlp.normalize(text)
        intent = nlp.detect_intent(text)
        radius = nlp.extract_radius(text)
        category = nlp.extract_category(text, self.category_names)
        municipality = nlp.extract_municipality(text, self.municipality_names)
        place = self._find_place(text)

        if radius is not None:
            self.radius = radius

        if place is not None:
            self._remember_place(place)

        if intent == "nearby":
            return self._nearby_response(
                category=category,
                municipality=municipality,
            )

        if intent == "itinerary":
            return self._itinerary_response(
                category=category,
                municipality=municipality,
            )

        if intent in {"history", "legends", "logistics", "directions", "place_info"}:
            return self._place_response(intent, place=place)

        if intent == "popular":
            return self._popular_response()

        if intent == "filter":
            return self._filter_response(
                category=category,
                municipality=municipality,
            )

        if intent == "favorites":
            return self._favorites_response()

        if intent == "help":
            return self._help_response()

        if intent == "thanks":
            return self._thanks_response()

        if intent == "goodbye":
            return self._goodbye_response()

        if intent == "greeting":
            return self._greeting()

        if intent == "list":
            return self._list_response()

        # Sin una intención explícita: usar entidades detectadas.
        if place is not None:
            return self._place_response("place_info", place=place)

        if category or municipality:
            return self._filter_response(
                category=category,
                municipality=municipality,
            )

        if radius is not None:
            return self._radius_response()

        if re.search(r"\b(mapa|filtrar|recorrido|ruta)\b", normalized):
            return self._help_response()

        return self._fallback_response()

    # ------------------------------------------------------------------
    # Respuestas de exploración
    # ------------------------------------------------------------------

    def _nearby_response(
        self,
        legacy: bool = False,
        category: str | None = None,
        municipality: str | None = None,
        radius: float | None = None,
        note: str | None = None,
    ) -> dict:
        radius = _clamp_radius(radius if radius is not None else self.radius)

        if not self._has_location():
            if legacy:
                raise AgentError({
                    "location": "Comparte tu ubicación para buscar lugares cercanos."
                })

            if category or municipality:
                return self._filter_response(
                    category=category,
                    municipality=municipality,
                    note=(
                        "No tengo tu ubicación, así que te muestro los lugares "
                        "registrados para esa selección."
                    ),
                )

            return self._location_request("nearby", radius)

        candidates = self._filter_candidates(category, municipality)
        distance_sources = [
            self._distance_source(place)
            for place in candidates
        ]
        close_items = nearby(
            distance_sources,
            self.latitude,
            self.longitude,
            radius,
            limit=MAX_NEARBY_RESULTS,
        )

        if not close_items:
            nearest = self._nearest_place(candidates)
            next_radius = min(
                MAX_RADIUS_KM,
                max(radius * 2, radius + 5),
            )

            if nearest is not None:
                place, distance = nearest
                reply = (
                    f"No encontré lugares dentro de {radius:g} km. "
                    f"El más cercano es {place.name}, a "
                    f"{distance:.1f} km en línea recta. "
                    f"¿Quieres que amplíe el radio?"
                )
            else:
                reply = (
                    f"No encontré lugares registrados dentro de {radius:g} km. "
                    "Prueba con un radio mayor o cambia la categoría."
                )

            return self._finalize({
                "reply": reply,
                "kind": "places",
                "places": [],
                "actions": [],
                "suggestions": self._suggestions(
                    (f"Buscar en {next_radius:g} km", f"Busca lugares en un radio de {next_radius:g} km"),
                    ("Ver todos los lugares", "Muéstrame todos los lugares"),
                    ("Cambiar categoría", "¿Qué categorías hay?"),
                ),
                "meta": {
                    "intent": "nearby",
                    "radius_km": radius,
                    "count": 0,
                    "requires_location": False,
                },
            })

        close_places = [
            self.by_id[item["id"]]
            for item in close_items
            if item.get("id") in self.by_id
        ]
        payloads = [
            self._place_payload(
                place,
                distance=item.get("distance_km"),
            )
            for place, item in zip(close_places, close_items)
        ]

        scope = ""
        if category:
            scope = f" de {category}"
        elif municipality:
            scope = f" en {municipality}"

        lines = [
            f"Revisé un radio de {radius:g} km desde tu ubicación.",
            f"Encontré {len(payloads)} lugar{'es' if len(payloads) != 1 else ''}{scope}:",
            "",
        ]

        for payload in payloads:
            distance_text = (
                f" · a {payload['distance_km']:g} km"
                if payload.get("distance_km") is not None
                else ""
            )
            lines.append(
                f"• {payload['name']} · {payload.get('category', 'Turismo')}"
                f"{distance_text}"
            )

        lines.extend([
            "",
            "Las distancias son en línea recta, no por carretera. "
            "Puedo abrir el mapa o armar un recorrido con estos lugares.",
        ])

        if note:
            lines.insert(0, note)

        place_ids = [payload["id"] for payload in payloads]

        return self._finalize({
            "reply": "\n".join(lines),
            "kind": "places",
            "places": payloads,
            "actions": [
                {
                    "type": "places",
                    "label": "Ver estos lugares en el mapa",
                    "place_ids": place_ids,
                },
                {
                    "type": "itinerary",
                    "label": "Armar un recorrido",
                    "place_ids": place_ids,
                },
            ],
            "suggestions": self._suggestions(
                (f"Ampliar a {min(MAX_RADIUS_KM, max(radius * 2, radius + 5)):g} km",
                 f"Busca lugares en un radio de {min(MAX_RADIUS_KM, max(radius * 2, radius + 5)):g} km"),
                ("Solo naturaleza", "Muéstrame solo lugares de naturaleza"),
                ("Recomiéndame imperdibles", "¿Cuáles son los lugares más destacados?"),
                ("Armar recorrido", "Arma un recorrido con los lugares cercanos"),
            ),
            "meta": {
                "intent": "nearby",
                "radius_km": radius,
                "count": len(payloads),
                "requires_location": False,
            },
        })

    def _itinerary_response(
        self,
        legacy: bool = False,
        category: str | None = None,
        municipality: str | None = None,
    ) -> dict:
        minutes = self.data.get("minutes")
        if minutes is None:
            minutes = nlp.extract_minutes(self.message)

        if not self._has_location():
            if legacy or category or municipality:
                return self._itinerary_without_location(
                    category=category,
                    municipality=municipality,
                    minutes=minutes,
                    legacy=legacy,
                )

            return self._location_request("itinerary", self.radius)

        candidates = self._filter_candidates(category, municipality)
        distance_sources = [
            self._distance_source(place)
            for place in candidates
        ]
        close_items = nearby(
            distance_sources,
            self.latitude,
            self.longitude,
            self.radius,
            limit=MAX_ITINERARY_STOPS,
        )

        if not close_items:
            nearest = self._nearest_place(candidates)
            next_radius = min(MAX_RADIUS_KM, max(self.radius * 2, self.radius + 5))

            if nearest is not None:
                place, distance = nearest
                reply = (
                    f"No hay lugares dentro de {self.radius:g} km para armar un recorrido. "
                    f"El más cercano es {place.name}, a {distance:.1f} km. "
                    f"Prueba con un radio de {next_radius:g} km."
                )
            else:
                reply = (
                    f"No encontré lugares dentro de {self.radius:g} km "
                    "para proponerte un recorrido."
                )

            return self._finalize({
                "reply": reply,
                "kind": "itinerary",
                "places": [],
                "actions": [],
                "suggestions": self._suggestions(
                    (f"Buscar en {next_radius:g} km", f"Busca lugares en un radio de {next_radius:g} km"),
                    ("Ver todos los lugares", "Muéstrame todos los lugares"),
                ),
                "meta": {
                    "intent": "itinerary",
                    "radius_km": self.radius,
                    "count": 0,
                    "requires_location": False,
                },
            })

        origin = (float(self.latitude), float(self.longitude))
        ordered = self._nearest_neighbor_route(origin, [
            self.by_id[item["id"]]
            for item in close_items
            if item.get("id") in self.by_id
        ])
        payloads = [
            self._place_payload(
                place,
                distance=self._distance_to(place),
            )
            for place in ordered
        ]

        total_distance = self._route_distance(origin, ordered)
        travel_minutes = (total_distance / AVERAGE_SPEED_KMH) * 60
        visit_minutes = VISIT_MINUTES_PER_STOP * len(ordered)
        total_minutes = round(travel_minutes + visit_minutes)

        lines = [
            f"Te propongo un recorrido de {len(payloads)} paradas "
            f"dentro de {self.radius:g} km:",
            "",
        ]

        for index, payload in enumerate(payloads, start=1):
            distance_text = (
                f" · a {payload['distance_km']:g} km"
                if payload.get("distance_km") is not None
                else ""
            )
            route_text = (
                f" · {payload['route_name']} ({payload['route_duration']})"
                if payload.get("route_name")
                else ""
            )
            lines.append(
                f"{index}. {payload['name']}{distance_text}{route_text}"
            )

        lines.extend([
            "",
            f"Distancia aproximada en línea recta: {total_distance:.1f} km.",
            (
                f"Tiempo estimado: {total_minutes // 60} h "
                f"{total_minutes % 60} min, incluyendo "
                f"{VISIT_MINUTES_PER_STOP} min por parada y un promedio de "
                f"{AVERAGE_SPEED_KMH:g} km/h. Ajusta el orden y el ritmo según tu visita."
            ),
            "El trazado real por carretera se calcula al abrirlo en el mapa.",
        ])

        if minutes:
            lines.append(
                f"Tu límite indicado era de {minutes} min; "
                "revisa si este plan se ajusta a tu tiempo."
            )

        return self._finalize({
            "reply": "\n".join(lines),
            "kind": "itinerary",
            "places": payloads,
            "actions": [{
                "type": "itinerary",
                "label": "Ver recorrido en el mapa",
                "place_ids": [payload["id"] for payload in payloads],
            }],
            "suggestions": self._suggestions(
                ("Cambiar a 10 km", "Busca lugares en un radio de 10 km"),
                ("Solo naturaleza", "Arma un recorrido solo con lugares de naturaleza"),
                ("Ver imperdibles", "¿Cuáles son los lugares más destacados?"),
                ("Ajustar paradas", "Muéstrame los lugares cercanos"),
            ),
            "meta": {
                "intent": "itinerary",
                "radius_km": self.radius,
                "count": len(payloads),
                "estimated_minutes": total_minutes,
                "estimated_distance_km": round(total_distance, 2),
                "requires_location": False,
            },
        })

    def _itinerary_without_location(
        self,
        category: str | None,
        municipality: str | None,
        minutes: int | None,
        legacy: bool,
    ) -> dict:
        candidates = self._filter_candidates(category, municipality)
        groups: dict[str, dict] = {}

        for place in candidates:
            route = place.route
            route_id = str(route.pk)

            if minutes:
                route_minutes = self._route_duration_minutes(route)
                if route_minutes and route_minutes > minutes:
                    continue

            groups.setdefault(route_id, {
                "route": route,
                "places": [],
            })
            groups[route_id]["places"].append(place)

        if not groups:
            reply = (
                "No hay recorridos registrados que cumplan ese límite de tiempo. "
                "Prueba con más minutos o consulta los lugares disponibles."
            )
            return self._finalize({
                "reply": reply,
                "kind": "itinerary",
                "places": [],
                "actions": [],
                "suggestions": self._suggestions(
                    ("Ver todos los lugares", "Muéstrame todos los lugares"),
                    ("Buscar cerca de mí", "¿Qué hay cerca de mí?"),
                ),
                "meta": {
                    "intent": "itinerary",
                    "count": 0,
                    "requires_location": False,
                },
            })

        lines = [
            "Estos son los recorridos registrados en NEXO"
            + (f" para {municipality}" if municipality else "")
            + (f" de {category}" if category else "")
            + ":",
            "",
        ]

        all_places: list[Place] = []

        for group in groups.values():
            route = group["route"]
            lines.append(
                f"{route.name} · duración registrada: "
                f"{format_duration(route.duration)}"
            )
            for place in group["places"]:
                lines.append(f"• {place.name} · {place.category.name}")
                all_places.append(place)
            lines.append("")

        lines.append(
            "Las duraciones corresponden a las rutas completas registradas "
            "en NEXO. Comparte tu ubicación si quieres ordenar las paradas "
            "por cercanía y estimar el traslado."
        )

        payloads = [
            self._place_payload(place)
            for place in all_places[:MAX_NEARBY_RESULTS]
        ]

        return self._finalize({
            "reply": "\n".join(lines).strip(),
            "kind": "itinerary",
            "places": payloads,
            "actions": [{
                "type": "itinerary",
                "label": "Ver recorrido en el mapa",
                "place_ids": [payload["id"] for payload in payloads],
            }] if payloads else [],
            "suggestions": self._suggestions(
                ("Compartir ubicación", "¿Qué hay cerca de mí?"),
                ("Ver todos los lugares", "Muéstrame todos los lugares"),
                ("Filtrar por categoría", "¿Qué categorías hay?"),
            ),
            "meta": {
                "intent": "itinerary",
                "count": len(payloads),
                "requires_location": False,
            },
        })

    def _popular_response(self) -> dict:
        editorial: dict[str, int] = {}

        for index, place_id in enumerate(RECOMMENDED_IDS):
            try:
                valid_id = str(UUID(str(place_id)))
            except (ValueError, TypeError, AttributeError):
                continue
            editorial[valid_id] = index

        chosen: list[Place] = []

        if editorial:
            chosen = [
                place
                for place in self.places
                if str(place.pk) in editorial
            ]
            chosen.sort(key=lambda place: editorial[str(place.pk)])

        if chosen:
            reply = (
                "Estos son los lugares destacados por la selección editorial "
                "de NEXO. No es una medición de popularidad en tiempo real."
            )
        else:
            chosen = list(
                Place.objects.select_related("category", "municipality", "route")
                .annotate(visit_count=Count("visits", distinct=True))
                .filter(visit_count__gt=0)
                .order_by("-visit_count", "name", "pk")[:5]
            )
            if chosen:
                reply = (
                    "Estos son los lugares con más visitas registradas en NEXO."
                )
            else:
                reply = (
                    "Todavía no hay destacados configurados ni visitas "
                    "registradas para calcular la popularidad. "
                    "Puedo mostrarte el catálogo completo."
                )

        payloads = [self._place_payload(place) for place in chosen[:5]]

        return self._finalize({
            "reply": reply,
            "kind": "places",
            "places": payloads,
            "actions": [{
                "type": "places",
                "label": "Ver destacados en el mapa",
                "place_ids": [payload["id"] for payload in payloads],
            }] if payloads else [],
            "suggestions": self._suggestions(
                ("Ver todos los lugares", "Muéstrame todos los lugares"),
                ("Buscar cerca de mí", "¿Qué hay cerca de mí?"),
                ("Armar un recorrido", "Arma un recorrido con los lugares destacados"),
            ),
            "meta": {
                "intent": "popular",
                "count": len(payloads),
                "requires_location": False,
            },
        })

    def _filter_response(
        self,
        category: str | None = None,
        municipality: str | None = None,
        legacy: bool = False,
        note: str | None = None,
    ) -> dict:
        if not category and not municipality:
            actions = [
                {
                    "type": "filter",
                    "label": category_item.name,
                    "category": category_item.name,
                }
                for category_item in self.categories
            ]

            reply = (
                "Selecciona una categoría para mostrar sus lugares en el mapa. "
                "También puedo buscar por municipio o por cercanía."
            )

            if not actions:
                reply = "Todavía no hay categorías registradas."

            return self._finalize({
                "reply": reply,
                "kind": "filter",
                "places": [],
                "actions": actions,
                "suggestions": self._suggestions(
                    ("Solo naturaleza", "Muéstrame solo lugares de naturaleza"),
                    ("Solo cultura", "Muéstrame solo lugares de cultura"),
                    ("Buscar cerca de mí", "¿Qué hay cerca de mí?"),
                ),
                "meta": {
                    "intent": "filter",
                    "count": 0,
                    "requires_location": False,
                },
            })

        candidates = self._filter_candidates(category, municipality)

        if not candidates:
            return self._finalize({
                "reply": (
                    "No encontré lugares que coincidan con esa selección. "
                    "Prueba con otra categoría o municipio."
                ),
                "kind": "places",
                "places": [],
                "actions": [],
                "suggestions": self._suggestions(
                    ("Ver todos los lugares", "Muéstrame todos los lugares"),
                    ("¿Qué categorías hay?", "¿Qué categorías hay?"),
                ),
                "meta": {
                    "intent": "filter",
                    "count": 0,
                    "requires_location": False,
                },
            })

        if self._has_location():
            candidates.sort(
                key=lambda place: (
                    self._distance_to(place) or math.inf,
                    place.name.casefold(),
                )
            )
        else:
            candidates.sort(key=lambda place: place.name.casefold())

        payloads = [
            self._place_payload(
                place,
                distance=self._distance_to(place) if self._has_location() else None,
            )
            for place in candidates[:12]
        ]

        scope_parts = []
        if category:
            scope_parts.append(category)
        if municipality:
            scope_parts.append(municipality)
        scope = " · ".join(scope_parts)

        lines = [f"Encontré {len(payloads)} lugares para {scope}:", ""]
        for payload in payloads:
            distance_text = (
                f" · a {payload['distance_km']:g} km"
                if payload.get("distance_km") is not None
                else ""
            )
            lines.append(
                f"• {payload['name']} · {payload.get('category', 'Turismo')}"
                f"{distance_text}"
            )

        if note:
            lines.insert(0, note)

        actions = [{
            "type": "places",
            "label": "Ver estos lugares en el mapa",
            "place_ids": [payload["id"] for payload in payloads],
        }]

        if category:
            actions.insert(0, {
                "type": "filter",
                "label": f"Filtrar {category}",
                "category": category,
            })

        return self._finalize({
            "reply": "\n".join(lines),
            "kind": "places",
            "places": payloads,
            "actions": actions,
            "suggestions": self._suggestions(
                ("Buscar cerca de mí", "¿Qué hay cerca de mí?"),
                ("Armar recorrido", f"Arma un recorrido con lugares de {scope}"),
                ("Ver todos", "Muéstrame todos los lugares"),
            ),
            "meta": {
                "intent": "filter",
                "category": category,
                "municipality": municipality,
                "count": len(payloads),
                "requires_location": False,
            },
        })

    def _list_response(self) -> dict:
        payloads = [
            self._place_payload(place)
            for place in self.places[:12]
        ]

        lines = [
            f"El catálogo de NEXO tiene {len(self.places)} lugares registrados. "
            "Estos son algunos:",
            "",
        ]
        for payload in payloads:
            lines.append(
                f"• {payload['name']} · {payload.get('category', 'Turismo')}"
                f" · {payload.get('municipality', 'Tabasco')}"
            )

        return self._finalize({
            "reply": "\n".join(lines),
            "kind": "places",
            "places": payloads,
            "actions": [{
                "type": "places",
                "label": "Ver catálogo en el mapa",
                "place_ids": [payload["id"] for payload in payloads],
            }],
            "suggestions": self._suggestions(
                ("Filtrar por categoría", "¿Qué categorías hay?"),
                ("Buscar cerca de mí", "¿Qué hay cerca de mí?"),
                ("Recomiéndame imperdibles", "¿Cuáles son los lugares más destacados?"),
            ),
            "meta": {
                "intent": "list",
                "count": len(payloads),
                "requires_location": False,
            },
        })

    # ------------------------------------------------------------------
    # Respuestas sobre un lugar
    # ------------------------------------------------------------------

    def _place_response(
        self,
        intent: str,
        place: Place | None = None,
        legacy: bool = False,
    ) -> dict:
        requested_id = self.data.get("place_id")
        if requested_id and str(requested_id) not in self.by_id:
            raise PlaceNotFound({
                "place_id": "Este lugar ya no está disponible."
            })

        place = place or self.last_place

        if place is None:
            if legacy:
                raise AgentError({
                    "place_id": "Selecciona un lugar de interés."
                })
            return self._ask_place(intent)

        self._remember_place(place)
        payload = self._place_payload(
            place,
            distance=self._distance_to(place) if self._has_location() else None,
        )
        location_line = (
            f"{place.name} está a {payload['distance_km']:g} km en línea recta "
            "desde tu ubicación."
            if payload.get("distance_km") is not None
            else None
        )

        if intent == "history":
            body = (
                place.history
                or place.description
                or "Este lugar todavía no tiene historia registrada."
            )
            reply = (
                body
                if legacy
                else (
                    f"{place.name}\n"
                    f"{place.category.name} · {place.municipality.name}\n\n"
                    f"{body}"
                )
            )
            suggestions = self._suggestions(
                ("Datos curiosos", f"¿Qué datos curiosos hay de {place.name}?"),
                ("Horarios y costos", f"¿Cuál es el horario y costo de {place.name}?"),
                ("Cómo llegar", f"¿Cómo llego a {place.name}?"),
                ("Ver en mapa", f"Muéstrame {place.name} en el mapa"),
            )
        elif intent == "legends":
            body = (
                LEGENDS.get(str(place.pk))
                or place.tips
                or place.importance
                or "Todavía no hay datos curiosos o leyendas registrados para este lugar."
            )
            reply = f"Datos curiosos y leyendas de {place.name}:\n\n{body}"
            suggestions = self._suggestions(
                ("Su historia", f"Cuéntame la historia de {place.name}"),
                ("Horarios y costos", f"¿Cuál es el horario y costo de {place.name}?"),
                ("Cómo llegar", f"¿Cómo llego a {place.name}?"),
            )
        elif intent == "logistics":
            lines = [
                f"Información práctica de {place.name}:",
                f"Horario: {place.schedule or 'No registrado'}.",
                f"Entrada: {place.cost or 'No registrada'}.",
            ]
            if place.recommendations:
                lines.append(f"Recomendaciones: {place.recommendations}")
            if place.tips:
                lines.append(f"Consejos: {place.tips}")
            lines.append(
                "Son los datos registrados en NEXO. Confirma su vigencia "
                "con el lugar antes de visitarlo."
            )
            reply = "\n".join(lines)
            suggestions = self._suggestions(
                ("Cómo llegar", f"¿Cómo llego a {place.name}?"),
                ("Su historia", f"Cuéntame la historia de {place.name}"),
                ("Datos curiosos", f"¿Qué datos curiosos hay de {place.name}?"),
            )
        elif intent == "directions":
            lines = []
            if location_line:
                lines.append(location_line)
            lines.extend([
                "Puedo trazar un recorrido por carretera desde tu ubicación. "
                "El mapa solicitará permiso de ubicación y mostrará el trazado "
                "calculado por el proveedor.",
                "No es una ruta peatonal ni garantiza accesibilidad.",
            ])
            reply = "\n".join(lines)
            suggestions = self._suggestions(
                ("Horarios y costos", f"¿Cuál es el horario y costo de {place.name}?"),
                ("Su historia", f"Cuéntame la historia de {place.name}"),
                ("Ver en mapa", f"Muéstrame {place.name} en el mapa"),
            )
        else:  # place_info
            lines = [
                f"{place.name}",
                f"{place.category.name} · {place.municipality.name}",
                "",
                place.description or "Sin descripción registrada.",
            ]
            if place.importance:
                lines.append(f"\nImportancia turística: {place.importance}")
            if place.schedule:
                lines.append(f"Horario: {place.schedule}")
            if place.cost:
                lines.append(f"Entrada: {place.cost}")
            reply = "\n".join(lines)
            suggestions = self._suggestions(
                ("Su historia", f"Cuéntame la historia de {place.name}"),
                ("Datos curiosos", f"¿Qué datos curiosos hay de {place.name}?"),
                ("Horarios y costos", f"¿Cuál es el horario y costo de {place.name}?"),
                ("Cómo llegar", f"¿Cómo llego a {place.name}?"),
            )

        actions: list[dict] = [{
            "type": "place",
            "label": f"Ver {place.name} en el mapa",
            "place_id": str(place.pk),
        }]

        if intent == "directions":
            actions.insert(0, {
                "type": "directions",
                "label": "Trazar desde mi ubicación",
                "place_id": str(place.pk),
            })

        return self._finalize({
            "reply": reply,
            "kind": "places",
            "places": [payload],
            "actions": actions,
            "suggestions": suggestions,
            "meta": {
                "intent": intent,
                "count": 1,
                "requires_location": False,
            },
        })

    def _ask_place(self, intent: str) -> dict:
        suggestions = []

        for place in self.places[:6]:
            if intent == "history":
                message = f"Cuéntame la historia de {place.name}"
            elif intent == "legends":
                message = f"¿Qué datos curiosos hay de {place.name}?"
            elif intent == "logistics":
                message = f"¿Cuál es el horario y costo de {place.name}?"
            elif intent == "directions":
                message = f"¿Cómo llego a {place.name}?"
            else:
                message = f"Háblame de {place.name}"

            suggestions.append({
                "label": place.name,
                "message": message,
            })

        return self._finalize({
            "reply": (
                "Claro. ¿Sobre qué lugar quieres que te hable? "
                "Puedo contarte su historia, sus datos curiosos, "
                "sus horarios o cómo llegar."
            ),
            "kind": "text",
            "places": [],
            "actions": [],
            "suggestions": suggestions,
            "meta": {
                "intent": "ask_place",
                "count": 0,
                "requires_place": True,
                "requires_location": False,
            },
        })

    # ------------------------------------------------------------------
    # Respuestas generales
    # ------------------------------------------------------------------

    def _greeting(self) -> dict:
        name = ""
        if getattr(self.request, "user", None) and self.request.user.is_authenticated:
            first_name = getattr(self.request.user, "first_name", "") or ""
            if first_name:
                name = f", {first_name}"

        return self._finalize({
            "reply": (
                f"¡Hola{name}! Soy NEXO, tu guía turístico inteligente de Tabasco. 🌿\n\n"
                "Puedo buscar lugares cerca de ti, recomendarte imperdibles, "
                "contarte su historia, armar un recorrido y mostrarte todo en el mapa.\n\n"
                "¿Por dónde empezamos?"
            ),
            "kind": "text",
            "places": [],
            "actions": [],
            "suggestions": self._suggestions(
                ("¿Qué hay cerca de mí?", "¿Qué hay cerca de mí?"),
                ("Recomiéndame imperdibles", "¿Cuáles son los lugares más destacados?"),
                ("Plan de un día", "Arma un itinerario de un día"),
                ("¿Qué puedes hacer?", "¿Qué puedes hacer?"),
            ),
            "meta": {
                "intent": "greeting",
                "count": 0,
                "requires_location": False,
            },
        })

    def _help_response(self) -> dict:
        return self._finalize({
            "reply": (
                "Soy NEXO y puedo ayudarte con esto:\n\n"
                "• Buscar lugares cerca de tu ubicación y decirte el radio de detección.\n"
                "• Recomendarte lugares destacados y filtrarlos por categoría o municipio.\n"
                "• Contarte la historia, leyendas, horarios y costos de cada lugar.\n"
                "• Armar un recorrido con paradas ordenadas y una estimación de tiempo.\n"
                "• Abrir el mapa, trazar rutas y guardar tus sitios favoritos.\n\n"
                "Pregúntame con tus propias palabras o usa una de las sugerencias."
            ),
            "kind": "text",
            "places": [],
            "actions": [],
            "suggestions": self._suggestions(
                ("Buscar cerca de mí", "¿Qué hay cerca de mí?"),
                ("Ver categorías", "¿Qué categorías hay?"),
                ("Lugares imperdibles", "¿Cuáles son los lugares más destacados?"),
                ("Armar un recorrido", "Arma un recorrido de un día"),
            ),
            "meta": {
                "intent": "help",
                "count": 0,
                "requires_location": False,
            },
        })

    def _thanks_response(self) -> dict:
        return self._finalize({
            "reply": (
                "¡Con gusto! Si quieres, puedo seguir explorando contigo: "
                "buscar lugares cercanos, revisar horarios o preparar otro recorrido."
            ),
            "kind": "text",
            "places": [],
            "actions": [],
            "suggestions": self._suggestions(
                ("Seguir explorando", "¿Qué hay cerca de mí?"),
                ("Ver imperdibles", "¿Cuáles son los lugares más destacados?"),
                ("Armar otro recorrido", "Arma un recorrido de un día"),
            ),
            "meta": {
                "intent": "thanks",
                "count": 0,
                "requires_location": False,
            },
        })

    def _goodbye_response(self) -> dict:
        return self._finalize({
            "reply": (
                "¡Buen viaje! Aquí estaré cuando quieras descubrir otro rincón "
                "de Tabasco. 🌿"
            ),
            "kind": "text",
            "places": [],
            "actions": [],
            "suggestions": self._suggestions(
                ("Volver a empezar", "Hola"),
                ("Ver lugares", "Muéstrame todos los lugares"),
            ),
            "meta": {
                "intent": "goodbye",
                "count": 0,
                "requires_location": False,
            },
        })

    def _fallback_response(self) -> dict:
        place = self._find_place(self.message)

        if place is not None:
            return self._place_response("place_info", place=place)

        return self._finalize({
            "reply": (
                "No estoy seguro de haber entendido esa consulta. "
                "Puedo buscar lugares cerca de ti, recomendarte imperdibles, "
                "contarte su historia o armar un recorrido. "
                "Prueba con una de estas opciones o dime el nombre de un lugar."
            ),
            "kind": "text",
            "places": [],
            "actions": [],
            "suggestions": self._suggestions(
                ("¿Qué hay cerca de mí?", "¿Qué hay cerca de mí?"),
                ("Lugares imperdibles", "¿Cuáles son los lugares más destacados?"),
                ("Categorías", "¿Qué categorías hay?"),
                ("Ver todos los lugares", "Muéstrame todos los lugares"),
            ),
            "meta": {
                "intent": "fallback",
                "count": 0,
                "requires_location": False,
            },
        })

    def _location_request(self, intent: str, radius: float) -> dict:
        return self._finalize({
            "reply": (
                f"Para medir distancias y buscar dentro de {radius:g} km "
                "necesito tu ubicación. Solo la usaré para esta consulta. "
                "¿Me la compartes?"
            ),
            "kind": "location",
            "places": [],
            "actions": [{
                "type": "location",
                "label": "Compartir mi ubicación",
            }],
            "suggestions": self._suggestions(
                ("Buscar en 10 km", "Busca lugares en un radio de 10 km"),
                ("Buscar en 25 km", "Busca lugares en un radio de 25 km"),
                ("Ver todos los lugares", "Muéstrame todos los lugares"),
            ),
            "meta": {
                "intent": intent,
                "radius_km": radius,
                "count": 0,
                "requires_location": True,
            },
        })

    def _radius_response(self) -> dict:
        if self._has_location():
            return self._nearby_response(radius=self.radius)

        return self._finalize({
            "reply": (
                f"Radio de búsqueda actualizado a {self.radius:g} km. "
                "Comparte tu ubicación y busco los lugares dentro de ese radio."
            ),
            "kind": "location",
            "places": [],
            "actions": [{
                "type": "location",
                "label": "Compartir mi ubicación",
            }],
            "suggestions": self._suggestions(
                ("Buscar cerca de mí", "¿Qué hay cerca de mí?"),
                ("Ver todos los lugares", "Muéstrame todos los lugares"),
            ),
            "meta": {
                "intent": "radius",
                "radius_km": self.radius,
                "count": 0,
                "requires_location": True,
            },
        })

    def _favorites_response(self) -> dict:
        return self._finalize({
            "reply": (
                "Para guardar un lugar, abre su ficha y pulsa el botón de "
                "favoritos. Después puedes consultarlo en la sección Favoritos.\n\n"
                "Para guardar un recorrido, abre el mapa, pulsa Crear ruta, "
                "agrega al menos dos lugares y pulsa Guardar.\n\n"
                "Los recorridos se guardan como rutas personalizadas."
            ),
            "kind": "text",
            "places": [],
            "actions": [
                {
                    "type": "favorites",
                    "label": "Abrir favoritos",
                },
                {
                    "type": "map",
                    "label": "Crear recorrido",
                },
            ],
            "suggestions": self._suggestions(
                ("Ver lugares", "Muéstrame todos los lugares"),
                ("Buscar cerca de mí", "¿Qué hay cerca de mí?"),
            ),
            "meta": {
                "intent": "favorites",
                "count": 0,
                "requires_location": False,
            },
        })

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _finalize(self, result: dict) -> dict:
        result.setdefault("places", [])
        result.setdefault("actions", [])
        result.setdefault("suggestions", [])
        result.setdefault("kind", "text")
        result.setdefault("meta", {})

        meta = result["meta"]
        meta.setdefault("intent", self.legacy_intent or "chat")
        meta.setdefault("count", len(result["places"]))
        meta.setdefault("radius_km", self.radius)
        meta.setdefault("requires_location", False)

        # Si el lugar llegó por la petición (place_id o context), la memoria
        # de la sesión debe reflejarlo aunque no se haya usado _remember_place.
        if self.last_place is not None:
            self.session.last_place = self.last_place

        result["session_id"] = str(self.session.pk)
        result["context"] = {
            "place_id": str(self.session.last_place_id) if self.session.last_place_id else None,
            "place_name": self.session.last_place.name if self.session.last_place_id and self.session.last_place else None,
            "radius_km": self.radius,
            "has_location": self._has_location(),
        }
        result["agent"] = {
            "name": AGENT_NAME,
            "role": AGENT_ROLE,
            "online": True,
        }

        self.session.last_intent = str(meta.get("intent") or "chat")[:40]
        self.session.radius_km = self.radius

        self.session.save(update_fields=[
            "last_place",
            "last_intent",
            "radius_km",
            "updated_at",
        ])

        return result

    def _resolve_radius(self) -> float:
        if self.data.get("radius_km") is not None:
            return _clamp_radius(self.data.get("radius_km"))
        return _clamp_radius(self.session.radius_km or DEFAULT_RADIUS_KM)

    def _resolve_initial_place(self) -> Place | None:
        candidates = [
            self.data.get("place_id"),
            self.context.get("place_id") if isinstance(self.context, dict) else None,
            self.session.last_place_id,
        ]

        for candidate in candidates:
            if not candidate:
                continue
            place = self.by_id.get(str(candidate))
            if place is not None:
                return place

        return None

    def _has_location(self) -> bool:
        return valid_coordinates(self.latitude, self.longitude)

    def _remember_place(self, place: Place) -> None:
        self.last_place = place
        self.session.last_place = place

    def _find_place(self, text: str) -> Place | None:
        if not text:
            return None
        return nlp.find_place(text, self.places)

    def _filter_candidates(
        self,
        category: str | None = None,
        municipality: str | None = None,
    ) -> list[Place]:
        candidates = self.places

        if category:
            normalized = nlp.normalize(category)
            candidates = [
                place
                for place in candidates
                if nlp.normalize(place.category.name) == normalized
            ]

        if municipality:
            normalized = nlp.normalize(municipality)
            candidates = [
                place
                for place in candidates
                if nlp.normalize(place.municipality.name) == normalized
            ]

        return list(candidates)

    def _distance_source(self, place: Place) -> dict:
        return {
            "id": str(place.pk),
            "name": place.name,
            "latitude": str(place.latitude),
            "longitude": str(place.longitude),
        }

    def _coordinates(self, place: Place) -> tuple[float, float] | None:
        if not valid_coordinates(place.latitude, place.longitude):
            return None
        return float(place.latitude), float(place.longitude)

    def _distance_to(self, place: Place) -> float | None:
        if not self._has_location():
            return None

        coordinates = self._coordinates(place)
        if coordinates is None:
            return None

        try:
            return round(
                distance_km(
                    self.latitude,
                    self.longitude,
                    coordinates[0],
                    coordinates[1],
                ),
                2,
            )
        except ValueError:
            return None

    def _nearest_place(
        self,
        places: list[Place],
    ) -> tuple[Place, float] | None:
        if not self._has_location():
            return None

        best: tuple[Place, float] | None = None

        for place in places:
            distance = self._distance_to(place)
            if distance is None:
                continue
            if best is None or distance < best[1]:
                best = (place, distance)

        return best

    def _nearest_neighbor_route(
        self,
        origin: tuple[float, float],
        places: list[Place],
    ) -> list[Place]:
        remaining = list(places)
        ordered: list[Place] = []
        current = origin

        while remaining:
            best_index = 0
            best_distance = math.inf

            for index, place in enumerate(remaining):
                coordinates = self._coordinates(place)
                if coordinates is None:
                    continue
                try:
                    distance = distance_km(
                        current[0],
                        current[1],
                        coordinates[0],
                        coordinates[1],
                    )
                except ValueError:
                    continue
                if distance < best_distance:
                    best_distance = distance
                    best_index = index

            place = remaining.pop(best_index)
            ordered.append(place)
            coordinates = self._coordinates(place)
            if coordinates is not None:
                current = coordinates

        return ordered

    def _route_distance(
        self,
        origin: tuple[float, float],
        places: list[Place],
    ) -> float:
        total = 0.0
        current = origin

        for place in places:
            coordinates = self._coordinates(place)
            if coordinates is None:
                continue
            try:
                total += distance_km(
                    current[0],
                    current[1],
                    coordinates[0],
                    coordinates[1],
                )
            except ValueError:
                continue
            current = coordinates

        return total

    def _route_duration_minutes(self, route: Route | None) -> int | None:
        if not route or not route.duration:
            return None
        return route.duration.hour * 60 + route.duration.minute

    def _place_payload(
        self,
        place: Place,
        distance: float | None = None,
    ) -> dict:
        image = None

        if place.image:
            try:
                image = place.image.url
                if self.request is not None:
                    image = self.request.build_absolute_uri(image)
            except (ValueError, AttributeError):
                image = None

        payload = {
            "id": str(place.pk),
            "name": place.name,
            "category": place.category.name,
            "municipality": place.municipality.name,
            "description": place.description,
            "image": image,
            "latitude": float(place.latitude),
            "longitude": float(place.longitude),
            "schedule": place.schedule or "",
            "cost": place.cost or "",
            "route_name": place.route.name if place.route else "",
            "route_duration": format_duration(place.route.duration) if place.route else "",
        }

        if distance is not None:
            payload["distance_km"] = round(float(distance), 2)

        return payload

    def _suggestions(self, *items: tuple[str, str]) -> list[dict]:
        return [
            {
                "label": label,
                "message": message,
            }
            for label, message in items
            if label and message
        ]
