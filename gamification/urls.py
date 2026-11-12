# -*- coding: utf-8 -*-
from django.urls import path
from .views import GamificationProfileView, AwardPointsView


urlpatterns = [
    path('profile/', GamificationProfileView.as_view(), name='gamification-profile'),
    path('award/', AwardPointsView.as_view(), name='gamification-award'),
]
from .station_views import StationListView, StationNearbyView, StationCheckinView

urlpatterns += [
    path('stations/', StationListView.as_view(), name='train-stations'),
    path('stations/<slug:slug>/nearby/', StationNearbyView.as_view(), name='station-nearby'),
    path('stations/<slug:slug>/visit/', StationCheckinView.as_view(), name='station-visit'),
]
