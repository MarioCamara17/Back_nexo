# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid


class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, max_length=150)

    avatar = models.ImageField(
        upload_to='users/avatars',
        null=True,
        blank=True,
        verbose_name='Foto de perfil'
    )

    description = models.TextField(
        null=True,
        blank=True,
        verbose_name='Descripción'
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    def __str__(self):
        return self.email