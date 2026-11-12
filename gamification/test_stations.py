import time
from unittest.mock import patch
from datetime import time as duration_time
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient
from .models import TrainStation, StationVisit, PointTransaction
from places.models import State, Municipality, Category, Place
from routes.models import Route


class StationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_train_stations', verbosity=0)
        User = get_user_model()
        cls.user = User.objects.create(**{User.USERNAME_FIELD: 'station-test@example.com' if User.USERNAME_FIELD == 'email' else 'station-test'})
        cls.other = User.objects.create(**{User.USERNAME_FIELD: 'station-other@example.com' if User.USERNAME_FIELD == 'email' else 'station-other'})
        cls.station = TrainStation.objects.get(pk='tenosique')
        state = State.objects.create(name='Tabasco')
        municipality = Municipality.objects.create(name='Tenosique', state=state)
        category = Category.objects.create(name='Cultura')
        route = Route.objects.create(name='Prueba', duration=duration_time(1))
        cls.place = Place.objects.create(name='Atractivo de prueba', description='Prueba', latitude=cls.station.latitude,
            longitude=cls.station.longitude, municipality=municipality, category=category, route=route)

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/gamification/stations/tenosique/visit/'

    def position(self, **changes):
        data = {'latitude':float(self.station.latitude), 'longitude':float(self.station.longitude),
                'accuracy_m':10, 'timestamp_ms':time.time()*1000}
        data.update(changes)
        return data

    def test_public_catalog_and_seed_idempotent(self):
        self.assertEqual(len(self.client.get('/api/v1/gamification/stations/').data['stations']), 3)
        self.station.summary='Texto editado';self.station.save()
        call_command('seed_train_stations', verbosity=0)
        self.station.refresh_from_db()
        self.assertEqual(self.station.summary,'Texto editado')
        self.assertEqual(TrainStation.objects.count(),3)

    def test_requires_authentication(self):
        self.assertIn(self.client.post(self.url,self.position(),format='json').status_code,[401,403])
        self.assertEqual(StationVisit.objects.count(),0)

    def test_twenty_points_once_and_user_isolation(self):
        self.client.force_authenticate(self.user)
        first=self.client.post(self.url,self.position(),format='json')
        self.assertEqual(first.status_code,201)
        self.assertEqual(first.data['points_awarded'],20)
        again=self.client.post(self.url,{},format='json')
        self.assertEqual(again.status_code,200)
        self.assertEqual(again.data['points_awarded'],0)
        profile=self.client.get('/api/v1/gamification/profile/').data
        self.assertEqual(profile['points'],20)
        mine=self.client.get('/api/v1/gamification/stations/').data['stations']
        self.assertTrue(next(s for s in mine if s['slug']=='tenosique')['visited'])
        self.client.force_authenticate(self.other)
        others=self.client.get('/api/v1/gamification/stations/').data['stations']
        self.assertFalse(next(s for s in others if s['slug']=='tenosique')['visited'])
        self.assertEqual(self.client.post(self.url,self.position(),format='json').status_code,201)
        self.assertEqual(StationVisit.objects.count(),2)
        self.assertEqual(PointTransaction.objects.count(),2)

    def test_rejects_far_poor_old_nan_and_missing(self):
        self.client.force_authenticate(self.user)
        cases=[self.position(latitude=0,longitude=0),self.position(accuracy_m=101),
            self.position(timestamp_ms=(time.time()-120)*1000),self.position(timestamp_ms=(time.time()+120)*1000),
            self.position(latitude='NaN'),self.position(accuracy_m='Infinity'),self.position(latitude=91),{}]
        for data in cases:
            with self.subTest(data=data):self.assertEqual(self.client.post(self.url,data,format='json').status_code,400)
        self.assertEqual(StationVisit.objects.count(),0)
        self.assertEqual(PointTransaction.objects.count(),0)

    def test_boundary_accounts_for_uncertainty(self):
        self.client.force_authenticate(self.user)
        with patch('gamification.station_views.distance_km',return_value=.25):
            self.assertEqual(self.client.post(self.url,self.position(accuracy_m=80),format='json').status_code,400)
        self.assertEqual(StationVisit.objects.count(),0)

    def test_disabled_and_unknown_station(self):
        self.client.force_authenticate(self.user)
        TrainStation.objects.filter(pk='tenosique').update(checkin_enabled=False)
        self.assertEqual(self.client.post(self.url,self.position(),format='json').status_code,409)
        self.assertEqual(self.client.post('/api/v1/gamification/stations/unknown/visit/',self.position(),format='json').status_code,404)

    def test_generic_award_does_not_bypass_location(self):
        self.client.force_authenticate(self.user)
        result=self.client.post('/api/v1/gamification/award/',{'action':'visited_station','object_id':'tenosique'},format='json')
        self.assertEqual(result.status_code,400)
        self.assertEqual(PointTransaction.objects.count(),0)

    def test_rollback_when_award_fails(self):
        self.client.force_authenticate(self.user)
        with patch('gamification.station_views.PointTransaction.objects.get_or_create',side_effect=RuntimeError('test')):
            with self.assertRaises(RuntimeError):self.client.post(self.url,self.position(),format='json')
        self.assertEqual(StationVisit.objects.count(),0)

    def test_nearby_and_invalid_radius(self):
        url='/api/v1/gamification/stations/tenosique/nearby/'
        self.assertEqual(self.client.get(url,{'radius_km':5}).data['results'][0]['id'],str(self.place.pk))
        for radius in ['NaN',0,101,'bad']:
            self.assertEqual(self.client.get(url,{'radius_km':radius}).status_code,400)
