from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

class AuthFunctionalTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testoperator',
            password='Password123!',
            email='operator@stantech.cm'
        )

    def test_login_successful_generates_jwt(self):
        """F-01: Authentification avec identifiants valides."""
        response = self.client.post('/api/auth/login/', {
            'username': 'testoperator',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['username'], 'testoperator')

    def test_login_failed_invalid_credentials(self):
        """F-01: Rejet en cas de mot de passe erroné."""
        response = self.client.post('/api/auth/login/', {
            'username': 'testoperator',
            'password': 'WrongPassword'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_protected_endpoint_denies_unauthenticated_access(self):
        """T-02: Accès sans authentification refusé sur les pages protégées."""
        response = self.client.get('/api/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
