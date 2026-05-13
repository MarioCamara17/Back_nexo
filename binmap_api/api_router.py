# -*- coding: utf-8 -*-
from rest_framework.routers import DefaultRouter

from places.views import (
    StateViewSet,
    MunicipalityViewSet,
    CategoryViewSet,
    PlaceViewSet,
    FavoriteViewSet,
    VisitedPlaceViewSet
)

from routes.views import (
    RouteViewSet,
    MunicipalityHasRouteViewSet,
    CustomRouteViewSet
)

router = DefaultRouter()

router.register(r'states', StateViewSet)
router.register(r'municipalities', MunicipalityViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'places', PlaceViewSet)
router.register(r'favorites', FavoriteViewSet, basename='favorites')
router.register(r'visited-places', VisitedPlaceViewSet, basename='visited-places')

router.register(r'routes', RouteViewSet)
router.register(r'municipality-routes', MunicipalityHasRouteViewSet)
router.register(r'custom-routes', CustomRouteViewSet, basename='custom-routes')