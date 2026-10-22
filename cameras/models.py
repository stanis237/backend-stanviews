from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

class InterconnectionDevice(models.Model):
    """
    Interconnection equipment: NVR, DVR, XVR, IP Video Encoder, or Switch/Gateway.
    Allows centralizing physical recording equipment by IP address and importing channels.
    """
    DEVICE_TYPES = [
        ('NVR', 'NVR (Enregistreur Vidéo Réseau IP)'),
        ('DVR', 'DVR (Enregistreur Numérique Hybride/Analogique)'),
        ('XVR', 'XVR (Enregistreur Multi-Standards 5-en-1)'),
        ('ENCODER', 'Encodeur Vidéo IP / Serveur Vidéo'),
        ('GATEWAY', 'Passerelle / Switch Vidéo'),
    ]

    BRAND_PROFILES = [
        ('HIKVISION', 'Hikvision / HiLook / Ezviz NVR'),
        ('DAHUA', 'Dahua / Imou / Lorex NVR'),
        ('UNIVIEW', 'Uniview (UNV) NVR'),
        ('XM_XIONGMAI', 'Xiongmai / XMeye / iCSee NVR/DVR'),
        ('GENERIC_ONVIF', 'NVR Générique ONVIF Profile S'),
        ('CUSTOM', 'Format RTSP Personnalisé'),
    ]

    STATUS_CHOICES = [
        ('ONLINE', 'En ligne / Connecté'),
        ('OFFLINE', 'Hors ligne'),
        ('ERROR', 'Erreur de communication'),
    ]

    name = models.CharField(max_length=120, verbose_name="Nom de l'équipement")
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES, default='NVR', verbose_name="Type d'appareil")
    brand_profile = models.CharField(max_length=30, choices=BRAND_PROFILES, default='HIKVISION', verbose_name="Marque / Profil")
    location = models.CharField(max_length=150, blank=True, default="", verbose_name="Emplacement / Baie de brassage")
    
    host = models.CharField(max_length=255, verbose_name="Adresse IP ou Nom d'hôte")
    rtsp_port = models.PositiveIntegerField(default=554, verbose_name="Port RTSP")
    http_port = models.PositiveIntegerField(default=80, verbose_name="Port HTTP / Gestion")
    onvif_port = models.PositiveIntegerField(default=8000, verbose_name="Port ONVIF / SDK")
    
    total_channels = models.PositiveIntegerField(default=8, verbose_name="Nombre total de voies / canaux")
    username = models.CharField(max_length=100, default="admin", verbose_name="Nom d'utilisateur")
    password = models.CharField(max_length=100, blank=True, default="", verbose_name="Mot de passe")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OFFLINE', verbose_name="Statut équipement")
    last_ping_ms = models.FloatField(default=0.0, verbose_name="Latence (ms)")
    last_status_check = models.DateTimeField(null=True, blank=True, verbose_name="Dernière vérification")
    last_error_message = models.TextField(blank=True, default="", verbose_name="Dernier message d'erreur")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Équipement d'interconnexion"
        verbose_name_plural = "Équipements d'interconnexion (NVR / DVR)"

    def __str__(self):
        return f"{self.name} ({self.get_device_type_display()}) [{self.host}]"

    def generate_channel_stream_url(self, channel_num):
        """Construct RTSP stream URL according to manufacturer brand standard."""
        auth_part = ""
        if self.username:
            auth_part = f"{self.username}:{self.password}@" if self.password else f"{self.username}@"

        brand = self.brand_profile
        if brand == 'HIKVISION':
            # Hikvision standard: rtsp://user:pass@ip:554/Streaming/Channels/101 (Ch 1 stream 1), 201 (Ch 2), etc.
            return f"rtsp://{auth_part}{self.host}:{self.rtsp_port}/Streaming/Channels/{channel_num}01"
        elif brand == 'DAHUA':
            # Dahua standard: rtsp://user:pass@ip:554/cam/realmonitor?channel=1&subtype=0
            return f"rtsp://{auth_part}{self.host}:{self.rtsp_port}/cam/realmonitor?channel={channel_num}&subtype=0"
        elif brand == 'UNIVIEW':
            # Uniview standard: rtsp://user:pass@ip:554/unicast/c1/s0/live
            return f"rtsp://{auth_part}{self.host}:{self.rtsp_port}/unicast/c{channel_num}/s0/live"
        elif brand == 'XM_XIONGMAI':
            # XMeye/Xiongmai standard: rtsp://user:pass@ip:554/channel=1&stream=0
            return f"rtsp://{auth_part}{self.host}:{self.rtsp_port}/channel={channel_num}&stream=0"
        else:
            # Generic ONVIF / standard NVR channel
            return f"rtsp://{auth_part}{self.host}:{self.rtsp_port}/ch{channel_num:02d}/main"


