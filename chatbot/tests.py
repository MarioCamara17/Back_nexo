from datetime import time
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from places.models import State, Municipality, Category, Place, VisitedPlace
from routes.models import Route
from .views import ChatbotView


class PreconfiguredChatTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        state = State.objects.create(name='Estado prueba')
        municipality = Municipality.objects.create(name='Municipio prueba', state=state)
        category = Category.objects.create(name='Cultura')
        route = Route.objects.create(name='Ruta prueba', duration=time(1))
        cls.place = Place.objects.create(name='Sitio prueba', description='Descripción',
            history='Historia documentada', schedule='9 a 17', cost='20', latitude=17.8,
            longitude=-91.5, municipality=municipality, category=category, route=route)

    def ask(self, data, status=200):
        response = ChatbotView.as_view()(APIRequestFactory().post('/api/chat/', data, format='json'))
        self.assertEqual(response.status_code, status)
        return response.data

    def test_menu(self):
        response = ChatbotView.as_view()(APIRequestFactory().get('/api/chat/'))
        self.assertEqual(len(response.data['menu']), 9)

    def test_information_uses_registered_content(self):
        self.assertEqual(self.ask({'intent':'history','place_id':str(self.place.pk)})['reply'], self.place.history)
        self.assertIn('20', self.ask({'intent':'logistics','place_id':str(self.place.pk)})['reply'])
        self.assertIn('no hay', self.ask({'intent':'legends','place_id':str(self.place.pk)})['reply'].lower())

    def test_nearby_and_empty_radius(self):
        found = self.ask({'intent':'nearby','latitude':17.8,'longitude':-91.5})
        self.assertEqual(found['places'][0]['distance_km'], 0)
        self.assertFalse(self.ask({'intent':'nearby','latitude':0,'longitude':0})['places'])

    def test_invalid_inputs(self):
        for payload in [{'intent':'nearby'}, {'intent':'nearby','latitude':'NaN','longitude':0},
                        {'intent':'history','place_id':'invalido'}, {'intent':'desconocido'},
                        {'intent':'nearby','latitude':91,'longitude':0},
                        {'intent':'itinerary','minutes':0}]:
            self.ask(payload, 400)
        self.ask({'intent':'history','place_id':'00000000-0000-0000-0000-000000000000'}, 404)

    def test_popularity_requires_evidence(self):
        self.assertFalse(self.ask({'intent':'popular'})['places'])
        User = get_user_model()
        user = User.objects.create(**{User.USERNAME_FIELD: 'prueba@example.com' if User.USERNAME_FIELD == 'email' else 'prueba'})
        VisitedPlace.objects.create(user=user, place=self.place)
        self.assertEqual(self.ask({'intent':'popular'})['places'][0]['id'], str(self.place.pk))

    def test_itinerary_time_limit(self):
        self.assertTrue(self.ask({'intent':'itinerary','minutes':60})['actions'])
        self.assertFalse(self.ask({'intent':'itinerary','minutes':30})['actions'])

    def test_map_actions_and_help(self):
        self.assertEqual(self.ask({'intent':'filter'})['actions'][0]['category'], 'Cultura')
        self.assertEqual(self.ask({'intent':'directions','place_id':str(self.place.pk)})['actions'][0]['type'], 'directions')
        self.assertEqual(self.ask({'intent':'favorites'})['actions'][0]['type'], 'favorites')