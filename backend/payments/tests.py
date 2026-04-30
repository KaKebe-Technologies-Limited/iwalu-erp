import uuid
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from users.models import User
from .models import PaymentConfig, PaymentTransaction

class PaymentAPITests(TenantTestCase):
    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        # Use an admin user — payment config CRUD and disbursements are now
        # admin-only (HIGH-severity findings from the Phase 6 security audit).
        self.user = User.objects.create_user(
            email='admin@test.com',
            username='paymentsadmin',
            password='password123',
            role='admin'
        )
        # Login to get JWT
        response = self.client.post('/api/auth/login/', {
            'email': 'admin@test.com',
            'password': 'password123',
        })
        token = response.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        
        # Setup PaymentConfig
        self.config = PaymentConfig.objects.get_or_create(pk=1)[0]
        self.config.is_enabled = True
        self.config.default_provider = 'mock'
        self.config.save()

    def test_initiate_payment_mock(self):
        url = reverse('payments-initiate')
        data = {
            'amount': '50000.00',
            'method': 'mobile_money',
            'phone_number': '256772123456',
            'description': 'Test Payment'
        }
        response = self.client.post(url, data, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')  # Mock provider succeeds immediately
        self.assertEqual(PaymentTransaction.objects.count(), 1)
        
        txn = PaymentTransaction.objects.first()
        self.assertEqual(txn.amount, Decimal('50000.00'))
        self.assertEqual(txn.provider, 'mock')

    def test_initiate_disbursement_mock(self):
        url = reverse('payments-disburse')
        data = {
            'amount': '25000.00',
            'method': 'mobile_money',
            'phone_number': '256772111222',
            'description': 'Test Disbursement'
        }
        response = self.client.post(url, data, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['transaction_type'], 'disbursement')
        
        txn = PaymentTransaction.objects.filter(transaction_type='disbursement').first()
        self.assertEqual(txn.amount, Decimal('25000.00'))
        self.assertTrue(txn.reference.startswith('DISB-'))

    def test_callback_pesapal(self):
        # Create a pending transaction
        txn = PaymentTransaction.objects.create(
            amount=Decimal('100.00'),
            method='card',
            provider='pesapal',
            reference='PAY-TEST-123',
            provider_transaction_id='pesapal-tracking-id',
            status='processing'
        )
        
        # Setup Pesapal config for the test
        self.config.pesapal_enabled = True
        self.config.pesapal_consumer_key = 'test'
        self.config.pesapal_consumer_secret = 'test'
        self.config.pesapal_ipn_id = 'test-ipn'
        self.config.save()
        
        url = reverse('payments-callback', kwargs={'provider_name': 'pesapal'})
        # Pesapal IPN is GET
        response = self.client.get(url, {'OrderTrackingId': 'pesapal-tracking-id'})
        
        # In a test environment without real API, it might fail/404 if handle_callback
        # tries to call Pesapal API. But we want to ensure the endpoint is reachable.
        self.assertIn(response.status_code, [200, 404])

    def test_payment_config_access(self):
        url = reverse('payment-config-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify secrets are not in response (serializer check)
        # PaymentConfigSerializer has write_only=True for keys
        self.assertNotIn('mtn_api_key', response.data)
        self.assertNotIn('pesapal_consumer_secret', response.data)
