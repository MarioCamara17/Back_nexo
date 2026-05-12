# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth import get_user_model
import uuid


User = get_user_model()


class PointTransaction(models.Model):
    ACTION_CHOICES = [
        ('visited_place', 'Lugar visitado'),
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