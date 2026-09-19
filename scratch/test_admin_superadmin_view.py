import os
import sys
import re
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db
import models
from seed import seed_default_college

class TestSuperAdminAccessToAdmin(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        with self.app.app_context():
            seed_default_college()

    def _get_csrf_token(self):
        res = self.client.get('/login')
        html = res.data.decode('utf-8')
        m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
        if m:
            return m.group(1)
        with self.client.session_transaction() as sess:
            return sess.get('csrf_token')

    def test_superadmin_can_access_college_admin_panel(self):
        # 1. Login with SuperAdmin credentials
        token = self._get_csrf_token()
        login_resp = self.client.post('/login', data={
            'email': 'superadmin@spmcollege.ac.in',
            'password': 'SuperAdmin@123',
            'csrf_token': token
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)

        # 2. Access /superadmin
        sa_resp = self.client.get('/superadmin')
        self.assertEqual(sa_resp.status_code, 200)

        # 3. Access /admin (the exact button the user clicked!)
        admin_resp = self.client.get('/admin')
        self.assertEqual(admin_resp.status_code, 200)
        self.assertIn(b'College Administration Portal', admin_resp.data)
        self.assertIn(b'Platform Super Admin Mode', admin_resp.data)
        self.assertNotIn(b'UnboundLocalError', admin_resp.data)
        print("\n[SUCCESS] Super Admin clicked 'College Admin Portal' -> Loaded HTTP 200 cleanly without error!")

    def test_alternate_superadmin_credentials_access(self):
        token = self._get_csrf_token()
        login_resp = self.client.post('/login', data={
            'email': 'superadmin@portal.internal',
            'password': 'AdminPassword@123',
            'csrf_token': token
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)

        admin_resp = self.client.get('/admin')
        self.assertEqual(admin_resp.status_code, 200)
        self.assertIn(b'Platform Super Admin Mode', admin_resp.data)
        print("[SUCCESS] Alternate Super Admin (superadmin@portal.internal) loaded /admin with HTTP 200!")

    def test_college_admin_access(self):
        token = self._get_csrf_token()
        login_resp = self.client.post('/login', data={
            'email': 'admin@spmcollege.ac.in',
            'password': 'CollegeAdmin@123',
            'csrf_token': token
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)

        admin_resp = self.client.get('/admin')
        self.assertEqual(admin_resp.status_code, 200)
        self.assertIn(b'College Admin Desk', admin_resp.data)
        print("[SUCCESS] College Admin (admin@spmcollege.ac.in) loaded /admin with HTTP 200!")

    def test_superadmin_edit_option_visible_on_frontend_and_admin(self):
        token = self._get_csrf_token()
        self.client.post('/login', data={
            'email': 'superadmin@spmcollege.ac.in',
            'password': 'SuperAdmin@123',
            'csrf_token': token
        }, follow_redirects=True)

        # 1. Homepage has prominent Edit Option
        home_resp = self.client.get('/')
        self.assertEqual(home_resp.status_code, 200)
        self.assertIn(b'Edit College Details', home_resp.data)
        self.assertIn(b'Edit Option', home_resp.data)

        # 2. College Admin has Edit Option banner
        admin_resp = self.client.get('/admin')
        self.assertEqual(admin_resp.status_code, 200)
        self.assertIn(b'Edit College Details', admin_resp.data)

        # 3. Super Admin has branding-editor
        sa_resp = self.client.get('/superadmin')
        self.assertEqual(sa_resp.status_code, 200)
        self.assertIn(b'branding-editor', sa_resp.data)
        self.assertIn(b'Institutional Identity & Branding Editor', sa_resp.data)
        print("[SUCCESS] Edit Option is visible on Homepage (/), Admin (/admin), and Super Admin (/superadmin)!")

if __name__ == '__main__':
    unittest.main()
