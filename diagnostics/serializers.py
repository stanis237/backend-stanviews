from rest_framework import serializers
from .models import DiagnosticLog

class DiagnosticLogSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source='camera.name', read_only=True)

    class Meta:
        model = DiagnosticLog
        fields = ['id', 'timestamp', 'level', 'category', 'camera', 'camera_name', 'message', 'details']