class Camera(models.Model):
    PROTOCOL_CHOICES = [
        ('RTSP', 'RTSP (Flux standard temps réel)'),
        ('ONVIF', 'ONVIF (Découverte et profil S/T)'),
        ('HTTP_MJPEG', 'HTTP MJPEG (Flux vidéo web continu)'),
        ('HTTP_SNAPSHOT', 'HTTP Snapshot (Images périodiques)'),
        ('SIMULATED', 'Simulateur STAN CAM (Démonstrateur / Test local)'),
    ]

    STATUS_CHOICES = [
        ('ONLINE', 'En direct / Connecté'),
        ('OFFLINE', 'Hors ligne'),
        ('ERROR', 'Erreur de flux'),
        ('TESTING', 'Vérification en cours'),
    ]

    name = models.CharField(max_length=100, verbose_name="Nom de la caméra")
    location = models.CharField(max_length=150, blank=True, default="", verbose_name="Emplacement / Zone")
    model_name = models.CharField(max_length=100, blank=True, default="V380 Pro Ampoule PTZ", verbose_name="Modèle de la caméra")
    
    protocol = models.CharField(max_length=20, choices=PROTOCOL_CHOICES, default='RTSP', verbose_name="Protocole")
    host = models.CharField(max_length=255, default="192.168.1.100", verbose_name="Adresse IP ou Nom d'hôte")
    port = models.PositiveIntegerField(default=554, verbose_name="Port réseau")
    stream_path = models.CharField(max_length=255, blank=True, default="/live/ch0", verbose_name="Chemin du flux")
    custom_url = models.CharField(max_length=500, blank=True, default="", verbose_name="URL personnalisée complète (optionnel)")

    username = models.CharField(max_length=100, blank=True, default="", verbose_name="Nom d'utilisateur")
    password = models.CharField(max_length=100, blank=True, default="", verbose_name="Mot de passe")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OFFLINE', verbose_name="Statut du flux")
    last_status_check = models.DateTimeField(null=True, blank=True, verbose_name="Dernière vérification")
    last_error_message = models.TextField(blank=True, default="", verbose_name="Dernier message d'erreur")
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name="Dernière activité reçue")

    resolution = models.CharField(max_length=30, default="1920x1080", verbose_name="Résolution")
    fps = models.PositiveIntegerField(default=15, verbose_name="Images par seconde")
    
    # PTZ & Bulb features
    ptz_supported = models.BooleanField(default=True, verbose_name="Support PTZ")
    bulb_light_supported = models.BooleanField(default=True, verbose_name="Éclairage ampoule contrôlable")
    bulb_light_status = models.BooleanField(default=False, verbose_name="État éclairage ampoule (Allumé/Éteint)")
    ptz_pan = models.IntegerField(default=0, verbose_name="Position Panoramique (-180° à +180°)")
    ptz_tilt = models.IntegerField(default=0, verbose_name="Position Inclinaison (-90° à +90°)")
    ptz_zoom = models.PositiveIntegerField(default=1, verbose_name="Niveau de zoom (1x à 10x)")

    # Interconnection equipment link (NVR/DVR channel)
    nvr_device = models.ForeignKey(InterconnectionDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name='cameras', verbose_name="Équipement NVR/DVR parent")
    nvr_channel = models.PositiveIntegerField(null=True, blank=True, verbose_name="Numéro de voie sur l'équipement")

    is_active = models.BooleanField(default=True, verbose_name="Caméra active")
    order_index = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage dans la grille")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order_index', 'id']
        verbose_name = "Caméra"
        verbose_name_plural = "Caméras"

    def __str__(self):
        return f"{self.name} [{self.protocol}] - {self.get_status_display()}"

    def get_effective_stream_url(self):
        """Construct the full sanitized or raw stream URL according to protocol."""
        if self.custom_url:
            return self.custom_url

        auth_part = ""
        if self.username:
            if self.password:
                auth_part = f"{self.username}:{self.password}@"
            else:
                auth_part = f"{self.username}@"

        path = self.stream_path
        if not path.startswith('/'):
            path = '/' + path

        if self.protocol == 'RTSP':
            return f"rtsp://{auth_part}{self.host}:{self.port}{path}"
        elif self.protocol in ['HTTP_MJPEG', 'HTTP_SNAPSHOT']:
            return f"http://{auth_part}{self.host}:{self.port}{path}"
        elif self.protocol == 'ONVIF':
            return f"http://{self.host}:{self.port}/onvif/device_service"
        else:
            return f"simulated://{self.id}"

    def mark_online(self):
        self.status = 'ONLINE'
        self.last_status_check = timezone.now()
        self.last_seen = timezone.now()
        self.last_error_message = ""
        self.save(update_fields=['status', 'last_status_check', 'last_seen', 'last_error_message', 'updated_at'])

    def mark_offline(self, error_msg=""):
        self.status = 'OFFLINE'
        self.last_status_check = timezone.now()
        if error_msg:
            self.last_error_message = error_msg
        self.save(update_fields=['status', 'last_status_check', 'last_error_message', 'updated_at'])

    def mark_error(self, error_msg):
        self.status = 'ERROR'
        self.last_status_check = timezone.now()
        self.last_error_message = error_msg
        self.save(update_fields=['status', 'last_status_check', 'last_error_message', 'updated_at'])


