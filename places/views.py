# -*- coding: utf-8 -*-
import math

from rest_framework import viewsets, permissions, filters, serializers
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from django.db.models import Q
from .models import State, Municipality, Category, Place, Favorite, VisitedPlace
from .geo import bounding_box, distance_km, valid_coordinates
from .serializers import (
    StateSerializer, 
    MunicipalitySerializer, 
    CategorySerializer, 
    PlaceSerializer, 
    FavoriteSerializer,
    FavoriteDetailSerializer,
    VisitedPlaceSerializer,
    VisitedPlaceDetailSerializer
)
from django.contrib.auth import get_user_model
from rest_framework.decorators import action
from django.utils import timezone

User = get_user_model()


class NearbyQuerySerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    radius_km = serializers.FloatField(
        min_value=0.5,
        max_value=100,
        required=False,
        default=5,
    )
    category = serializers.CharField(required=False, allow_blank=True)
    municipality = serializers.CharField(required=False, allow_blank=True)
    search = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(
        min_value=1,
        max_value=100,
        required=False,
        default=50,
    )

    def validate(self, attrs):
        for field in ("latitude", "longitude", "radius_km"):
            value = attrs.get(field)
            if value is not None and not math.isfinite(value):
                raise serializers.ValidationError({
                    field: "Introduce un número finito."
                })
        return attrs



