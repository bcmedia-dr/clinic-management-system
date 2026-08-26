import os
import re
import shutil
import tempfile
import unittest


_TEMP_DIR = tempfile.mkdtemp(prefix='clinic_security_test_')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(_TEMP_DIR, 'clinic.db')
os.environ['SECRET_KEY'] = 'test-only-secret-key'
os.environ['ADMIN_PASSWORD'] = 'test-admin-password'
os.environ['USER_PASSWORD'] = 'test-user-password'
os.environ.pop('RENDER', None)

from app import app, db  # noqa: E402


class SecurityRegressionTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TEMP_DIR, ignore_errors=True)

    def setUp(self):
        app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
        with app.app_context():
            db.drop_all()
            db.create_all()
        self.client = app.test_client()

    @staticmethod
    def _csrf_from_html(response):
        match = re.search(rb'<meta name="csrf-token" content="([^"]+)"', response.data)
        if not match:
            raise AssertionError('CSRF meta token missing')
        return match.group(1).decode()

    def _login_admin(self):
        response = self.client.post('/login', json={
            'username': 'admin',
            'password': 'test-admin-password',
        })
        self.assertEqual(response.status_code, 200)
        page = self.client.get('/')
        return self._csrf_from_html(page)

    def test_sensitive_routes_require_login(self):
        for path in (
            '/api/clinics?per_page=1',
            '/api/export',
            '/api/health-mall/export',
            '/api/baiwei/export',
            '/api/campaign/match-history',
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)

        self.assertEqual(
            self.client.delete('/api/campaign/match-history/1').status_code,
            401,
        )

    def test_login_page_and_security_headers_remain_available(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self._csrf_from_html(response)
        self.assertEqual(response.headers['X-Frame-Options'], 'DENY')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])

    def test_csrf_blocks_write_but_valid_flow_still_works(self):
        token = self._login_admin()
        payload = {
            'region': '台北市',
            'district': '中正區',
            'name': '安全測試診所',
            'phone': '02-2345-6789',
        }
        blocked = self.client.post('/api/clinics', json=payload)
        self.assertEqual(blocked.status_code, 403)

        created = self.client.post(
            '/api/clinics',
            json=payload,
            headers={'X-CSRF-Token': token},
        )
        self.assertEqual(created.status_code, 200)
        listing = self.client.get('/api/clinics')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.get_json()['total'], 1)
        self.assertEqual(listing.headers['Cache-Control'], 'no-store')

    def test_user_role_cannot_modify_admin_data(self):
        self.client.post('/login', json={
            'username': 'user',
            'password': 'test-user-password',
        })
        token = self._csrf_from_html(self.client.get('/'))
        response = self.client.post(
            '/api/clinics',
            json={'name': '不可新增'},
            headers={'X-CSRF-Token': token},
        )
        self.assertEqual(response.status_code, 403)

    def test_existing_clinic_crud_and_export_flows_still_work(self):
        token = self._login_admin()
        headers = {'X-CSRF-Token': token}
        created = self.client.post('/api/clinics', json={
            'region': '台北市',
            'district': '中正區',
            'name': '回歸測試診所',
            'phone': '02-2777-8888',
            'specialties': '家醫科',
        }, headers=headers)
        self.assertEqual(created.status_code, 200)
        clinic_id = created.get_json()['id']

        detail = self.client.get(f'/api/clinics/{clinic_id}')
        self.assertEqual(detail.get_json()['name'], '回歸測試診所')
        updated = self.client.put(f'/api/clinics/{clinic_id}', json={
            'region': '新北市',
            'district': '板橋區',
            'name': '回歸測試診所更新',
            'phone': '02-2777-8888',
            'specialties': '內科',
        }, headers=headers)
        self.assertEqual(updated.status_code, 200)

        exported = self.client.get('/api/export')
        self.assertEqual(exported.status_code, 200)
        self.assertIn(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            exported.content_type,
        )

        self.assertEqual(
            self.client.delete(f'/api/clinics/{clinic_id}', headers=headers).status_code,
            200,
        )
        deleted = self.client.get('/api/clinics/deleted').get_json()
        self.assertEqual(len(deleted), 1)
        self.assertEqual(
            self.client.put(f'/api/clinics/{clinic_id}/restore', headers=headers).status_code,
            200,
        )

    def test_existing_campaign_crud_flow_still_works(self):
        token = self._login_admin()
        headers = {'X-CSRF-Token': token}
        created = self.client.post('/api/campaigns', json={
            'name': '安全回歸活動',
            'brand': '測試品牌',
            'year': 2026,
            'month': 8,
        }, headers=headers)
        self.assertEqual(created.status_code, 200)
        campaign_id = created.get_json()['id']
        self.assertEqual(len(self.client.get('/api/campaigns').get_json()), 1)
        updated = self.client.put(f'/api/campaigns/{campaign_id}', json={
            'brand': '更新品牌',
            'year': 2026,
            'month': 9,
            'note': '不變更流程',
        }, headers=headers)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(
            self.client.delete(f'/api/campaigns/{campaign_id}', headers=headers).status_code,
            200,
        )


if __name__ == '__main__':
    unittest.main()
