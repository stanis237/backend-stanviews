from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from .models import Camera

class CameraFunctionalTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='adminuser',
            password='Password123!',
            is_staff=True
        )
        self.client.force_authenticate(user=self.user)

        self.camera = Camera.objects.create(
            name='Caméra Ampoule Entrée',
            location='Hall A',
            protocol='SIMULATED',
            host='192.168.1.50',
            port=554,
            ptz_supported=True,
            bulb_light_supported=True,
            bulb_light_status=False
        )

    def test_add_camera_f02(self):
        """F-02: Ajouter une caméra avec paramètres requis."""
        payload = {
            'name': 'Caméra Caisse 2',
            'location': 'Comptoir',
            'protocol': 'RTSP',
            'host': '192.168.1.120',
            'port': 554,
            'stream_path': '/live/ch0',
            'username': 'admin',
            'password': 'camerapassword',
            'ptz_supported': True,
            'bulb_light_supported': True,
        }
        response = self.client.post('/api/cameras/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Caméra Caisse 2')
        # Verify password is NOT exposed in plain text in response
        self.assertNotIn('camerapassword', str(response.data))
        self.assertTrue(response.data['has_password'])

    def test_probe_stream_f03(self):
        """F-03: Tester le flux (joignabilité ou message clair)."""
        response = self.client.post('/api/cameras/probe/', {
            'host': '127.0.0.1',
            'port': 554,
            'protocol': 'SIMULATED'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

    def test_camera_connection_action(self):
        """T-03: Action de test de connexion sur caméra enregistrée."""
        response = self.client.post(f'/api/cameras/{self.camera.id}/test/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.camera.refresh_from_db()
        self.assertEqual(self.camera.status, 'ONLINE')

    def test_modify_and_delete_camera_f08(self):
        """F-08: Modifier et supprimer une caméra."""
        # Update
        patch_res = self.client.patch(f'/api/cameras/{self.camera.id}/', {
            'name': 'Ampoule Entrée Renommée',
            'location': 'Hall Rénové'
        })
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['name'], 'Ampoule Entrée Renommée')

        # Delete
        del_res = self.client.delete(f'/api/cameras/{self.camera.id}/')
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Camera.objects.filter(id=self.camera.id).exists())

    def test_ptz_controls_and_bulb_light_f09(self):
        """F-09: Commandes PTZ et bascule d'éclairage ampoule."""
        # Pan Left
        move_res = self.client.post(f'/api/cameras/{self.camera.id}/ptz/', {
            'action': 'move',
            'direction': 'left',
            'step': 15
        })
        self.assertEqual(move_res.status_code, status.HTTP_200_OK)
        self.camera.refresh_from_db()
        self.assertEqual(self.camera.ptz_pan, -15)

        # Light Toggle (Ampoule)
        light_res = self.client.post(f'/api/cameras/{self.camera.id}/ptz/', {
            'action': 'light',
            'state': 'toggle'
        })
        self.assertEqual(light_res.status_code, status.HTTP_200_OK)
        self.camera.refresh_from_db()
        self.assertTrue(self.camera.bulb_light_status)

    def test_snapshot_stream_rendering(self):
        """T-04: Rendu de l'image de surveillance JPEG."""
        response = self.client.get(f'/api/cameras/{self.camera.id}/snapshot/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertGreater(len(response.content), 500)
