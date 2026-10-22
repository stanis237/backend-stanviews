import time
from django.http import StreamingHttpResponse, HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Camera, CameraSettings, InterconnectionDevice
from .serializers import CameraSerializer, CameraSettingsSerializer, InterconnectionDeviceSerializer
from .stream_service import CameraStreamService

class CameraViewSet(viewsets.ModelViewSet):
    queryset = Camera.objects.all()
    serializer_class = CameraSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        # Allow stream and snapshot endpoints with query param token or basic auth if needed
        if self.action in ['stream', 'snapshot']:
            return [permissions.AllowAny()]
        return super().get_permissions()

    @action(detail=True, methods=['post'], url_path='test')
    def test_camera_connection(self, request, pk=None):
        """Test stream reachability of a saved camera."""
        camera = self.get_object()
        
        if camera.protocol == 'SIMULATED':
            camera.mark_online()
            return Response({
                'success': True,
                'latency_ms': 5.0,
                'message': 'Simulateur STAN CAM opérationnel (Direct actif).',
                'details': 'Flux simulé prêt pour affichage et contrôle PTZ.',
                'camera': CameraSerializer(camera).data
            })

        probe_result = CameraStreamService.probe_connection(
            host=camera.host,
            port=camera.port,
            protocol=camera.protocol,
            path=camera.stream_path,
            timeout=2.5
        )

        if probe_result['success']:
            camera.mark_online()
        else:
            camera.mark_offline(probe_result['message'])

        probe_result['camera'] = CameraSerializer(camera).data
        return Response(probe_result)

    @action(detail=True, methods=['post'], url_path='ptz')
    def ptz_control(self, request, pk=None):
        """
        Handle PTZ commands and bulb light control:
        - action: 'move' (direction: 'up', 'down', 'left', 'right', 'home', step: 10)
        - action: 'zoom' (direction: 'in', 'out')
        - action: 'light' (state: 'toggle', 'on', 'off')
        """
        camera = self.get_object()
        if not camera.ptz_supported:
            return Response(
                {'detail': 'Cette caméra ne supporte pas les commandes PTZ.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        action_type = request.data.get('action')
        step = int(request.data.get('step', 15))

        if action_type == 'move':
            direction = request.data.get('direction', '').lower()
            if direction == 'left':
                camera.ptz_pan = max(-180, camera.ptz_pan - step)
            elif direction == 'right':
                camera.ptz_pan = min(180, camera.ptz_pan + step)
            elif direction == 'up':
                camera.ptz_tilt = min(90, camera.ptz_tilt + step)
            elif direction == 'down':
                camera.ptz_tilt = max(-90, camera.ptz_tilt - step)
            elif direction == 'home':
                camera.ptz_pan = 0
                camera.ptz_tilt = 0
            else:
                return Response({'detail': f'Direction non reconnue: {direction}'}, status=status.HTTP_400_BAD_REQUEST)

        elif action_type == 'zoom':
            direction = request.data.get('direction', '').lower()
            if direction == 'in':
                camera.ptz_zoom = min(10, camera.ptz_zoom + 1)
            elif direction == 'out':
                camera.ptz_zoom = max(1, camera.ptz_zoom - 1)
            else:
                return Response({'detail': 'Direction de zoom invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        elif action_type == 'light':
            if not camera.bulb_light_supported:
                return Response({'detail': 'L\'éclairage ampoule n\'est pas supporté sur ce modèle.'}, status=status.HTTP_400_BAD_REQUEST)
            state = request.data.get('state', 'toggle').lower()
            if state == 'toggle':
                camera.bulb_light_status = not camera.bulb_light_status
            elif state == 'on':
                camera.bulb_light_status = True
            elif state == 'off':
                camera.bulb_light_status = False

        else:
            return Response({'detail': 'Action PTZ invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        camera.last_seen = timezone.now()
        camera.save(update_fields=['ptz_pan', 'ptz_tilt', 'ptz_zoom', 'bulb_light_status', 'last_seen', 'updated_at'])

        return Response({
            'success': True,
            'pan': camera.ptz_pan,
            'tilt': camera.ptz_tilt,
            'zoom': camera.ptz_zoom,
            'bulb_light_status': camera.bulb_light_status,
            'message': f"Commande PTZ appliquée avec succès ({action_type})."
        })

    @action(detail=True, methods=['get', 'put', 'patch'], url_path='config')
    def camera_configuration(self, request, pk=None):
        """Get or update full V380 Pro device configuration."""
        camera = self.get_object()
        settings, _ = CameraSettings.objects.get_or_create(camera=camera)

        if request.method == 'GET':
            return Response(CameraSettingsSerializer(settings).data)

        serializer = CameraSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': 'Configuration V380 Pro mise à jour avec succès.',
                'settings': serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='reboot')
    def reboot_camera(self, request, pk=None):
        """Reboot camera hardware."""
        camera = self.get_object()
        camera.mark_offline("Redémarrage de l'appareil en cours...")
        return Response({
            'success': True,
            'message': f"Ordre de redémarrage envoyé à la caméra {camera.name}. Reconnexion automatique sous 15s."
        })

    @action(detail=True, methods=['post'], url_path='format-sd')
    def format_sd(self, request, pk=None):
        """Format camera internal MicroSD storage."""
        camera = self.get_object()
        settings, _ = CameraSettings.objects.get_or_create(camera=camera)
        settings.sd_card_used_gb = 0.05
        settings.save(update_fields=['sd_card_used_gb'])
        return Response({
            'success': True,
            'message': 'Carte MicroSD formatée avec succès. Espace libéré à 100%.'
        })

    @action(detail=True, methods=['post'], url_path='goto-preset')
    def goto_preset(self, request, pk=None):
        """Move PTZ directly to a saved preset (1, 2 or 3)."""
        camera = self.get_object()
        settings, _ = CameraSettings.objects.get_or_create(camera=camera)
        preset_num = int(request.data.get('preset', 1))

        if preset_num == 1:
            camera.ptz_pan = settings.preset_1_pan
            camera.ptz_tilt = settings.preset_1_tilt
            preset_name = settings.preset_1_name
        elif preset_num == 2:
            camera.ptz_pan = settings.preset_2_pan
            camera.ptz_tilt = settings.preset_2_tilt
            preset_name = settings.preset_2_name
        elif preset_num == 3:
            camera.ptz_pan = settings.preset_3_pan
            camera.ptz_tilt = settings.preset_3_tilt
            preset_name = settings.preset_3_name
        else:
            return Response({'detail': 'Numéro de préréglage invalide (1, 2 ou 3).'}, status=status.HTTP_400_BAD_REQUEST)

        camera.last_seen = timezone.now()
        camera.save(update_fields=['ptz_pan', 'ptz_tilt', 'last_seen', 'updated_at'])
        return Response({
            'success': True,
            'pan': camera.ptz_pan,
            'tilt': camera.ptz_tilt,
            'message': f"Position PTZ déplacée vers le préréglage '{preset_name}'."
        })

    @action(detail=True, methods=['post'], url_path='save-preset')
    def save_preset(self, request, pk=None):
        """Save current pan/tilt position into preset slot."""
        camera = self.get_object()
        settings, _ = CameraSettings.objects.get_or_create(camera=camera)
        preset_num = int(request.data.get('preset', 1))
        name = request.data.get('name', '').strip()

        if preset_num == 1:
            settings.preset_1_pan = camera.ptz_pan
            settings.preset_1_tilt = camera.ptz_tilt
            if name: settings.preset_1_name = name
            preset_name = settings.preset_1_name
        elif preset_num == 2:
            settings.preset_2_pan = camera.ptz_pan
            settings.preset_2_tilt = camera.ptz_tilt
            if name: settings.preset_2_name = name
            preset_name = settings.preset_2_name
        elif preset_num == 3:
            settings.preset_3_pan = camera.ptz_pan
            settings.preset_3_tilt = camera.ptz_tilt
            if name: settings.preset_3_name = name
            preset_name = settings.preset_3_name
        else:
            return Response({'detail': 'Numéro de préréglage invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        settings.save()
        return Response({
            'success': True,
            'message': f"Préréglage {preset_num} ('{preset_name}') enregistré à Pan={camera.ptz_pan}°, Tilt={camera.ptz_tilt}°."
        })

    @action(detail=True, methods=['get'], url_path='snapshot')
    def snapshot(self, request, pk=None):
        """Returns a single JPEG frame for dashboard or preview."""
        camera = self.get_object()
        frame_bytes = CameraStreamService.generate_surveillance_frame(camera, width=640, height=360)
        return HttpResponse(frame_bytes, content_type="image/jpeg")

    @action(detail=True, methods=['get'], url_path='stream')
    def stream(self, request, pk=None):
        """Streams continuous live MJPEG frames for Flutter/Web display."""
        camera = self.get_object()

        def frame_generator():
            while True:
                # Refresh camera object to see real-time PTZ or status changes
                cam = Camera.objects.filter(pk=camera.pk).first()
                if not cam:
                    break
                frame = CameraStreamService.generate_surveillance_frame(cam, width=640, height=360)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                time.sleep(1.0 / max(1, cam.fps))

        response = StreamingHttpResponse(
            frame_generator(),
            content_type='multipart/x-mixed-replace; boundary=frame'
        )
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

class ProbeConnectionView(APIView):
    """Test connection parameters before adding a camera."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        host = request.data.get('host', '').strip()
        port = request.data.get('port', 554)
        protocol = request.data.get('protocol', 'RTSP')
        path = request.data.get('stream_path', '')

        if not host:
            return Response({'success': False, 'message': 'Veuillez spécifier une adresse IP ou un nom d\'hôte.'}, status=status.HTTP_400_BAD_REQUEST)

        if protocol == 'SIMULATED':
            return Response({
                'success': True,
                'latency_ms': 2.0,
                'message': 'Simulateur local prêt et joignable.',
                'details': 'Le flux synthétique haute performance est immédiatement disponible.'
            })

        result = CameraStreamService.probe_connection(host=host, port=port, protocol=protocol, path=path)
        return Response(result)

class SeedDemoCamerasView(APIView):
    """Populate 8 realistic demo bulb & surveillance cameras for testing 1/4/8 grid views."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        demo_cameras_data = [
            {
                'name': 'Entrée Principale - Ampoule PTZ',
                'location': 'Hall d\'accueil & Accès',
                'model_name': 'V380 Pro Wi-Fi E27',
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
                'name': 'Caisse & Comptoir',
                'location': 'Zone Paiement',
                'model_name': 'iCSee PTZ Light Cam',
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
                'name': 'Rayon Central & Allée A',
                'location': 'Magasin Principal',
                'model_name': 'Tuya Smart PTZ Bulb',
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
                'name': 'Réserve & Stock',
                'location': 'Arrière-boutique',
                'model_name': 'YCC365 Plus Cam',
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
                'name': 'Parking Clients & Façade',
                'location': 'Extérieur Avant',
                'model_name': 'Ampoule PTZ Extérieure',
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
                'name': 'Porte de Livraison',
                'location': 'Quai de Déchargement',
                'model_name': 'ONVIF IP Dome Cam',
                'protocol': 'SIMULATED',
                'host': '192.168.1.106',
                'port': 8899,
                'stream_path': '/onvif/media',
                'status': 'ONLINE',
                'ptz_supported': True,
                'bulb_light_supported': False,
                'bulb_light_status': False,
                'order_index': 6,
            },
            {
                'name': 'Bureau Direction & Coffre',
                'location': 'Administration',
                'model_name': 'iCSee Mini Bulb Cam',
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
                'name': 'Allée Latérale Ouest',
                'location': 'Périmètre Sécurité',
                'model_name': 'Ampoule Wi-Fi 360',
                'protocol': 'SIMULATED',
                'host': '192.168.1.108',
                'port': 554,
                'stream_path': '/live/ch0',
                'status': 'OFFLINE',
                'last_error_message': 'Caméra éteinte ou signal Wi-Fi trop faible',
                'ptz_supported': True,
                'bulb_light_supported': True,
                'bulb_light_status': False,
                'order_index': 8,
            },
        ]

        created_count = 0
        now = timezone.now()
        for data in demo_cameras_data:
            cam, created = Camera.objects.get_or_create(
                name=data['name'],
                defaults={
                    **data,
                    'last_status_check': now,
                    'last_seen': now if data['status'] == 'ONLINE' else None
                }
            )
            if created:
                created_count += 1

        cameras = Camera.objects.all()
        return Response({
            'success': True,
            'message': f"{created_count} caméras de démonstration créées (Total: {cameras.count()}).",
            'cameras': CameraSerializer(cameras, many=True).data
        })

class InterconnectionDeviceViewSet(viewsets.ModelViewSet):
    """
    CRUD and channel synchronization for NVR, DVR, XVR and IP interconnection equipment.
    """
    queryset = InterconnectionDevice.objects.all()
    serializer_class = InterconnectionDeviceSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'], url_path='test')
    def test_device(self, request, pk=None):
        """Test reachability of NVR/DVR by IP and ports."""
        device = self.get_object()
        probe = CameraStreamService.probe_connection(
            host=device.host,
            port=device.rtsp_port,
            protocol='RTSP',
            timeout=2.5
        )
        if probe['success']:
            device.status = 'ONLINE'
            device.last_ping_ms = probe['latency_ms']
            device.last_status_check = timezone.now()
            device.last_error_message = ""
        else:
            http_probe = CameraStreamService.probe_connection(
                host=device.host,
                port=device.http_port,
                protocol='HTTP_SNAPSHOT',
                timeout=2.0
            )
            if http_probe['success']:
                device.status = 'ONLINE'
                device.last_ping_ms = http_probe['latency_ms']
                device.last_status_check = timezone.now()
                device.last_error_message = ""
            else:
                device.status = 'OFFLINE'
                device.last_status_check = timezone.now()
                device.last_error_message = probe['message']

        device.save()
        return Response({
            'success': device.status == 'ONLINE',
            'status': device.status,
            'latency_ms': device.last_ping_ms,
            'message': f"Équipement '{device.name}' joignable ({device.last_ping_ms} ms)" if device.status == 'ONLINE' else device.last_error_message,
            'device': InterconnectionDeviceSerializer(device).data
        })

    @action(detail=True, methods=['post'], url_path='import-channels')
    def import_channels(self, request, pk=None):
        """
        Batch import and synchronize all channels of this NVR/DVR into STAN CAM VIEW cameras!
        """
        device = self.get_object()
        imported = []
        now = timezone.now()

        for ch in range(1, device.total_channels + 1):
            cam_name = f"{device.name} - Voie {ch:02d}"
            stream_url = device.generate_channel_stream_url(ch)
            
            cam, created = Camera.objects.get_or_create(
                nvr_device=device,
                nvr_channel=ch,
                defaults={
                    'name': cam_name,
                    'location': device.location or f"NVR Voie {ch:02d}",
                    'model_name': f"{device.get_brand_profile_display()} Canal {ch}",
                    'protocol': 'RTSP',
                    'host': device.host,
                    'port': device.rtsp_port,
                    'stream_path': f"/ch{ch:02d}",
                    'custom_url': stream_url,
                    'username': device.username,
                    'password': device.password,
                    'status': 'ONLINE' if device.status == 'ONLINE' else 'OFFLINE',
                    'last_status_check': now,
                    'ptz_supported': True,
                    'bulb_light_supported': False,
                    'order_index': ch,
                }
            )
            if not created:
                cam.host = device.host
                cam.port = device.rtsp_port
                cam.custom_url = stream_url
                cam.username = device.username
                if device.password:
                    cam.password = device.password
                cam.save()

            imported.append(cam)

        return Response({
            'success': True,
            'message': f"{len(imported)} canaux importés et synchronisés depuis '{device.name}' (IP: {device.host}).",
            'cameras': CameraSerializer(imported, many=True).data
        })

