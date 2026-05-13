# -*- coding: utf-8 -*-
from django.db import models
import uuid

class Route(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)
    duration = models.TimeField()

    def __str__(self):
        return self.name


class Municipality_has_Route(models.Model):
    municipality = models.ForeignKey('places.Municipality', on_delete=models.CASCADE)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('municipality', 'route')
        verbose_name = "Ruta Municipal"
        verbose_name_plural = "Rutas Municipales"

    def __str__(self):
        return f"{self.municipality.name} - {self.route.name}"

from django.contrib.auth import get_user_model
from places.models import Place
import uuid


User = get_user_model()


class CustomRoute(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='custom_routes'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Custom Route'
        verbose_name_plural = 'Custom Routes'

    def __str__(self):
        return f'{self.name} - {self.user.email}'


class CustomRoutePlace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    custom_route = models.ForeignKey(
        CustomRoute,
        on_delete=models.CASCADE,
        related_name='route_places'
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name='custom_route_places'
    )
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']
        unique_together = ('custom_route', 'place')

    def __str__(self):
        return f'{self.custom_route.name} - {self.order}. {self.place.name}'