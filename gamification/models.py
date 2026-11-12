# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth import get_user_model
import uuid


User = get_user_model()


class PointTransaction(models.Model):
    ACTION_CHOICES = [
        ('visited_place', 'Lugar visitado'),
        ('visited_station', 'Estación visitada con ubicación'),
        ('favorite_place', 'Lugar agregado a favoritos'),
        ('custom_route', 'Ruta personalizada creada'),
        ('completed_route', 'Ruta completada'),
        ('chatbot_use', 'Uso del chatbot'),
        ('ar_experience', 'Experiencia de realidad aumentada'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='point_transactions'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    points = models.IntegerField(default=0)
    description = models.CharField(max_length=255)
    object_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'action', 'object_id'],
                name='unique_user_action_object_points'
            )
        ]

    def __str__(self):
        return f'{self.user.email} - {self.action} - {self.points} pts'

class TrainStation(models.Model):
    slug = models.SlugField(primary_key=True, max_length=60)
    name = models.CharField(max_length=100)
    municipality = models.CharField(max_length=60)
    order = models.PositiveSmallIntegerField(default=1)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=11, decimal_places=7)
    summary = models.TextField()
    history = models.TextField()
    opening_hours = models.CharField(max_length=255, blank=True)
    timetable_url = models.URLField(default='https://www.trenmaya.gob.mx/horarios.php')
    booking_url = models.URLField(default='https://reservas.ventaboletostrenmaya.com.mx/')
    coordinates_source = models.URLField()
    sources = models.JSONField(default=list)
    checked_on = models.DateField()
    checkin_radius_m = models.PositiveIntegerField(default=300)
    checkin_enabled = models.BooleanField(default=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class StationVisit(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='station_visits')
    station = models.ForeignKey(TrainStation, on_delete=models.PROTECT, related_name='visits')
    visited_at = models.DateTimeField(auto_now_add=True)
    # Solo se conserva precisión y distancia, no la ubicación exacta del usuario.
    accuracy_m = models.FloatField()
    distance_m = models.FloatField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'station'], name='unique_user_train_station_visit')]
        ordering = ['-visited_at']
