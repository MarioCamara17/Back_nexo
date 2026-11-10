from datetime import time

from django.test import TestCase
from rest_framework.test import APIClient

from routes.models import Route

from .models import Category, Municipality, Place, State


class NearbyPlacesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        state = State.objects.create(name="Tabasco")
        cls.centro = Municipality.objects.create(name="Centro", state=state)
        cls.balancan = Municipality.objects.create(name="Balancán", state=state)
        cls.cultura = Category.objects.create(name="Cultura")
        cls.naturaleza = Category.objects.create(name="Naturaleza")
        cls.route = Route.objects.create(name="Ruta prueba", duration=time(1))

        cls.center_place = Place.objects.create(
            name="Centro",
            description="Centro",
            latitude=18.0,
            longitude=-92.9,
            municipality=cls.centro,
            category=cls.cultura,
            route=cls.route,
        )
        cls.near_place = Place.objects.create(
            name="Cerca",
            description="Cerca",
            latitude=18.01,
            longitude=-92.9,
            municipality=cls.centro,
            category=cls.naturaleza,
            route=cls.route,
        )
        cls.far_place = Place.objects.create(
            name="Lejos",
            description="Lejos",
            latitude=18.2,
            longitude=-92.9,
            municipality=cls.balancan,
            category=cls.naturaleza,
            route=cls.route,
        )

    def setUp(self):
        self.client = APIClient()

    def get_nearby(self, **params):
        payload = {
            "latitude": 18.0,
            "longitude": -92.9,
            "radius_km": 5,
            **params,
        }
        return self.client.get("/api/v1/places/nearby/", payload)

    def test_returns_places_inside_radius_ordered_by_distance(self):
        response = self.get_nearby()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["radius_km"], 5)
        names = [place["name"] for place in response.data["results"]]
        self.assertEqual(names, ["Centro", "Cerca"])
        self.assertEqual(response.data["results"][0]["distance_km"], 0)
        self.assertGreater(response.data["results"][1]["distance_km"], 0)

    def test_large_radius_includes_far_place(self):
        response = self.get_nearby(radius_km=100)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)

    def test_category_filter(self):
        response = self.get_nearby(category="Naturaleza")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {place["name"] for place in response.data["results"]},
            {"Cerca"},
        )

    def test_municipality_filter(self):
        response = self.get_nearby(municipality="Balancán", radius_km=100)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [place["name"] for place in response.data["results"]],
            ["Lejos"],
        )

    def test_search_filter(self):
        response = self.get_nearby(search="Cerca")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [place["name"] for place in response.data["results"]],
            ["Cerca"],
        )

    def test_limit(self):
        response = self.get_nearby(limit=1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_invalid_coordinates(self):
        response = self.get_nearby(latitude=91)
        self.assertEqual(response.status_code, 400)

    def test_invalid_radius(self):
        response = self.get_nearby(radius_km=0)
        self.assertEqual(response.status_code, 400)
