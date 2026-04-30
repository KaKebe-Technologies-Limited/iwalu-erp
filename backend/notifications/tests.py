from decimal import Decimal
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django.contrib.auth import get_user_model

from .models import Notification, NotificationPreference, NotificationTemplate
from . import services

User = get_user_model()


class NotificationTestBase(TenantTestCase):
    def setUp(self):
        self.client = TenantClient(self.tenant)
        self.admin = User.objects.create_user(
            email='admin@test.com', username='admin',
            password='testpass123', role='admin',
        )
        self.manager = User.objects.create_user(
            email='manager@test.com', username='manager',
            password='testpass123', role='manager',
        )
        self.cashier = User.objects.create_user(
            email='cashier@test.com', username='cashier',
            password='testpass123', role='cashier',
        )

    def _auth(self, user):
        response = self.client.post('/api/auth/login/', {
            'email': user.email, 'password': 'testpass123',
        })
        token = response.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'

    def _create_notification(self, recipient=None, **kwargs):
        defaults = {
            'recipient_id': (recipient or self.cashier).pk,
            'notification_type': 'low_stock',
            'channel': 'in_app',
            'priority': 'normal',
            'title': 'Low stock alert',
            'body': 'Product X is running low.',
        }
        defaults.update(kwargs)
        return Notification.objects.create(**defaults)


class NotificationServiceTests(NotificationTestBase):

    def test_create_notification(self):
        n = services.create_notification(
            recipient_id=self.cashier.pk,
            notification_type='low_stock',
            title='Low stock: Petrol',
            body='Petrol is below reorder level.',
        )
        self.assertIsNotNone(n)
        self.assertEqual(n.recipient_id, self.cashier.pk)
        self.assertEqual(n.notification_type, 'low_stock')
        self.assertIsNone(n.read_at)

    def test_create_notification_respects_opt_out(self):
        NotificationPreference.objects.create(
            user_id=self.cashier.pk,
            notification_type='low_stock',
            channel='in_app',
            is_enabled=False,
        )
        n = services.create_notification(
            recipient_id=self.cashier.pk,
            notification_type='low_stock',
            title='Low stock: Petrol',
            body='Petrol is below reorder level.',
        )
        self.assertIsNone(n)

    def test_mark_read(self):
        n = self._create_notification()
        updated = services.mark_read(n.pk, self.cashier.pk)
        self.assertIsNotNone(updated.read_at)

    def test_mark_read_wrong_user(self):
        n = self._create_notification()
        with self.assertRaises(Exception):
            services.mark_read(n.pk, self.admin.pk)

    def test_mark_all_read(self):
        self._create_notification()
        self._create_notification(title='Another alert')
        count = services.mark_all_read(self.cashier.pk)
        self.assertEqual(count, 2)
        self.assertEqual(
            Notification.objects.filter(
                recipient_id=self.cashier.pk, read_at__isnull=True,
            ).count(),
            0,
        )

    def test_mark_all_read_by_type(self):
        self._create_notification(notification_type='low_stock')
        self._create_notification(notification_type='low_fuel')
        count = services.mark_all_read(self.cashier.pk, notification_type='low_stock')
        self.assertEqual(count, 1)

    def test_unread_count(self):
        self._create_notification()
        self._create_notification()
        n3 = self._create_notification()
        services.mark_read(n3.pk, self.cashier.pk)
        self.assertEqual(services.get_unread_count(self.cashier.pk), 2)

    def test_create_from_template(self):
        NotificationTemplate.objects.create(
            notification_type='low_stock',
            channel='in_app',
            subject='Low stock: {product_name}',
            body='{product_name} at {outlet_name} is at {quantity} units.',
            variables=['product_name', 'outlet_name', 'quantity'],
        )
        n = services.create_notification_from_template(
            recipient_id=self.cashier.pk,
            notification_type='low_stock',
            context={
                'product_name': 'Diesel',
                'outlet_name': 'Main Station',
                'quantity': '15',
            },
        )
        self.assertIsNotNone(n)
        self.assertIn('Diesel', n.title)
        self.assertIn('Main Station', n.body)

    def test_create_from_template_missing(self):
        n = services.create_notification_from_template(
            recipient_id=self.cashier.pk,
            notification_type='low_stock',
            context={'product_name': 'Diesel'},
        )
        self.assertIsNone(n)


