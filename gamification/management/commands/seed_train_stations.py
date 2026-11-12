from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from gamification.models import TrainStation
from gamification.station_catalog import STATIONS, CHECKED_ON


class Command(BaseCommand):
    help = 'Carga solo las estaciones que aún no existen; no sobrescribe ediciones del administrador.'

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        for station in STATIONS:
            data = dict(station)
            slug = data.pop('slug')
            data['checked_on'] = date.fromisoformat(CHECKED_ON)
            _, created = TrainStation.objects.get_or_create(slug=slug, defaults=data)
            created_count += int(created)
        self.stdout.write(self.style.SUCCESS(f'Estaciones creadas: {created_count}. Existentes conservadas.'))
