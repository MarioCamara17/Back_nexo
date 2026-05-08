# -*- coding: utf-8 -*-
from rest_framework import serializers
from .models import Municipality, State, Category, Place, Favorite, VisitedPlace
from django.contrib.auth import get_user_model
from routes.models import Route

User = get_user_model()


class StateSerializer(serializers.ModelSerializer):
    class Meta:
        model = State
        fields = '__all__'


class MunicipalitySerializer(serializers.ModelSerializer):
    state = StateSerializer(read_only=True)

    class Meta:
        model = Municipality
        fields = ('id', 'name', 'description', 'state')


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class RouteBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ('id', 'name', 'description', 'duration')


class PlaceSerializer(serializers.ModelSerializer):
    municipality = MunicipalitySerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    route = RouteBasicSerializer(read_only=True)

    class Meta:
        model = Place
        fields = (
            'id',
            'name',
            'description',
            'history',
            'importance',
            'recommendations',
            'schedule',
            'cost',
            'tips',
            'latitude',
            'longitude',
            'image',
            'video',
            'municipality',
            'category',
            'route',
        )


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = '__all__'


class FavoriteDetailSerializer(serializers.ModelSerializer):
    place = PlaceSerializer(read_only=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = Favorite
        fields = '__all__'


class VisitedPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitedPlace
        fields = '__all__'


class VisitedPlaceDetailSerializer(serializers.ModelSerializer):
    place = PlaceSerializer(read_only=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = VisitedPlace
        fields = '__all__'