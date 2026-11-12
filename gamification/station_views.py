"""Catálogo público y registro autenticado con validación geográfica en servidor."""
import math
import time
from django.db import transaction, OperationalError
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from places.geo import distance_km, valid_coordinates
from places.models import Place
from places.serializers import PlaceSerializer
from .models import TrainStation, StationVisit, PointTransaction

STATION_POINTS = 20
MAX_ACCURACY_M = 100
MAX_AGE_SECONDS = 60


class CheckinSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    accuracy_m = serializers.FloatField(min_value=0, max_value=MAX_ACCURACY_M)
    timestamp_ms = serializers.FloatField(min_value=0)

    def validate(self, attrs):
        if not all(math.isfinite(value) for value in attrs.values()):
            raise serializers.ValidationError('La ubicación debe contener valores finitos.')
        age = time.time() - attrs['timestamp_ms'] / 1000
        if age < -10 or age > MAX_AGE_SECONDS:
            raise serializers.ValidationError('La ubicación caducó o la hora del dispositivo es incorrecta. Vuelve a consultarla.')
        return attrs


def station_data(station, visited_at=None):
    return {
        'slug': station.slug, 'name': station.name, 'municipality': station.municipality,
        'order': station.order, 'latitude': float(station.latitude), 'longitude': float(station.longitude),
        'summary': station.summary, 'history': station.history, 'opening_hours': station.opening_hours,
        'timetable_url': station.timetable_url, 'booking_url': station.booking_url,
        'coordinates_source': station.coordinates_source, 'sources': station.sources,
        'checked_on': station.checked_on.isoformat(), 'checkin_radius_m': station.checkin_radius_m,
        'max_accuracy_m': MAX_ACCURACY_M, 'checkin_enabled': station.checkin_enabled,
        'points': STATION_POINTS, 'visited': bool(visited_at), 'visited_at': visited_at,
    }


class StationListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        visits = dict(StationVisit.objects.filter(user=request.user).values_list('station_id', 'visited_at')) if request.user.is_authenticated else {}
        return Response({'stations': [station_data(s, visits.get(s.pk)) for s in TrainStation.objects.filter(active=True)]})


class StationNearbyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        station = get_object_or_404(TrainStation, pk=slug, active=True)
        try:
            radius = float(request.query_params.get('radius_km', 30))
        except (ValueError, TypeError):
            radius = float('nan')
        if not math.isfinite(radius) or not 1 <= radius <= 100:
            return Response({'message': 'El radio debe estar entre 1 y 100 km.'}, status=400)
        # La sección se enfoca en lugares de la Región Ríos de Tabasco.
        candidates = Place.objects.select_related('category', 'municipality__state', 'route').filter(
            municipality__state__name__iexact='Tabasco',
            municipality__name__in=['Balancán', 'Balancan', 'Tenosique', 'Emiliano Zapata'])
        matches = []
        for place in candidates:
            if not valid_coordinates(place.latitude, place.longitude):
                continue
            distance = distance_km(station.latitude, station.longitude, place.latitude, place.longitude)
            if distance <= radius:
                matches.append((place, distance))
        matches.sort(key=lambda item: (item[1], item[0].name))
        places = []
        for place, distance in matches:
            data = dict(PlaceSerializer(place, context={'request': request}).data)
            data['distance_km'] = round(distance, 2)
            places.append(data)
        return Response({'station': slug, 'radius_km': radius, 'count': len(places), 'results': places})


class StationCheckinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        station = get_object_or_404(TrainStation, pk=slug, active=True)
        # Una repetición es una lectura idempotente: nunca vuelve a dar puntos.
        existing = StationVisit.objects.filter(user=request.user, station=station).first()
        if existing:
            return Response({'created': False, 'points_awarded': 0, 'visited': True,
                             'visited_at': existing.visited_at, 'message': 'Esta estación ya está registrada. No se duplicaron los puntos.'})
        if not station.checkin_enabled:
            return Response({'message': 'El registro de visitas está temporalmente deshabilitado para esta estación.'}, status=409)
        payload = CheckinSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        distance = distance_km(data['latitude'], data['longitude'], station.latitude, station.longitude) * 1000
        # Criterio conservador: el círculo de precisión debe quedar dentro del radio.
        if distance + data['accuracy_m'] > station.checkin_radius_m:
            return Response({'message': f'Acércate a la estación. Distancia estimada: {distance:.0f} m; radio permitido: {station.checkin_radius_m} m. Tu precisión debe ser de 100 m o mejor.',
                             'distance_m': round(distance, 1), 'radius_m': station.checkin_radius_m}, status=400)
        try:
            with transaction.atomic():
                visit, created = StationVisit.objects.get_or_create(user=request.user, station=station,
                    defaults={'accuracy_m': data['accuracy_m'], 'distance_m': distance})
                awarded = False
                if created:
                    _, awarded = PointTransaction.objects.get_or_create(user=request.user, action='visited_station',
                        object_id=station.pk, defaults={'points': STATION_POINTS, 'description': f'Visita verificada por cercanía: {station.name}'})
        except OperationalError:
            # SQLite puede bloquear escrituras simultáneas; un reintento es seguro.
            return Response({'message': 'El registro está ocupado. Inténtalo nuevamente; no se duplicarán puntos.'}, status=503)
        return Response({'created': created, 'points_awarded': STATION_POINTS if awarded else 0,
                         'visited': True, 'visited_at': visit.visited_at,
                         'message': 'Visita registrada: +20 chocopuntos.' if awarded else 'La visita ya estaba registrada. No se duplicaron los puntos.'}, status=201 if created else 200)
