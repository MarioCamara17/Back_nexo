"""Utilidades geográficas compartidas por el mapa y el asistente NEXO.

Las distancias son geodésicas (fórmula de Haversine) y se expresan en
kilómetros. No representan recorridos por carretera ni tiempos reales.
"""

from __future__ import annotations

import math
from typing import Any, Iterable


EARTH_RADIUS_KM = 6371.0088
MAX_RADIUS_KM = 100.0


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def valid_coordinates(latitude: Any, longitude: Any) -> bool:
    """Comprueba que un par de coordenadas sea finito y esté en rango."""

    lat = _as_float(latitude)
    lng = _as_float(longitude)

    if lat is None or lng is None:
        return False

    return -90 <= lat <= 90 and -180 <= lng <= 180


def distance_km(lat1: Any, lng1: Any, lat2: Any, lng2: Any) -> float:
    """Distancia en kilómetros entre dos coordenadas válidas."""

    if not valid_coordinates(lat1, lng1) or not valid_coordinates(lat2, lng2):
        raise ValueError("Coordenadas inválidas.")

    first_lat, first_lng, second_lat, second_lng = map(
        math.radians,
        (
            float(lat1),
            float(lng1),
            float(lat2),
            float(lng2),
        ),
    )

    value = (
        math.sin((second_lat - first_lat) / 2) ** 2
        + math.cos(first_lat)
        * math.cos(second_lat)
        * math.sin((second_lng - first_lng) / 2) ** 2
    )

    value = min(1.0, max(0.0, value))

    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(value))


def bounding_box(
    latitude: Any,
    longitude: Any,
    radius_km: Any,
) -> tuple[float, float, float, float] | None:
    """Caja geográfica que contiene el círculo pedido.

    Sirve para reducir candidatos en la base de datos antes de calcular la
    distancia exacta. Es una aproximación conservadora.
    """

    if not valid_coordinates(latitude, longitude):
        return None

    radius = _as_float(radius_km)
    if radius is None or radius <= 0:
        return None

    radius = min(radius, MAX_RADIUS_KM)
    lat = float(latitude)
    lng = float(longitude)

    latitude_delta = radius / 111.32
    cosine = max(math.cos(math.radians(lat)), 0.01)
    longitude_delta = radius / (111.32 * cosine)

    return (
        max(-90.0, lat - latitude_delta),
        min(90.0, lat + latitude_delta),
        max(-180.0, lng - longitude_delta),
        min(180.0, lng + longitude_delta),
    )


def nearby(
    places: Iterable[dict],
    latitude: Any,
    longitude: Any,
    radius: Any,
    limit: int | None = None,
) -> list[dict]:
    """Filtra y ordena diccionarios de lugares por cercanía.

    Cada elemento debe incluir ``latitude`` y ``longitude``. El resultado es
    una copia de cada diccionario con ``distance_km`` redondeado a dos
    decimales.
    """

    if not valid_coordinates(latitude, longitude):
        return []

    radius_number = _as_float(radius)
    if radius_number is None or radius_number <= 0:
        return []

    results: list[dict] = []

    for place in places:
        if not isinstance(place, dict):
            continue

        place_lat = place.get("latitude")
        place_lng = place.get("longitude")

        if not valid_coordinates(place_lat, place_lng):
            continue

        try:
            distance = distance_km(latitude, longitude, place_lat, place_lng)
        except ValueError:
            continue

        if distance <= radius_number:
            results.append({
                **place,
                "distance_km": round(distance, 2),
            })

    results.sort(
        key=lambda item: (
            item["distance_km"],
            str(item.get("name", "")).casefold(),
        )
    )

    return results[:limit] if limit else results
