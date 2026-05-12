# -*- coding: utf-8 -*-
from rest_framework import serializers
from .models import PointTransaction


class PointTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PointTransaction
        fields = [
            'id',
            'action',
            'points',
            'description',
            'object_id',
            'created_at'
        ]


class AwardPointsSerializer(serializers.Serializer):
    action = serializers.CharField()
    object_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)