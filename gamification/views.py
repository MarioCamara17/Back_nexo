# -*- coding: utf-8 -*-
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum

from .models import PointTransaction
from .serializers import PointTransactionSerializer, AwardPointsSerializer


POINT_RULES = {
    'visited_place': {
        'points': 50,
        'description': 'Marcaste un lugar como visitado'
    },
    'favorite_place': {
        'points': 10,
        'description': 'Agregaste un lugar a favoritos'
    },
    'custom_route': {
        'points': 30,
        'description': 'Creaste una ruta personalizada'
    },
    'completed_route': {
        'points': 150,
        'description': 'Completaste una ruta turística'
    },
    'chatbot_use': {
        'points': 5,
        'description': 'Usaste el chatbot para recibir una recomendación'
    },
}


TOP_LEVEL_POINTS = 1000
TOP_LEVEL_NAME = "Embajador de Tabasco"


LEVELS = [
    {
        'name': 'Visitante inicial',
        'min_points': 0,
        'next_points': 100
    },
    {
        'name': 'Explorador novato',
        'min_points': 100,
        'next_points': 300
    },
    {
        'name': 'Rastreador cultural',
        'min_points': 300,
        'next_points': 600
    },
    {
        'name': 'Guía regional',
        'min_points': 600,
        'next_points': TOP_LEVEL_POINTS
    },
    {
        'name': TOP_LEVEL_NAME,
        'min_points': TOP_LEVEL_POINTS,
        'next_points': None
    },
]


def get_level(points):
    current_level = LEVELS[0]

    for level in LEVELS:
        if points >= level['min_points']:
            current_level = level

    return current_level


def build_badges(user, total_points):
    visited_count = PointTransaction.objects.filter(
        user=user,
        action='visited_place'
    ).count()

    favorite_count = PointTransaction.objects.filter(
        user=user,
        action='favorite_place'
    ).count()

    custom_route_count = PointTransaction.objects.filter(
        user=user,
        action='custom_route'
    ).count()

    completed_route_count = PointTransaction.objects.filter(
        user=user,
        action='completed_route'
    ).count()

    chatbot_count = PointTransaction.objects.filter(
        user=user,
        action='chatbot_use'
    ).count()

    station_count = PointTransaction.objects.filter(
        user=user,
        action='visited_station'
    ).count()

    return [
        {
            'icon': '🏆',
            'name': TOP_LEVEL_NAME,
            'description': f'Alcanza {TOP_LEVEL_POINTS} Chocopuntos.',
            'unlocked': total_points >= TOP_LEVEL_POINTS,
            'is_top_level': True,
        },
        {
            'icon': '📍',
            'name': 'Primer destino',
            'description': 'Marca tu primer lugar como visitado.',
            'unlocked': visited_count >= 1
        },
        {
            'icon': '🌿',
            'name': 'Explorador natural',
            'description': 'Visita 3 lugares turísticos.',
            'unlocked': visited_count >= 3
        },
        {
            'icon': '❤️',
            'name': 'Coleccionista de favoritos',
            'description': 'Agrega 3 lugares a favoritos.',
            'unlocked': favorite_count >= 3
        },
        {
            'icon': '🧭',
            'name': 'Creador de rutas',
            'description': 'Crea tu primera ruta personalizada.',
            'unlocked': custom_route_count >= 1
        },
        {
            'icon': '🏛️',
            'name': 'Guardián cultural',
            'description': 'Completa 2 rutas turísticas.',
            'unlocked': completed_route_count >= 2
        },
        {
            'icon': '💬',
            'name': 'Explorador asistido',
            'description': 'Usa el chatbot para recibir recomendaciones.',
            'unlocked': chatbot_count >= 1
        },
        {
            'icon': '🚉',
            'name': 'Primera estación',
            'description': 'Confirma con tu ubicación la visita a una estación del Tren Maya.',
            'unlocked': station_count >= 1
        },
    ]


class GamificationProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        total_points = PointTransaction.objects.filter(user=user).aggregate(
            total=Sum('points')
        )['total'] or 0

        level = get_level(total_points)
        next_points = level['next_points']

        if next_points is None:
            points_to_next_level = 0
            progress_percent = 100
        else:
            points_to_next_level = max(next_points - total_points, 0)
            level_range = next_points - level['min_points']
            current_progress = total_points - level['min_points']
            progress_percent = int((current_progress / level_range) * 100) if level_range > 0 else 0

        recent_transactions = PointTransaction.objects.filter(user=user)[:5]

        visited_places = PointTransaction.objects.filter(
            user=user,
            action='visited_place'
        ).count()

        favorite_places = PointTransaction.objects.filter(
            user=user,
            action='favorite_place'
        ).count()

        completed_routes = PointTransaction.objects.filter(
            user=user,
            action='completed_route'
        ).count()

        badges = build_badges(user, total_points)

        return Response({
            'points': total_points,
            'level': level['name'],
            'next_level_points': next_points,
            'points_to_next_level': points_to_next_level,
            'progress_percent': progress_percent,
            'visited_places': visited_places,
            'favorite_places': favorite_places,
            'completed_routes': completed_routes,
            'badges': badges,
            'unlocked_badges_count': len([badge for badge in badges if badge['unlocked']]),
            'recent_activities': PointTransactionSerializer(
                recent_transactions,
                many=True
            ).data
        }, status=status.HTTP_200_OK)


class AwardPointsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AwardPointsSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data.get('action')
        object_id = serializer.validated_data.get('object_id') or None

        if action not in POINT_RULES:
            return Response(
                {'message': 'Acción de gamificación no válida.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        rule = POINT_RULES[action]

        transaction, created = PointTransaction.objects.get_or_create(
            user=request.user,
            action=action,
            object_id=object_id,
            defaults={
                'points': rule['points'],
                'description': rule['description']
            }
        )

        if not created:
            return Response({
                'created': False,
                'message': 'Esta acción ya había otorgado puntos anteriormente.',
                'transaction': PointTransactionSerializer(transaction).data
            }, status=status.HTTP_200_OK)

        return Response({
            'created': True,
            'message': 'Puntos otorgados correctamente.',
            'transaction': PointTransactionSerializer(transaction).data
        }, status=status.HTTP_201_CREATED)