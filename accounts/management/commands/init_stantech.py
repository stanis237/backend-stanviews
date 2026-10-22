import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from cameras.models import Camera, InterconnectionDevice
from diagnostics.models import DiagnosticLog

class Command(BaseCommand):
    help = "Initialize default STANTECH admin account and sample PTZ bulb cameras"

    def handle(self, *args, **options):
        # 1. Create or get Admin user
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'contact@stantech.cm',
                'is_staff': True,
                'is_superuser': True,
                'first_name': 'Superviseur',
                'last_name': 'STANTECH'
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            admin_user.profile.role = 'ADMIN'
            admin_user.profile.phone = '+237 600 000 000'
            admin_user.profile.save()
            self.stdout.write(self.style.SUCCESS("Compte Administrateur 'admin' créé avec succès (mdp: admin123)."))
        else:
            self.stdout.write("Compte Administrateur 'admin' déjà existant.")

        # 2. Seed initial cameras (1 to 8)
        now = timezone.now()
        sample_cameras = [
            {
                'name': 'Entrée Magasin - Ampoule PTZ E27',
                'location': 'Hall d\'entrée',
                'model_name': 'V380 Pro PTZ Bulb',
                'protocol': 'SIMULATED',
                'host': '192.168.1.101',
                'port': 554,
                'stream_path': '/live/ch0',
                'status': 'ONLINE',
                'ptz_supported': True,
                'bulb_light_supported': True,
                'bulb_light_status': True,
                'order_index': 1,
            },
            {
                'name': 'Caisse Principale',
                'location': 'Zone Comptoir',
                'model_name': 'iCSee Smart 360',
                'protocol': 'SIMULATED',
                'host': '192.168.1.102',
                'port': 554,
                'stream_path': '/stream1',
                'status': 'ONLINE',
                'ptz_supported': True,
                'bulb_light_supported': True,
                'bulb_light_status': False,
                'order_index': 2,
            },
            {
                'name': 'Rayon High-Tech',
                'location': 'Allée Centrale',
                'model_name': 'Tuya Panoramic Bulb',
                'protocol': 'SIMULATED',
                'host': '192.168.1.103',
                'port': 554,
                'stream_path': '/live/ch1',
                'status': 'ONLINE',
                'ptz_supported': True,
                'bulb_light_supported': True,
                'bulb_light_status': True,
                'order_index': 3,
            },
            {
                'name': 'Stock & Réserve',
                'location': 'Sous-sol Sécurisé',
                'model_name': 'YCC365 Light Cam',
                'protocol': 'SIMULATED',
                'host': '192.168.1.104',
                'port': 554,
                'stream_path': '/onvif1',
                'status': 'ONLINE',
                'ptz_supported': True,
                'bulb_light_supported': False,
                'bulb_light_status': False,
                'order_index': 4,
            },
            {
                'name': 'Parking & Allée Clients',
                'location': 'Extérieur Façade',
                'model_name': 'PTZ Outdoor Wi-Fi Bulb',
                'protocol': 'SIMULATED',
                'host': '192.168.1.105',
                'port': 554,
                'stream_path': '/live/ch0',
                'status': 'ONLINE',
                'ptz_supported': True,
                'bulb_light_supported': True,
                'bulb_light_status': False,
                'order_index': 5,
            },
            {
                'name': 'Quai de Livraison',
                'location': 'Accès Logistique',
                'model_name': 'ONVIF Dome HD',
                'protocol': 'SIMULATED',
                'host': '192.168.1.106',
                'port': 8899,
                'stream_path': '/media/stream',
                'status': 'ONLINE',
                'ptz_supported': True,
                'bulb_light_supported': False,
                'bulb_light_status': False,
                'order_index': 6,
            },
            {
                'name': 'Bureau Direction',
                'location': 'Étage 1',
                'model_name': 'Ampoule Wi-Fi 1080p',
                'protocol': 'SIMULATED',
                'host': '192.168.1.107',
                'port': 554,
                'stream_path': '/live/ch0',
                'status': 'ONLINE',
                'ptz_supported': True,
                'bulb_light_supported': True,
                'bulb_light_status': True,
                'order_index': 7,
            },
            {
                'name': 'Périmètre Arrière',
                'location': 'Zone Grillage Ouest',
                'model_name': 'Ampoule PTZ 360',
                'protocol': 'SIMULATED',
                'host': '192.168.1.108',
                'port': 554,
                'stream_path': '/live/ch0',
                'status': 'OFFLINE',
                'last_error_message': 'Caméra éteinte ou signal Wi-Fi insuffisant',
                'ptz_supported': True,
                'bulb_light_supported': True,
                'bulb_light_status': False,
                'order_index': 8,
            },
        ]

        count = 0
        for data in sample_cameras:
            c, created = Camera.objects.get_or_create(
                name=data['name'],
                defaults={
                    **data,
                    'last_status_check': now,
                    'last_seen': now if data['status'] == 'ONLINE' else None,
                }
            )
            if created:
                count += 1

        self.stdout.write(self.style.SUCCESS(f"{count} caméras initiales enregistrées pour STAN CAM VIEW."))

        # 3. Seed sample NVR Interconnection Device
        nvr, nvr_created = InterconnectionDevice.objects.get_or_create(
            name='NVR Hikvision 8 Voies - Entrepôt Principal',
            defaults={
                'device_type': 'NVR',
                'brand_profile': 'HIKVISION',
                'location': 'Baie de Brassage Serveur',
                'host': '192.168.1.200',
                'rtsp_port': 554,
                'http_port': 80,
                'onvif_port': 8000,
                'total_channels': 8,
                'username': 'admin',
                'status': 'ONLINE',
                'last_ping_ms': 12.4,
                'last_status_check': now,
            }
        )
        if nvr_created:
            self.stdout.write(self.style.SUCCESS("Équipement NVR de référence interconnecté (IP: 192.168.1.200)."))

        # 4. Add initial log
        DiagnosticLog.objects.create(
            level='INFO',
            category='SYSTEM',
            message='Initialisation STAN CAM VIEW réussie.',
            details='Système configuré avec 8 caméras et 1 NVR interconnecté par IP.'
        )
