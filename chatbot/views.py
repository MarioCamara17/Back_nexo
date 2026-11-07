import math
from uuid import UUID

from django.db.models import Count

from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from places.models import Place, Category

from .content import LEGENDS, RECOMMENDED_IDS
from .engine import nearby


MENU = [
    {
        "id": "nearby",
        "label": "¿Qué hay cerca de mi ubicación actual?",
        "group": "Exploración",
    },
    {
        "id": "popular",
        "label": "¿Cuáles son los lugares más destacados o populares?",
        "group": "Exploración",
    },
    {
        "id": "itinerary",
        "label": (
            "¿Qué lugares cercanos puedo visitar "
            "y cuánto duran sus rutas?"
        ),
        "group": "Exploración",
    },
    {
        "id": "history",
        "label": "¿Cuál es la historia de este lugar?",
        "group": "Historia y cultura",
    },
    {
        "id": "legends",
        "label": "¿Existen datos curiosos o leyendas sobre este lugar?",
        "group": "Historia y cultura",
    },
    {
        "id": "directions",
        "label": "¿Cómo llego a este lugar desde donde estoy?",
        "group": "Rutas y logística",
    },
    {
        "id": "logistics",
        "label": "¿Cuáles son los horarios y costos de entrada?",
        "group": "Rutas y logística",
    },
    {
        "id": "filter",
        "label": "¿Cómo puedo filtrar el mapa por categoría?",
        "group": "Ayuda de NEXO",
    },
    {
        "id": "favorites",
        "label": "¿Cómo guardo lugares y recorridos?",
        "group": "Ayuda de NEXO",
    },
]


class ChatRequest(serializers.Serializer):
    intent = serializers.ChoiceField(
        choices=[item["id"] for item in MENU] + ["menu"],
        default="menu",
    )

    place_id = serializers.UUIDField(required=False)

    latitude = serializers.FloatField(
        min_value=-90,
        max_value=90,
        required=False,
    )

    longitude = serializers.FloatField(
        min_value=-180,
        max_value=180,
        required=False,
    )

    radius_km = serializers.FloatField(
        min_value=0.1,
        max_value=100,
        default=5,
    )

    def validate(self, attrs):
        for field in ("latitude", "longitude", "radius_km"):
            if field in attrs and not math.isfinite(attrs[field]):
                raise serializers.ValidationError({
                    field: "Introduce un número finito."
                })

        return attrs


def place_data(place):
    return {
        "id": str(place.pk),
        "name": place.name,
        "latitude": str(place.latitude),
        "longitude": str(place.longitude),
        "category": place.category.name,
    }


def format_duration(duration):
    if not duration:
        return "Duración no registrada"

    if not (duration.hour or duration.minute or duration.second):
        return "Duración no registrada"

    text = f"{duration.hour} h {duration.minute} min"

    if duration.second:
        text += f" {duration.second} s"

    return text


