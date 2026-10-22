from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DiagnosticLogViewSet, SystemHealthView

router = DefaultRouter()
router.register(r'logs', DiagnosticLogViewSet, basename='diagnostic_log')

urlpatterns = [
    path('health/', SystemHealthView.as_view(), name='system_health'),
    path('', include(router.urls)),
]
