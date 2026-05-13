# -*- coding: utf-8 -*-
from rest_framework import viewsets, permissions
from .models import Route, Municipality_has_Route, CustomRoute
from .serializers import (
    RouteSerializer,
    MunicipalityHasRouteSerializer,
    CustomRouteSerializer
)


class IsAdminUserOrReadOnly(permissions.BasePermission):
    """
    Permite operaciones de lectura a todos los usuarios,
    pero solo permite crear, editar o eliminar a usuarios administradores.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user and (request.user.is_staff or request.user.is_superuser)


class RouteViewSet(viewsets.ModelViewSet):
    """
    Endpoint para ver y administrar rutas generales del sistema.
    """
    queryset = Route.objects.all()
    serializer_class = RouteSerializer
    permission_classes = [IsAdminUserOrReadOnly]


class MunicipalityHasRouteViewSet(viewsets.ModelViewSet):
    """
    Endpoint para ver y administrar relaciones entre municipios y rutas.
    """
    queryset = Municipality_has_Route.objects.all()
    serializer_class = MunicipalityHasRouteSerializer
    permission_classes = [IsAdminUserOrReadOnly]


class CustomRouteViewSet(viewsets.ModelViewSet):
    """
    Endpoint para que cada usuario cree y consulte sus rutas personalizadas.
    """
    serializer_class = CustomRouteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CustomRoute.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save()