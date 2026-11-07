import math


def distance_km(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(
        math.radians,
        (lat1, lng1, lat2, lng2),
    )

    value = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin((lng2 - lng1) / 2) ** 2
    )

    value = min(1, max(0, value))

    return 6371 * 2 * math.asin(math.sqrt(value))


def nearby(places, latitude, longitude, radius):
    results = []

    for place in places:
        try:
            place_lat = float(place["latitude"])
            place_lng = float(place["longitude"])

            if not (
                math.isfinite(place_lat)
                and math.isfinite(place_lng)
                and -90 <= place_lat <= 90
                and -180 <= place_lng <= 180
            ):
                continue

            distance = distance_km(
                latitude,
                longitude,
                place_lat,
                place_lng,
            )

        except (TypeError, ValueError, KeyError):
            continue

        if distance <= radius:
            results.append({
                **place,
                "distance_km": round(distance, 2),
            })

    return sorted(
        results,
        key=lambda place: (
            place["distance_km"],
            place["name"],
        ),
    )