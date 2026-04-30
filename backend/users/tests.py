from datetime import timedelta
from unittest.mock import patch
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User, UserInvitation


class RegistrationTest(APITestCase):
    def test_register_success(self):
        data = {
            'email': 'new@example.com',
            'username': 'newuser',
            'password': 'securepass123',
            'first_name': 'New',
            'last_name': 'User',
        }
        response = self.client.post('/api/auth/register/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['email'], 'new@example.com')
        self.assertTrue(User.objects.filter(email='new@example.com').exists())

    def test_register_duplicate_email(self):
        User.objects.create_user(
            email='dup@example.com', username='dup', password='pass123456',
        )
        data = {
            'email': 'dup@example.com',
            'username': 'dup2',
            'password': 'securepass123',
            'first_name': 'Dup',
            'last_name': 'User',
        }
        response = self.client.post('/api/auth/register/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_short_password(self):
        data = {
            'email': 'short@example.com',
            'username': 'shortpw',
            'password': '12345',
            'first_name': 'Short',
            'last_name': 'Pass',
        }
        response = self.client.post('/api/auth/register/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_defaults_to_cashier(self):
        data = {
            'email': 'cashier@example.com',
            'username': 'cashier',
            'password': 'securepass123',
            'first_name': 'Default',
            'last_name': 'Role',
        }
        response = self.client.post('/api/auth/register/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['role'], 'cashier')


class LoginTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='login@example.com', username='loginuser', password='testpass123',
        )

    def test_login_success(self):
        response = self.client.post('/api/auth/login/', {
            'email': 'login@example.com', 'password': 'testpass123',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_wrong_password(self):
        response = self.client.post('/api/auth/login/', {
            'email': 'login@example.com', 'password': 'wrongpass',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CurrentUserTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='me@example.com', username='meuser', password='testpass123',
            first_name='Me', last_name='User', role='admin',
        )

    def test_me_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'me@example.com')

    def test_me_unauthenticated(self):
        response = self.client.get('/api/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserCRUDPermissionsTest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', username='admin', password='pass123456',
            role='admin',
        )
        self.manager = User.objects.create_user(
            email='manager@example.com', username='manager', password='pass123456',
            role='manager',
        )
        self.cashier = User.objects.create_user(
            email='cashier@example.com', username='cashier', password='pass123456',
            role='cashier',
        )

    def test_list_users_authenticated(self):
        self.client.force_authenticate(user=self.cashier)
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_users_unauthenticated(self):
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_create_user(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/users/', {
            'email': 'new@example.com', 'username': 'newuser',
            'password': 'pass123456', 'first_name': 'New', 'last_name': 'User',
            'role': 'attendant',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_manager_can_create_user(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post('/api/users/', {
            'email': 'new2@example.com', 'username': 'newuser2',
            'password': 'pass123456', 'first_name': 'New', 'last_name': 'User2',
            'role': 'cashier',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cashier_cannot_create_user(self):
        self.client.force_authenticate(user=self.cashier)
        response = self.client.post('/api/users/', {
            'email': 'nope@example.com', 'username': 'nope',
            'password': 'pass123456', 'first_name': 'No', 'last_name': 'Way',
            'role': 'cashier',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cashier_cannot_update_user(self):
        self.client.force_authenticate(user=self.cashier)
        response = self.client.patch(
            f'/api/users/{self.manager.pk}/',
            {'first_name': 'Hacked'}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ActivateDeactivateTest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', username='admin', password='pass123456',
            role='admin',
        )
        self.target = User.objects.create_user(
            email='target@example.com', username='target', password='pass123456',
            role='cashier',
        )
        self.manager = User.objects.create_user(
            email='manager@example.com', username='manager', password='pass123456',
            role='manager',
        )

    def test_admin_can_deactivate(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/users/{self.target.pk}/deactivate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

    def test_admin_can_activate(self):
        self.target.is_active = False
        self.target.save()
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/users/{self.target.pk}/activate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)

    def test_admin_cannot_deactivate_self(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/users/{self.admin.pk}/deactivate/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manager_cannot_deactivate(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(f'/api/users/{self.target.pk}/deactivate/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cashier_cannot_deactivate(self):
        cashier = User.objects.create_user(
            email='cashier2@example.com', username='cashier2', password='pass123456',
            role='cashier',
        )
        self.client.force_authenticate(user=cashier)
        response = self.client.post(f'/api/users/{self.target.pk}/deactivate/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CurrentUserPermissionsTest(APITestCase):
    """Tests for the /api/auth/me/permissions/ endpoint."""

    def _make_user(self, role):
        return User.objects.create_user(
            email=f'{role}@test.com', username=role,
            password='testpass123', role=role,
        )

    def test_requires_authentication(self):
        response = self.client.get('/api/auth/me/permissions/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_gets_all_sections(self):
        user = self._make_user('admin')
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/auth/me/permissions/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['role'], 'admin')
        self.assertIn('settings', data['sections'])
        self.assertIn('accounting', data['sections'])
        self.assertIn('manage_system_config', data['actions'])
        self.assertIn('manage_audit_settings', data['actions'])

    def test_manager_cannot_access_settings(self):
        user = self._make_user('manager')
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/auth/me/permissions/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertNotIn('settings', data['sections'])
        self.assertNotIn('manage_audit_settings', data['actions'])
        self.assertIn('manage_outlets', data['actions'])

    def test_cashier_minimal_access(self):
        user = self._make_user('cashier')
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/auth/me/permissions/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['role'], 'cashier')
        self.assertIn('pos', data['sections'])
        self.assertIn('shifts', data['sections'])
        self.assertIn('open_shift', data['actions'])
        self.assertNotIn('accounting', data['sections'])
        self.assertNotIn('outlets', data['sections'])
        self.assertNotIn('manage_outlets', data['actions'])

    def test_accountant_sees_finance_not_pos(self):
        user = self._make_user('accountant')
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/auth/me/permissions/')
        data = response.json()
        self.assertIn('accounting', data['sections'])
        self.assertIn('post_journal_entries', data['actions'])
        self.assertNotIn('pos', data['sections'])
        self.assertNotIn('process_sale', data['actions'])

    def test_attendant_fuel_and_pos_only(self):
        user = self._make_user('attendant')
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/auth/me/permissions/')
        data = response.json()
        self.assertIn('fuel', data['sections'])
        self.assertIn('pos', data['sections'])
        self.assertNotIn('products', data['sections'])
        self.assertNotIn('accounting', data['sections'])


class UserInvitationTests(APITestCase):
    """
    Tests for the invite / accept-invite flow.
    Uses the public schema directly (no tenant schema creation needed).
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@acme.com', username='admin_acme',
            password='pass1234', first_name='Admin', last_name='User',
            role='admin',
        )
        self.manager = User.objects.create_user(
            email='manager@acme.com', username='manager_acme',
            password='pass1234', first_name='Mgr', last_name='User',
            role='manager',
        )
        self.cashier = User.objects.create_user(
            email='cashier@acme.com', username='cashier_acme',
            password='pass1234', first_name='Cash', last_name='User',
            role='cashier',
        )

    @patch('users.views.send_invitation_email')
    def test_admin_can_invite(self, mock_send):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/users/invite/', {
            'email': 'newstaff@acme.com', 'role': 'cashier',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(UserInvitation.objects.filter(email='newstaff@acme.com').exists())
        mock_send.assert_called_once()

    @patch('users.views.send_invitation_email')
    def test_manager_can_invite(self, mock_send):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post('/api/users/invite/', {
            'email': 'newstaff2@acme.com', 'role': 'attendant',
        }, format='json')
        self.assertEqual(response.status_code, 201)

    def test_cashier_cannot_invite(self):
        self.client.force_authenticate(user=self.cashier)
        response = self.client.post('/api/users/invite/', {
            'email': 'newstaff3@acme.com', 'role': 'cashier',
        }, format='json')
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_cannot_invite(self):
        response = self.client.post('/api/users/invite/', {
            'email': 'x@x.com', 'role': 'cashier',
        }, format='json')
        self.assertEqual(response.status_code, 401)

    @patch('users.views.send_invitation_email')
    def test_cannot_invite_admin_role(self, mock_send):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/users/invite/', {
            'email': 'newadmin@acme.com', 'role': 'admin',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    @patch('users.views.send_invitation_email')
    def test_cannot_invite_existing_user(self, mock_send):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/users/invite/', {
            'email': 'cashier@acme.com', 'role': 'manager',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def _make_invitation(self, email='invite@acme.com', role='cashier', schema='public', hours_valid=48):
        return UserInvitation.objects.create(
            email=email,
            role=role,
            tenant_schema=schema,
            invited_by_id=self.admin.pk,
            expires_at=timezone.now() + timedelta(hours=hours_valid),
        )

    def test_accept_invite_creates_user(self):
        inv = self._make_invitation()
        response = self.client.post('/api/users/accept-invite/', {
            'token': str(inv.token),
            'first_name': 'Jane',
            'last_name': 'Doe',
            'username': 'janedoe',
            'password': 'securepass99',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertIn('access', data)
        self.assertIn('refresh', data)
        self.assertEqual(data['user']['email'], 'invite@acme.com')
        self.assertEqual(data['user']['role'], 'cashier')
        inv.refresh_from_db()
        self.assertIsNotNone(inv.accepted_at)

    def test_accept_expired_invite_returns_400(self):
        inv = self._make_invitation(hours_valid=-1)
        response = self.client.post('/api/users/accept-invite/', {
            'token': str(inv.token),
            'first_name': 'Jane', 'last_name': 'Doe',
            'username': 'janedoe2', 'password': 'securepass99',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('expired', response.json()['error'].lower())

    def test_accept_already_used_invite_returns_400(self):
        inv = self._make_invitation(email='used@acme.com')
        inv.accepted_at = timezone.now()
        inv.save()
        response = self.client.post('/api/users/accept-invite/', {
            'token': str(inv.token),
            'first_name': 'A', 'last_name': 'B',
            'username': 'uniqueuser', 'password': 'securepass99',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_accept_invalid_token_returns_400(self):
        response = self.client.post('/api/users/accept-invite/', {
            'token': '00000000-0000-0000-0000-000000000000',
            'first_name': 'A', 'last_name': 'B',
            'username': 'abc', 'password': 'securepass99',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_accept_wrong_tenant_schema_returns_400(self):
        inv = self._make_invitation(schema='othertenant')
        response = self.client.post('/api/users/accept-invite/', {
            'token': str(inv.token),
            'first_name': 'A', 'last_name': 'B',
            'username': 'wrongschema', 'password': 'securepass99',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    @patch('users.views.send_invitation_email')
    def test_list_invitations_requires_admin_or_manager(self, mock_send):
        self.client.force_authenticate(user=self.cashier)
        response = self.client.get('/api/users/invitations/')
        self.assertEqual(response.status_code, 403)
