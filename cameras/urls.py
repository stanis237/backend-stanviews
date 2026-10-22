from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CameraViewSet,
    InterconnectionDeviceViewSet,
    ProbeConnectionView,
    SeedDemoCamerasView,
)

router = DefaultRouter()
router.register(r'cameras', CameraViewSet, basename='camera')
router.register(r'devices', InterconnectionDeviceViewSet, basename='device')

urlpatterns = [
    path('cameras/probe/', ProbeConnectionView.as_view(), name='camera_probe'),
    path('cameras/seed-demo/', SeedDemoCamerasView.as_view(), name='camera_seed_demo'),
    path('', include(router.urls)),
]