class IsAdminUserOrReadOnly(permissions.BasePermission):
    """
    Custom permission that allows all users to perform read operations,
    but only allows admin users to perform write operations.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user and (request.user.is_staff or request.user.is_superuser)


class StateViewSet(viewsets.ModelViewSet):
    queryset = State.objects.all()
    serializer_class = StateSerializer
    permission_classes = [IsAdminUserOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class MunicipalityViewSet(viewsets.ModelViewSet):
    queryset = Municipality.objects.all()
    serializer_class = MunicipalitySerializer
    permission_classes = [IsAdminUserOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'state__name']


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUserOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class PlaceViewSet(viewsets.ModelViewSet):
    queryset = Place.objects.all()
    serializer_class = PlaceSerializer
    permission_classes = [IsAdminUserOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = [
        'name',
        'municipality__name',
        'municipality__id',
        'category__name',
        'category__id',
        'route__name',
        'route__id'
    ]
    pagination_class = None

    @action(detail=False, methods=['get'], url_path='nearby')
    def nearby(self, request):
        """Lugares dentro de un radio, ordenados por distancia geodésica.

        Parámetros: latitude, longitude, radius_km, category, municipality,
        search y limit. La distancia es en línea recta, no por carretera.
        """
        serializer = NearbyQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        latitude = data['latitude']
        longitude = data['longitude']
        radius_km = data.get('radius_km', 5)
        limit = data.get('limit', 50)

        bounds = bounding_box(latitude, longitude, radius_km)
        if bounds is None:
            return Response(
                {'detail': 'Coordenadas o radio inválidos.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        min_lat, max_lat, min_lng, max_lng = bounds

        queryset = (
            self.get_queryset()
            .select_related('category', 'municipality', 'route')
            .filter(
                latitude__gte=min_lat,
                latitude__lte=max_lat,
                longitude__gte=min_lng,
                longitude__lte=max_lng,
            )
        )

        category = (data.get('category') or '').strip()
        municipality = (data.get('municipality') or '').strip()
        search = (data.get('search') or '').strip()

        if category:
            queryset = queryset.filter(category__name__iexact=category)
        if municipality:
            queryset = queryset.filter(municipality__name__iexact=municipality)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(municipality__name__icontains=search)
                | Q(category__name__icontains=search)
            )

        results = []

        for place in queryset:
            if not valid_coordinates(place.latitude, place.longitude):
                continue

            try:
                distance = distance_km(
                    latitude,
                    longitude,
                    place.latitude,
                    place.longitude,
                )
            except ValueError:
                continue

            if distance > radius_km:
                continue

            payload = PlaceSerializer(
                place,
                context={'request': request},
            ).data
            payload['distance_km'] = round(distance, 2)
            results.append((distance, payload))

        results.sort(key=lambda item: (item[0], item[1]['name'].casefold()))
        payloads = [item[1] for item in results[:limit]]

        return Response({
            'center': {
                'latitude': latitude,
                'longitude': longitude,
            },
            'radius_km': radius_km,
            'count': len(payloads),
            'results': payloads,
        })

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_visited(self, request, pk=None):
        """
        Marca o desmarca un lugar como visitado por el usuario actual
        """
        place = self.get_object()
        user = request.user
        
        visited = VisitedPlace.objects.filter(place=place, user=user).first()
        
        if visited:
            visited.delete()
            return Response(
                {"message": "Lugar desmarcado como visitado correctamente"},
                status=status.HTTP_200_OK
            )
        else:
            visited_date = request.data.get('visited_date', timezone.now().date())
            notes = request.data.get('notes', '')
            
            visited = VisitedPlace.objects.create(
                place=place,
                user=user,
                visited_date=visited_date,
                notes=notes
            )
            
            serializer = VisitedPlaceSerializer(visited)
            return Response(
                {"message": "Lugar marcado como visitado correctamente", "data": serializer.data},
                status=status.HTTP_201_CREATED
            )


class FavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user)

    def list(self, request):
        queryset = self.get_queryset()
        serializer = FavoriteDetailSerializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request):
        # Verificar si el favorito ya existe antes de intentar crearlo
        place_id = request.data.get('place')
        if not place_id:
            return Response(
                {"error": "Se requiere el ID del lugar"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Verificar si el favorito ya existe
        existing_favorite = Favorite.objects.filter(
            user=request.user, 
            place_id=place_id
        ).first()
        
        if existing_favorite:
            # Si ya existe, devolver el favorito existente con un mensaje
            serializer = FavoriteDetailSerializer(existing_favorite)
            return Response(
                {
                    "message": "Este lugar ya está en tus favoritos",
                    "favorite": serializer.data
                }, 
                status=status.HTTP_200_OK
            )
        
        # Si no existe, crear uno nuevo
        try:
            # Crear un nuevo diccionario de datos que incluya el usuario
            data = {
                'place': place_id,
                'user': request.user.id
            }
            
            serializer = self.get_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"No se pudo guardar el favorito: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def destroy(self, request, pk=None):
        favorite = get_object_or_404(Favorite, id=pk, user=request.user)
        favorite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
        
    @action(detail=False, methods=['post'])
    def toggle(self, request):
        """
        Alterna un lugar como favorito: si ya existe lo elimina, si no existe lo crea
        """
        place_id = request.data.get('place')
        if not place_id:
            return Response(
                {"error": "Se requiere el ID del lugar"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Verificar si el favorito ya existe
        existing_favorite = Favorite.objects.filter(
            user=request.user, 
            place_id=place_id
        ).first()
        
        if existing_favorite:
            # Si ya existe, eliminarlo
            existing_favorite.delete()
            return Response(
                {"message": "Favorito eliminado correctamente"}, 
                status=status.HTTP_200_OK
            )
        else:
            # Si no existe, crearlo
            data = {
                'place': place_id,
                'user': request.user.id
            }
            
            serializer = self.get_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"message": "Favorito agregado correctamente", "data": serializer.data}, 
                    status=status.HTTP_201_CREATED
                )
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VisitedPlaceViewSet(viewsets.ModelViewSet):
    serializer_class = VisitedPlaceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return VisitedPlace.objects.filter(user=self.request.user)

    def list(self, request):
        queryset = self.get_queryset()
        serializer = VisitedPlaceDetailSerializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request):
        # Verificar si el lugar ya está marcado como visitado antes de intentar crearlo
        place_id = request.data.get('place')
        if not place_id:
            return Response(
                {"error": "Se requiere el ID del lugar"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Verificar si el lugar ya está marcado como visitado
        existing_visit = VisitedPlace.objects.filter(
            user=request.user, 
            place_id=place_id
        ).first()
        
        if existing_visit:
            # Si ya está marcado como visitado, devolver el registro existente con un mensaje
            serializer = VisitedPlaceDetailSerializer(existing_visit)
            return Response(
                {
                    "message": "Este lugar ya está marcado como visitado",
                    "visited_place": serializer.data
                }, 
                status=status.HTTP_200_OK
            )
        
        # Si no existe, crear uno nuevo
        try:
            # Crear un nuevo diccionario de datos que incluya el usuario
            data = {
                'place': place_id,
                'user': request.user.id,
                'visited_date': request.data.get('visited_date', timezone.now().date()),
                'notes': request.data.get('notes', '')
            }
            
            serializer = self.get_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"No se pudo guardar el lugar como visitado: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def destroy(self, request, pk=None):
        visited_place = get_object_or_404(VisitedPlace, id=pk, user=request.user)
        visited_place.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
        
    @action(detail=False, methods=['post'])
    def toggle(self, request):
        """
        Alterna un lugar como visitado: si ya existe lo elimina, si no existe lo crea
        """
        place_id = request.data.get('place')
        if not place_id:
            return Response(
                {"error": "Se requiere el ID del lugar"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Verificar si el lugar ya está marcado como visitado
        existing_visit = VisitedPlace.objects.filter(
            user=request.user, 
            place_id=place_id
        ).first()
        
        if existing_visit:
            # Si ya está marcado como visitado, lo eliminamos
            existing_visit.delete()
            return Response(
                {"message": "Lugar desmarcado como visitado correctamente"}, 
                status=status.HTTP_200_OK
            )
        else:
            # Si no está marcado como visitado, lo marcamos
            data = {
                'place': place_id,
                'user': request.user.id,
                'visited_date': request.data.get('visited_date', timezone.now().date()),
                'notes': request.data.get('notes', '')
            }
            
            serializer = self.get_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"message": "Lugar marcado como visitado correctamente", "data": serializer.data}, 
                    status=status.HTTP_201_CREATED
                )
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