class ChatbotView(APIView):
    # Consultas públicas de información turística.
    # Guardar favoritos y rutas sigue utilizando sus APIs autenticadas.
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "reply": "Selecciona una pregunta para comenzar.",
            "menu": MENU,
        })

    def post(self, request):
        serializer = ChatRequest(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        intent = data["intent"]

        if intent == "menu":
            return self.get(request)

        places = Place.objects.select_related(
            "category",
            "route",
        ).order_by("name", "pk")

        result = {
            "reply": "",
            "places": [],
            "actions": [],
        }

        # 1. Lugares cercanos.
        if intent == "nearby":
            self.require_location(data)

            close_places = nearby(
                [place_data(place) for place in places],
                data["latitude"],
                data["longitude"],
                data["radius_km"],
            )

            result["places"] = close_places

            if close_places:
                result["reply"] = (
                    f"Lugares dentro de {data['radius_km']:g} km "
                    "de tu ubicación, ordenados por cercanía. "
                    "Las distancias se miden en línea recta."
                )

                result["actions"] = [{
                    "type": "places",
                    "label": "Ver lugares cercanos en el mapa",
                    "place_ids": [
                        place["id"] for place in close_places
                    ],
                }]
            else:
                result["reply"] = (
                    "No hay lugares registrados dentro de ese radio. "
                    "Selecciona un radio mayor y vuelve a consultar."
                )

        # 2. Destacados editoriales o popularidad por visitas.
        elif intent == "popular":
            editorial = {}

            for index, place_id in enumerate(RECOMMENDED_IDS):
                try:
                    valid_id = str(UUID(str(place_id)))
                except (ValueError, TypeError, AttributeError):
                    continue

                editorial[valid_id] = index

            chosen = (
                list(places.filter(pk__in=editorial.keys()))
                if editorial
                else []
            )

            if chosen:
                chosen.sort(
                    key=lambda place: editorial[str(place.pk)]
                )

                result["reply"] = (
                    "Estos son los lugares destacados "
                    "por la selección editorial de NEXO."
                )
            else:
                chosen = list(
                    places.annotate(
                        visit_count=Count(
                            "visits",
                            distinct=True,
                        )
                    )
                    .filter(visit_count__gt=0)
                    .order_by("-visit_count", "name", "pk")[:5]
                )

                if chosen:
                    result["reply"] = (
                        "Estos son los lugares con más "
                        "visitas registradas en NEXO."
                    )
                else:
                    result["reply"] = (
                        "Todavía no hay destacados configurados "
                        "ni visitas registradas para calcular "
                        "la popularidad."
                    )

            result["places"] = [
                place_data(place) for place in chosen[:5]
            ]

        # 3. Lugares cercanos y duración de sus rutas completas.
        # No filtra por el tiempo disponible del turista.
        elif intent == "itinerary":
            self.require_location(data)

            catalog = list(places)

            places_by_id = {
                str(place.pk): place
                for place in catalog
            }

            close_places = nearby(
                [place_data(place) for place in catalog],
                data["latitude"],
                data["longitude"],
                data["radius_km"],
            )

            result["places"] = close_places

            if not close_places:
                result["reply"] = (
                    "No hay lugares registrados dentro de ese radio. "
                    "Selecciona un radio mayor y vuelve a consultar."
                )
            else:
                groups = {}

                for item in close_places:
                    route = places_by_id[item["id"]].route
                    route_id = str(route.pk)

                    if route_id not in groups:
                        groups[route_id] = {
                            "route": route,
                            "places": [],
                        }

                    groups[route_id]["places"].append(item)

                lines = [
                    (
                        f"Estos son los lugares cercanos dentro de "
                        f"{data['radius_km']:g} km."
                    ),
                    (
                        "Las distancias se miden en línea recta. "
                        "No se filtran por tu tiempo disponible."
                    ),
                    (
                        "Las duraciones corresponden a las rutas "
                        "completas registradas en NEXO, no al tiempo "
                        "de visita de estos lugares ni al traslado "
                        "desde tu ubicación."
                    ),
                ]

                for group in groups.values():
                    route = group["route"]
                    duration_text = format_duration(route.duration)

                    lines.append(
                        f"\n{route.name} · "
                        f"Ruta completa: {duration_text}"
                    )

                    for item in group["places"]:
                        lines.append(
                            f"• {item['name']} · "
                            f"{item['distance_km']:g} km"
                        )

                    result["actions"].append({
                        "type": "places",
                        "label": (
                            f"Ver lugares cercanos de {route.name}"
                        ),
                        "place_ids": [
                            item["id"]
                            for item in group["places"]
                        ],
                    })

                result["reply"] = "\n".join(lines)

        # 4. Filtros del mapa.
        elif intent == "filter":
            categories = Category.objects.order_by("name")

            result["reply"] = (
                "Selecciona una categoría para mostrar "
                "sus lugares en el mapa."
            )

            result["actions"] = [
                {
                    "type": "filter",
                    "label": category.name,
                    "category": category.name,
                }
                for category in categories
            ]

            if not result["actions"]:
                result["reply"] = (
                    "Todavía no hay categorías registradas."
                )

        # 5. Ayuda para favoritos y recorridos.
        elif intent == "favorites":
            result["reply"] = (
                "Para guardar un lugar, abre su ficha y pulsa "
                "el botón de favoritos. Después puedes consultarlo "
                "en la sección Favoritos.\n\n"
                "Para guardar un recorrido, abre el mapa, pulsa "
                "Crear ruta óptima, agrega al menos dos lugares "
                "y pulsa Guardar.\n\n"
                "Los recorridos se guardan como rutas personalizadas."
            )

            result["actions"] = [
                {
                    "type": "favorites",
                    "label": "Abrir favoritos",
                },
                {
                    "type": "map",
                    "label": "Crear recorrido",
                },
            ]

        # Preguntas sobre un lugar específico.
        else:
            if "place_id" not in data:
                raise serializers.ValidationError({
                    "place_id": "Selecciona un lugar de interés."
                })

            place = places.filter(
                pk=data["place_id"]
            ).first()

            if place is None:
                return Response(
                    {
                        "reply": "Este lugar ya no está disponible.",
                        "places": [],
                        "actions": [],
                    },
                    status=404,
                )

            result["places"] = [place_data(place)]

            # 6. Historia.
            if intent == "history":
                result["reply"] = (
                    place.history
                    or "Este lugar todavía no tiene historia registrada."
                )

            # 7. Datos curiosos o leyendas.
            elif intent == "legends":
                result["reply"] = (
                    LEGENDS.get(str(place.pk))
                    or (
                        "Todavía no hay datos curiosos "
                        "o leyendas registrados para este lugar."
                    )
                )

            # 8. Horarios y costos.
            elif intent == "logistics":
                result["reply"] = (
                    f"Horario: {place.schedule or 'No registrado'}.\n"
                    f"Entrada: {place.cost or 'No registrada'}.\n\n"
                    "Son los datos registrados en NEXO. "
                    "Confirma su vigencia con el lugar "
                    "antes de visitarlo."
                )

            # 9. Cómo llegar.
            elif intent == "directions":
                result["reply"] = (
                    "Pulsa Trazar desde mi ubicación. "
                    "El mapa solicitará permiso de ubicación "
                    "y consultará un recorrido por carretera. "
                    "No es una ruta peatonal ni garantiza accesibilidad."
                )

                result["actions"] = [{
                    "type": "directions",
                    "label": "Trazar desde mi ubicación",
                    "place_id": str(place.pk),
                }]

        return Response(result)

    @staticmethod
    def require_location(data):
        if "latitude" not in data or "longitude" not in data:
            raise serializers.ValidationError({
                "location": (
                    "Comparte tu ubicación para buscar "
                    "lugares cercanos."
                )
            })