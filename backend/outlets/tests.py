from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django.contrib.auth import get_user_model

User = get_user_model()


class OutletAPITest(TenantTestCase):
    def setUp(self):
        self.client = TenantClient(self.tenant)
        self.admin = User.objects.create_user(
            email='admin@test.com', username='admin',
            password='testpass123', role='admin',
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

    def test_admin_can_create_outlet(self):
        self._auth(self.admin)
        response = self.client.post('/api/outlets/', {
            'name': 'Main Station',
            'outlet_type': 'fuel_station',
            'address': 'Lira Road',
            'phone': '+256700000000',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], 'Main Station')

    def test_cashier_cannot_create_outlet(self):
        self._auth(self.cashier)
        response = self.client.post('/api/outlets/', {
            'name': 'Side Shop',
            'outlet_type': 'cafe',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_cashier_can_list_outlets(self):
        self._auth(self.cashier)
        response = self.client.get('/api/outlets/')
        self.assertEqual(response.status_code, 200)

    def test_filter_by_outlet_type(self):
        self._auth(self.admin)
        self.client.post('/api/outlets/', {
            'name': 'Fuel 1', 'outlet_type': 'fuel_station',
        }, content_type='application/json')
        self.client.post('/api/outlets/', {
            'name': 'Cafe 1', 'outlet_type': 'cafe',
        }, content_type='application/json')
        response = self.client.get('/api/outlets/?outlet_type=fuel_station')
        results = response.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Fuel 1')

    def test_search_outlets(self):
        self._auth(self.admin)
        self.client.post('/api/outlets/', {
            'name': 'Lira Main', 'outlet_type': 'fuel_station',
        }, content_type='application/json')
        self.client.post('/api/outlets/', {
            'name': 'Gulu Branch', 'outlet_type': 'fuel_station',
        }, content_type='application/json')
        response = self.client.get('/api/outlets/?search=Lira')
        results = response.json()['results']
        self.assertEqual(len(results), 1)

    def test_admin_can_delete_outlet(self):
        self._auth(self.admin)
        resp = self.client.post('/api/outlets/', {
            'name': 'To Delete', 'outlet_type': 'general',
        }, content_type='application/json')
        outlet_id = resp.json()['id']
        response = self.client.delete(f'/api/outlets/{outlet_id}/')
        self.assertEqual(response.status_code, 204)
