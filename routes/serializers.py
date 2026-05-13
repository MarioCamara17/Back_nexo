# -*- coding: utf-8 -*-
from rest_framework import serializers
from places.serializers import MunicipalitySerializer, PlaceSerializer
from .models import Route, Municipality_has_Route, CustomRoute, CustomRoutePlace


class RouteSerializer(serializers.ModelSerializer):
    places = PlaceSerializer(read_only=True, many=True)

    class Meta:
        model = Route
        fields = ('id', 'name', 'description', 'duration', 'places', 'municipalities')

    class NestedMunicipalityHasRouteSerializer(serializers.ModelSerializer):
        municipality = MunicipalitySerializer(read_only=True)

        class Meta:
            model = Municipality_has_Route
            fields = ('municipality')

    municipalities = NestedMunicipalityHasRouteSerializer(read_only=True, many=True)


class MunicipalityHasRouteSerializer(serializers.ModelSerializer):
    route = RouteSerializer(read_only=True)
    municipality = MunicipalitySerializer(read_only=True)

    class Meta:
        model = Municipality_has_Route
        fields = ('route', 'municipality')

class CustomRoutePlaceSerializer(serializers.ModelSerializer):
    place_name = serializers.CharField(source='place.name', read_only=True)
    place_latitude = serializers.DecimalField(
        source='place.latitude',
        max_digits=10,
        decimal_places=8,
        read_only=True
    )
    place_longitude = serializers.DecimalField(
        source='place.longitude',
        max_digits=11,
        decimal_places=8,
        read_only=True
    )
    place_image = serializers.ImageField(source='place.image', read_only=True)

    class Meta:
        model = CustomRoutePlace
        fields = [
            'id',
            'place',
            'place_name',
            'place_latitude',
            'place_longitude',
            'place_image',
            'order'
        ]


class CustomRouteSerializer(serializers.ModelSerializer):
    route_places = CustomRoutePlaceSerializer(many=True, read_only=True)
    places = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=True
    )

    class Meta:
        model = CustomRoute
        fields = [
            'id',
            'name',
            'description',
            'created_at',
            'route_places',
            'places'
        ]

    def create(self, validated_data):
        places = validated_data.pop('places')
        user = self.context['request'].user

        custom_route = CustomRoute.objects.create(
            user=user,
            **validated_data
        )

        for index, place_id in enumerate(places, start=1):
            CustomRoutePlace.objects.create(
                custom_route=custom_route,
                place_id=place_id,
                order=index
            )

        return custom_route
