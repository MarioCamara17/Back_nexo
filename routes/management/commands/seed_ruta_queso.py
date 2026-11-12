from datetime import time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from places.models import Category, Municipality, Place, State
from routes.models import Municipality_has_Route, Route


ROUTE_NAME = 'Ruta del Queso de Poro de Balancán'
STOPS = (
    (
        'Quesería San Marquito', '17.81190200', '-91.53700200',
        'Calle 20 de Noviembre, colonia Gregorio Méndez.',
        'Comienza por conocer el queso de poro y pregunta por las variedades locales.',
    ),
    (
        'Quesería San Judas Tadeo', '17.81122500', '-91.53823800',
        'Calle Agustín de Iturbide, colonia Gregorio Méndez.',
        'Pregunta por la textura del queso de poro y cómo se usa en la cocina local.',
    ),
    (
        'Quesería Bejucal', '17.80247600', '-91.54126700',
        'Francisco I. Madero 712, colonia Las Flores.',
        'Conoce una quesería familiar documentada en estudios sobre la producción artesanal.',
    ),
)


class Command(BaseCommand):
    help = 'Carga la Ruta del Queso de Poro y sus paradas en Balancán.'

    @transaction.atomic
    def handle(self, *args, **options):
        state, _ = State.objects.get_or_create(name__iexact='Tabasco', defaults={'name': 'Tabasco'})
        municipality, _ = Municipality.objects.get_or_create(
            state=state, name__iexact='Balancán', defaults={'name': 'Balancán'},
        )
        category, _ = Category.objects.get_or_create(
            name__iexact='Gastronomía', defaults={'name': 'Gastronomía'},
        )
        route, _ = Route.objects.get_or_create(
            name=ROUTE_NAME,
            defaults={
                'description': (
                    'Conoce el queso de poro en Balancán, cuna de esta tradición '
                    'gastronómica, a través de tres queserías de la cabecera municipal. '
                    'Recorrido sugerido: San Marquito, San Judas Tadeo y Bejucal. '
                    'Duración estimada: 90 minutos.'
                ),
                'duration': time(1, 30),
            },
        )
        Municipality_has_Route.objects.get_or_create(municipality=municipality, route=route)

        for name, latitude, longitude, address, description in STOPS:
            place, created = Place.objects.get_or_create(
                municipality=municipality,
                name__iexact=name,
                defaults={
                    'name': name,
                    'category': category,
                    'route': route,
                    'latitude': Decimal(latitude),
                    'longitude': Decimal(longitude),
                    'description': f'{description} {address}',
                    'recommendations': 'Confirma el horario y la disponibilidad antes de ir.',
                },
            )
            if not created and (place.route_id != route.pk or place.category_id != category.pk):
                place.route = route
                place.category = category
                place.save(update_fields=['route', 'category'])

        self.stdout.write(self.style.SUCCESS(f'Ruta cargada: {route.name} ({len(STOPS)} paradas).'))