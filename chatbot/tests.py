from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from places.models import Category, Municipality, Place, State, VisitedPlace
from routes.models import Route

from .models import ChatSession
from .views import ChatbotView


class ConversationalChatTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        state = State.objects.create(name="Tabasco")
        cls.centro = Municipality.objects.create(name="Centro", state=state)
        cls.balancan = Municipality.objects.create(name="Balancán", state=state)

        cls.naturaleza = Category.objects.create(name="Naturaleza")
        cls.cultura = Category.objects.create(name="Cultura")

        cls.route = Route.objects.create(name="Ruta natural", duration=time(2))

        cls.la_venta = Place.objects.create(
            name="Parque Museo La Venta",
            description="Parque museo al aire libre.",
            history="Historia documentada de La Venta.",
            schedule="9 a 17",
            cost="20",
            latitude=18.00204,
            longitude=-92.93411,
            municipality=cls.centro,
            category=cls.cultura,
            route=cls.route,
        )
        cls.yumka = Place.objects.create(
            name="Yumká",
            description="Centro de interpretación ambiental.",
            history="Historia de Yumká.",
            schedule="8 a 16",
            cost="50",
            latitude=18.00081,
            longitude=-92.80409,
            municipality=cls.centro,
            category=cls.naturaleza,
            route=cls.route,
        )
        cls.cascadas = Place.objects.create(
            name="Cascadas de Reforma",
            description="Cascadas naturales.",
            history="Historia de las cascadas.",
            latitude=17.75621,
            longitude=-91.37381,
            municipality=cls.balancan,
            category=cls.naturaleza,
            route=cls.route,
        )

    def ask(self, data, status=200):
        response = ChatbotView.as_view()(
            APIRequestFactory().post("/api/chat/", data, format="json")
        )
        self.assertEqual(response.status_code, status)
        return response.data

    def test_free_text_greeting(self):
        result = self.ask({"message": "Hola"})
        self.assertIn("NEXO", result["reply"])
        self.assertTrue(result["suggestions"])
        self.assertEqual(result["meta"]["intent"], "greeting")

    def test_nearby_requires_location(self):
        result = self.ask({"message": "¿Qué hay cerca de mí?"})
        self.assertTrue(result["meta"]["requires_location"])
        self.assertEqual(result["actions"][0]["type"], "location")

    def test_nearby_with_location_and_radius(self):
        result = self.ask({
            "message": "¿Qué hay cerca de mí?",
            "latitude": 18.00204,
            "longitude": -92.93411,
            "radius_km": 5,
        })
        self.assertFalse(result["meta"]["requires_location"])
        self.assertEqual(result["meta"]["radius_km"], 5)
        self.assertEqual(result["places"][0]["id"], str(self.la_venta.pk))
        self.assertEqual(result["places"][0]["distance_km"], 0)
        self.assertTrue(result["actions"])

    def test_place_history_and_memory(self):
        first = self.ask({
            "message": "Cuéntame la historia del Parque Museo La Venta",
        })
        self.assertIn("Historia documentada", first["reply"])
        self.assertEqual(first["context"]["place_id"], str(self.la_venta.pk))

        second = self.ask({
            "message": "¿Y sus leyendas?",
            "session_id": first["session_id"],
        })
        self.assertEqual(second["context"]["place_id"], str(self.la_venta.pk))
        self.assertEqual(second["meta"]["intent"], "legends")

    def test_place_id_is_saved_in_session_memory(self):
        first = self.ask({"message": "Hola"})
        second = self.ask({
            "message": "¿Y sus leyendas?",
            "session_id": first["session_id"],
            "place_id": str(self.la_venta.pk),
        })

        self.assertEqual(second["context"]["place_id"], str(self.la_venta.pk))
        self.assertEqual(second["context"]["place_name"], "Parque Museo La Venta")

        session = ChatSession.objects.get(pk=first["session_id"])
        self.assertEqual(session.last_place_id, self.la_venta.pk)

    def test_filter_by_category(self):
        result = self.ask({"message": "Muéstrame solo naturaleza"})
        self.assertEqual(result["meta"]["intent"], "filter")
        self.assertTrue(result["places"])
        self.assertTrue(
            all(place["category"] == "Naturaleza" for place in result["places"])
        )

    def test_itinerary_with_location(self):
        result = self.ask({
            "message": "Arma un recorrido de un día",
            "latitude": 18.00204,
            "longitude": -92.93411,
            "radius_km": 20,
        })
        self.assertEqual(result["kind"], "itinerary")
        self.assertTrue(result["actions"])
        self.assertGreater(result["meta"]["estimated_minutes"], 0)

    def test_radius_extraction(self):
        result = self.ask({
            "message": "Busca lugares en un radio de 10 km",
            "latitude": 18.00204,
            "longitude": -92.93411,
        })
        self.assertEqual(result["context"]["radius_km"], 10)
        self.assertEqual(result["meta"]["radius_km"], 10)

    def test_session_is_reused(self):
        first = self.ask({"message": "Hola"})
        second = self.ask({
            "message": "Muéstrame todos los lugares",
            "session_id": first["session_id"],
        })
        self.assertEqual(first["session_id"], second["session_id"])
        self.assertEqual(ChatSession.objects.count(), 1)

    def test_empty_message_is_rejected(self):
        self.ask({"message": "   "}, 400)

    def test_delete_session(self):
        first = self.ask({"message": "Hola"})
        response = ChatbotView.as_view()(
            APIRequestFactory().delete(
                f"/api/chat/?session_id={first['session_id']}"
            )
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            ChatSession.objects.filter(pk=first["session_id"]).exists()
        )


class LegacyChatTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        state = State.objects.create(name="Estado prueba")
        municipality = Municipality.objects.create(name="Municipio prueba", state=state)
        category = Category.objects.create(name="Cultura")
        route = Route.objects.create(name="Ruta prueba", duration=time(1))
        cls.place = Place.objects.create(
            name="Sitio prueba",
            description="Descripción",
            history="Historia documentada",
            schedule="9 a 17",
            cost="20",
            latitude=17.8,
            longitude=-91.5,
            municipality=municipality,
            category=category,
            route=route,
        )

    def ask(self, data, status=200):
        response = ChatbotView.as_view()(
            APIRequestFactory().post("/api/chat/", data, format="json")
        )
        self.assertEqual(response.status_code, status)
        return response.data

    def test_menu(self):
        response = ChatbotView.as_view()(APIRequestFactory().get("/api/chat/"))
        self.assertEqual(len(response.data["menu"]), 9)

    def test_information_uses_registered_content(self):
        self.assertEqual(
            self.ask({"intent": "history", "place_id": str(self.place.pk)})["reply"],
            self.place.history,
        )
        self.assertIn(
            "20",
            self.ask({"intent": "logistics", "place_id": str(self.place.pk)})["reply"],
        )
        self.assertIn(
            "no hay",
            self.ask({"intent": "legends", "place_id": str(self.place.pk)})["reply"].lower(),
        )

    def test_nearby_and_empty_radius(self):
        found = self.ask({"intent": "nearby", "latitude": 17.8, "longitude": -91.5})
        self.assertEqual(found["places"][0]["distance_km"], 0)
        self.assertFalse(
            self.ask({"intent": "nearby", "latitude": 0, "longitude": 0})["places"]
        )

    def test_invalid_inputs(self):
        for payload in [
            {"intent": "nearby"},
            {"intent": "nearby", "latitude": "NaN", "longitude": 0},
            {"intent": "history", "place_id": "invalido"},
            {"intent": "desconocido"},
            {"intent": "nearby", "latitude": 91, "longitude": 0},
            {"intent": "itinerary", "minutes": 0},
        ]:
            self.ask(payload, 400)
        self.ask(
            {"intent": "history", "place_id": "00000000-0000-0000-0000-000000000000"},
            404,
        )

    def test_popularity_requires_evidence(self):
        self.assertFalse(self.ask({"intent": "popular"})["places"])
        User = get_user_model()
        user = User.objects.create(
            **{
                User.USERNAME_FIELD: (
                    "prueba@example.com"
                    if User.USERNAME_FIELD == "email"
                    else "prueba"
                )
            }
        )
        VisitedPlace.objects.create(user=user, place=self.place)
        self.assertEqual(
            self.ask({"intent": "popular"})["places"][0]["id"],
            str(self.place.pk),
        )

    def test_itinerary_time_limit(self):
        self.assertTrue(self.ask({"intent": "itinerary", "minutes": 60})["actions"])
        self.assertFalse(self.ask({"intent": "itinerary", "minutes": 30})["actions"])

    def test_map_actions_and_help(self):
        self.assertEqual(
            self.ask({"intent": "filter"})["actions"][0]["category"],
            "Cultura",
        )
        self.assertEqual(
            self.ask({"intent": "directions", "place_id": str(self.place.pk)})["actions"][0]["type"],
            "directions",
        )
        self.assertEqual(
            self.ask({"intent": "favorites"})["actions"][0]["type"],
            "favorites",
        )