class NotificationAPITests(NotificationTestBase):

    def test_list_own_notifications(self):
        self._create_notification(recipient=self.cashier)
        self._create_notification(recipient=self.admin)
        self._auth(self.cashier)
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

    def test_filter_unread(self):
        n1 = self._create_notification()
        self._create_notification()
        services.mark_read(n1.pk, self.cashier.pk)
        self._auth(self.cashier)
        response = self.client.get('/api/notifications/?is_read=false')
        self.assertEqual(response.json()['count'], 1)

    def test_unread_count_endpoint(self):
        self._create_notification()
        self._create_notification()
        self._auth(self.cashier)
        response = self.client.get('/api/notifications/unread-count/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['unread_count'], 2)

    def test_mark_read_endpoint(self):
        n = self._create_notification()
        self._auth(self.cashier)
        response = self.client.post(f'/api/notifications/{n.pk}/read/')
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json()['read_at'])

    def test_read_all_endpoint(self):
        self._create_notification()
        self._create_notification()
        self._auth(self.cashier)
        response = self.client.post('/api/notifications/read-all/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['marked_read'], 2)

    def test_unauthenticated_access(self):
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, 401)


class NotificationPreferenceAPITests(NotificationTestBase):

    def test_list_preferences(self):
        NotificationPreference.objects.create(
            user_id=self.cashier.pk,
            notification_type='low_stock',
            channel='in_app',
            is_enabled=True,
        )
        self._auth(self.cashier)
        response = self.client.get('/api/notification-preferences/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

    def test_update_preference(self):
        self._auth(self.cashier)
        response = self.client.post(
            '/api/notification-preferences/update-preference/',
            data={
                'notification_type': 'low_fuel',
                'channel': 'in_app',
                'is_enabled': False,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()['is_enabled'])

    def test_update_preference_toggle(self):
        NotificationPreference.objects.create(
            user_id=self.cashier.pk,
            notification_type='low_fuel',
            channel='in_app',
            is_enabled=True,
        )
        self._auth(self.cashier)
        response = self.client.post(
            '/api/notification-preferences/update-preference/',
            data={
                'notification_type': 'low_fuel',
                'channel': 'in_app',
                'is_enabled': False,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['is_enabled'])


class NotificationTemplateAPITests(NotificationTestBase):

    def test_create_template_admin(self):
        self._auth(self.admin)
        response = self.client.post('/api/notification-templates/', {
            'notification_type': 'low_stock',
            'channel': 'in_app',
            'subject': 'Low stock: {product_name}',
            'body': '{product_name} is at {quantity} units.',
            'variables': ['product_name', 'quantity'],
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)

    def test_create_template_cashier_denied(self):
        self._auth(self.cashier)
        response = self.client.post('/api/notification-templates/', {
            'notification_type': 'low_stock',
            'channel': 'in_app',
            'subject': 'Test',
            'body': 'Test',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_list_templates_authenticated(self):
        NotificationTemplate.objects.create(
            notification_type='low_stock',
            channel='in_app',
            subject='Test',
            body='Test body',
        )
        self._auth(self.cashier)
        response = self.client.get('/api/notification-templates/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

    def test_preview_template(self):
        t = NotificationTemplate.objects.create(
            notification_type='low_stock',
            channel='in_app',
            subject='Low stock: {product_name}',
            body='{product_name} at {outlet_name} is low.',
        )
        self._auth(self.admin)
        response = self.client.post(
            f'/api/notification-templates/{t.pk}/preview/',
            data={'context': {'product_name': 'Diesel', 'outlet_name': 'Main'}},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('Diesel', response.json()['subject'])
        self.assertIn('Main', response.json()['body'])
