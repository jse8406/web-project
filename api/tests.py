from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User


class HelloWorldAPITest(APITestCase):
    def test_hello_world(self):
        """
        hello_world API 엔드포인트 테스트
        """
        response = self.client.get('/api/hello/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Hello, World!')


class UserViewSetTest(APITestCase):
    def setUp(self):
        """
        테스트용 사용자 생성
        """
        User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_user_list(self):
        """
        사용자 목록 조회 테스트
        """
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
