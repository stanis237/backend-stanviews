from rest_framework import serializers
from .models import Camera, CameraSettings, InterconnectionDevice

class InterconnectionDeviceSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_password = serializers.SerializerMethodField()
    cameras_count = serializers.SerializerMethodField()
    device_type_display = serializers.CharField(source='get_device_type_display', read_only=True)
    brand_profile_display = serializers.CharField(source='get_brand_profile_display', read_only=True)

    class Meta:
        model = InterconnectionDevice
        fields = [
            'id',
            'name',
            'device_type',
            'device_type_display',
            'brand_profile',
            'brand_profile_display',
            'location',
            'host',
            'rtsp_port',
            'http_port',
            'onvif_port',
            'total_channels',
            'username',
            'password',
            'has_password',
            'status',
            'last_ping_ms',
            'last_status_check',
            'last_error_message',
            'cameras_count',
            'created_at',
            'updated_at',
        ]

    def get_has_password(self, obj):
        return bool(obj.password)

    def get_cameras_count(self, obj):
        return obj.cameras.count()

    def create(self, validated_data):
        password = validated_data.pop('password', '')
        device = InterconnectionDevice(**validated_data)
        if password:
            device.password = password
        device.save()
        return device

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password is not None and password != '':
            instance.password = password
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class CameraSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CameraSettings
        fields = [
            'id',
            'device_id',
            'firmware_version',
            'mac_address',
            'wifi_ssid',
            'wifi_signal_rssi',
            'network_mode',
            'ip_gateway',
            'ip_dns',
            'video_quality',
            'video_flip_180',
            'brightness',
            'contrast',
            'night_vision_mode',
            'light_mode',
            'light_brightness',
            'light_duration_seconds',
            'schedule_start',
            'schedule_end',
            'motion_detection_enabled',
            'humanoid_detection',
            'motion_sensitivity',
            'alarm_sound',
            'alarm_auto_tracking',
            'alarm_notifications',
            'ptz_speed',
            'preset_1_name',
            'preset_1_pan',
            'preset_1_tilt',
            'preset_2_name',
            'preset_2_pan',
            'preset_2_tilt',
            'preset_3_name',
            'preset_3_pan',
            'preset_3_tilt',
            'sd_card_present',
            'sd_card_total_gb',
            'sd_card_used_gb',
            'recording_mode',
            'record_audio',
            'loop_recording',
            'ntp_server',
            'timezone_name',
            'updated_at',
        ]

class CameraSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_password = serializers.SerializerMethodField()
    effective_stream_url = serializers.SerializerMethodField()
    settings = CameraSettingsSerializer(read_only=True)
    nvr_device_name = serializers.CharField(source='nvr_device.name', read_only=True)

    class Meta:
        model = Camera
        fields = [
            'id',
            'name',
            'location',
            'model_name',
            'protocol',
            'host',
            'port',
            'stream_path',
            'custom_url',
            'username',
            'password',
            'has_password',
            'status',
            'last_status_check',
            'last_error_message',
            'last_seen',
            'resolution',
            'fps',
            'ptz_supported',
            'bulb_light_supported',
            'bulb_light_status',
            'ptz_pan',
            'ptz_tilt',
            'ptz_zoom',
            'nvr_device',
            'nvr_device_name',
            'nvr_channel',
            'is_active',
            'order_index',
            'effective_stream_url',
            'settings',
            'created_at',
            'updated_at',
        ]

    def get_has_password(self, obj):
        return bool(obj.password)

    def get_effective_stream_url(self, obj):
        url = obj.get_effective_stream_url()
        if obj.password and obj.password in url:
            url = url.replace(obj.password, '******')
        return url

    def create(self, validated_data):
        password = validated_data.pop('password', '')
        camera = Camera(**validated_data)
        if password:
            camera.password = password
        camera.save()
        return camera

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password is not None and password != '':
            instance.password = password
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