class CameraSettings(models.Model):
    """
    Advanced V380 Pro style camera settings:
    Network, Video quality, Dual-light bulb, AI humanoid motion alarm, PTZ presets, and SD storage.
    """
    camera = models.OneToOneField(Camera, on_delete=models.CASCADE, related_name='settings')

    # 1. Device & Network (V380 Pro format)
    device_id = models.CharField(max_length=64, default="MV58923019", verbose_name="ID Appareil / N° Série V380")
    firmware_version = models.CharField(max_length=50, default="V5.1.8_202610", verbose_name="Version Firmware")
    mac_address = models.CharField(max_length=30, default="B4:E6:2D:4A:88:12", verbose_name="Adresse MAC")
    wifi_ssid = models.CharField(max_length=100, default="STANTECH_WIFI_SURVEILLANCE", verbose_name="Nom réseau Wi-Fi")
    wifi_signal_rssi = models.IntegerField(default=85, verbose_name="Signal Wi-Fi (%)")
    network_mode = models.CharField(max_length=20, default="DHCP", choices=[('DHCP', 'DHCP Automatique'), ('STATIC', 'IP Statique')])
    ip_gateway = models.CharField(max_length=50, default="192.168.1.1", verbose_name="Passerelle")
    ip_dns = models.CharField(max_length=50, default="8.8.8.8", verbose_name="Serveur DNS")

    # 2. Video & Image Profile
    video_quality = models.CharField(max_length=10, default="HD", choices=[('HD', 'Haute Définition (1080p)'), ('SD', 'Standard (720p)')])
    video_flip_180 = models.BooleanField(default=False, verbose_name="Retourner l'image à 180° (Plafond/Ampoule)")
    brightness = models.IntegerField(default=50, verbose_name="Luminosité (0-100)")
    contrast = models.IntegerField(default=50, verbose_name="Contraste (0-100)")
    night_vision_mode = models.CharField(
        max_length=20,
        default="AUTO",
        choices=[
            ('AUTO', 'Intelligent Double Éclairage (IR + Lumière blanche sur alerte)'),
            ('COLOR', 'Plein Éclairage Couleur (Lumière blanche permanente)'),
            ('IR', 'Infrarouge N&B classique'),
            ('OFF', 'Désactivé')
        ]
    )

    # 3. Light Bulb control (V380 Pro Lamp)
    light_mode = models.CharField(
        max_length=20,
        default="AUTO",
        choices=[
            ('AUTO', 'Automatique sur détection'),
            ('MANUAL', 'Manuel (Interrupteur)'),
            ('SCHEDULE', 'Programmation horaire')
        ]
    )
    light_brightness = models.IntegerField(default=80, verbose_name="Intensité lumineuse ampoule (10-100%)")
    light_duration_seconds = models.IntegerField(default=60, verbose_name="Délai extinction après détection (sec)")
    schedule_start = models.CharField(max_length=10, default="18:30", verbose_name="Heure allumage (HH:MM)")
    schedule_end = models.CharField(max_length=10, default="06:00", verbose_name="Heure extinction (HH:MM)")

    # 4. Motion Detection & AI Alarm
    motion_detection_enabled = models.BooleanField(default=True, verbose_name="Détection de mouvement active")
    humanoid_detection = models.BooleanField(default=True, verbose_name="Filtrage IA détection humaine")
    motion_sensitivity = models.CharField(
        max_length=10,
        default="MEDIUM",
        choices=[('LOW', 'Faible'), ('MEDIUM', 'Moyenne'), ('HIGH', 'Élevée')]
    )
    alarm_sound = models.CharField(
        max_length=20,
        default="SIREN",
        choices=[
            ('NONE', 'Silencieux'),
            ('BEEP', 'Bip d\'avertissement'),
            ('VOICE_PROMPT', 'Message vocal : Zone sous surveillance'),
            ('SIREN', 'Sirène dissuasive puissante')
        ]
    )
    alarm_auto_tracking = models.BooleanField(default=False, verbose_name="Suivi automatique du mouvement (PTZ Tracking)")
    alarm_notifications = models.BooleanField(default=True, verbose_name="Envoyer des notifications d'alarme")

    # 5. PTZ Speed & Presets
    ptz_speed = models.IntegerField(default=5, verbose_name="Vitesse de déplacement PTZ (1-10)")
    preset_1_name = models.CharField(max_length=50, default="Entrée principale")
    preset_1_pan = models.IntegerField(default=0)
    preset_1_tilt = models.IntegerField(default=0)
    preset_2_name = models.CharField(max_length=50, default="Zone caisse / comptoir")
    preset_2_pan = models.IntegerField(default=45)
    preset_2_tilt = models.IntegerField(default=-15)
    preset_3_name = models.CharField(max_length=50, default="Allée centrale")
    preset_3_pan = models.IntegerField(default=-60)
    preset_3_tilt = models.IntegerField(default=10)

    # 6. SD Card Storage & Recording
    sd_card_present = models.BooleanField(default=True, verbose_name="Carte MicroSD insérée")
    sd_card_total_gb = models.FloatField(default=64.0, verbose_name="Capacité totale SD (Go)")
    sd_card_used_gb = models.FloatField(default=18.4, verbose_name="Espace utilisé (Go)")
    recording_mode = models.CharField(
        max_length=20,
        default="CONTINUOUS",
        choices=[
            ('CONTINUOUS', 'Enregistrement continu 24/7'),
            ('MOTION_ONLY', 'Sur détection de mouvement uniquement'),
            ('DISABLED', 'Désactivé')
        ]
    )
    record_audio = models.BooleanField(default=True, verbose_name="Enregistrer l'audio du microphone")
    loop_recording = models.BooleanField(default=True, verbose_name="Écrasement automatique des anciennes vidéos")

    # 7. Time & Maintenance
    ntp_server = models.CharField(max_length=100, default="pool.ntp.org", verbose_name="Serveur NTP")
    timezone_name = models.CharField(max_length=50, default="Africa/Douala (GMT+1)", verbose_name="Fuseau horaire")

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Configuration V380 Pro [{self.camera.name}]"

@receiver(post_save, sender=Camera)
def ensure_camera_settings(sender, instance, created, **kwargs):
    if not hasattr(instance, 'settings'):
        CameraSettings.objects.create(
            camera=instance,
            device_id=f"MV{58923000 + instance.id}"
        )
