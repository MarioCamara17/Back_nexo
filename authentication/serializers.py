# -*- coding: utf-8 -*-
from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.hashers import make_password
from django.utils.translation import gettext_lazy as _


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False)
    password = serializers.CharField(required=False, min_length=8, write_only=True)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    avatar = serializers.ImageField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'username',
            'password',
            'first_name',
            'last_name',
            'avatar',
            'description'
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        request = self.context.get('request')

        if instance.avatar:
            avatar_url = instance.avatar.url
            if request:
                representation['avatar'] = request.build_absolute_uri(avatar_url)
            else:
                representation['avatar'] = avatar_url
        else:
            representation['avatar'] = ''

        return representation

    def create(self, validated_data):
        password = validated_data.pop('password', None)

        user = User(**validated_data)

        if password:
            user.password = make_password(password)

        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.password = make_password(password)

        instance.save()
        return instance


class CustomAuthTokenSerializer(serializers.Serializer):
    email = serializers.EmailField(label=_("Email"))
    password = serializers.CharField(
        label=_("Password"),
        style={'input_type': 'password'},
        trim_whitespace=False
    )

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(
                request=self.context.get('request'),
                email=email,
                password=password
            )

            if not user:
                msg = _('No se pudo iniciar sesión con las credenciales proporcionadas.')
                raise serializers.ValidationError(msg, code='authorization')
        else:
            msg = _('Debe incluir "email" y "password".')
            raise serializers.ValidationError(msg, code='authorization')

        attrs['user'] = user
        return attrs