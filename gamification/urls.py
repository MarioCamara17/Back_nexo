# -*- coding: utf-8 -*-
from django.urls import path
from .views import GamificationProfileView, AwardPointsView


urlpatterns = [
    path('profile/', GamificationProfileView.as_view(), name='gamification-profile'),
    path('award/', AwardPointsView.as_view(), name='gamification-award'),
]