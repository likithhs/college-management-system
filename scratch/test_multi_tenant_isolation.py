import sys
import os
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from app import app
from extensions import db
import models
from seed import seed_default_college, onboard_new_college

class MultiTenantWhiteLabelingTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_multi_tenant_isolation_and_white_labeling(self):
        print("\n========================================================")
        print("RUNNING MULTI-TENANT COMMERCIAL WHITE-LABELING ISOLATION TEST")
        print("========================================================")

        # 1. Ensure Default College A exists
        college_a = models.College.query.get(1) or models.College.query.filter_by(slug='seshadripuram-college').first()
        if not college_a:
            seed_default_college()
            college_a = models.College.query.get(1)
        self.assertIsNotNone(college_a, "College A (Seshadripuram) must exist")

        # 2. Onboard Client College B (e.g. Christ College)
        college_b = models.College.query.filter_by(slug='christ-college').first()
        if not college_b:
            success, college_b = onboard_new_college(
                name="Christ College Autonomous",
                slug="christ-college",
                email_info="info@christcollege.edu",
                principal_name="Dr. Thomas C. Mathew",
                affiliation="Bengaluru City University",
                admin_email="admin@christcollege.edu",
                admin_password="Password@123"
            )
            self.assertTrue(success, "Onboarding College B must succeed")
        self.assertIsNotNone(college_b, "College B (Christ College) must exist in DB")

        print(f"[*] College A ID: {college_a.id}, Name: '{college_a.name}'")
        print(f"[*] College B ID: {college_b.id}, Name: '{college_b.name}'")

        # Ensure College B has independent settings and clean initial state
        setting_b = college_b.settings
        self.assertIsNotNone(setting_b, "College B must have isolated CollegeSetting row")
        self.assertEqual(setting_b.college_id, college_b.id)
        
        # Reset clean baseline state
        college_a.name = "Seshadripuram College"
        if college_a.settings:
            college_a.settings.college_name = "Seshadripuram College"
            college_a.settings.principal_name = "Dr. Meera K. Rao"
        college_b.name = "Christ College Autonomous"
        setting_b.college_name = "Christ College Autonomous"
        setting_b.principal_name = "Dr. Thomas C. Mathew"
        db.session.commit()

        orig_b_principal = "Dr. Thomas C. Mathew"
        orig_b_name = "Christ College Autonomous"

        # 3. Simulate Super Admin logging in and editing College A
        superadmin_user = models.User.query.filter_by(email="superadmin@portal.internal").first()
        if not superadmin_user:
            superadmin_user = models.User.query.filter_by(role='PLATFORM_SUPER_ADMIN').first()
        self.assertIsNotNone(superadmin_user, "Super Admin user must exist")

        csrf_token = 'test_csrf_token_12345678901234567890'
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(superadmin_user.id)
            sess['_fresh'] = True
            sess['csrf_token'] = csrf_token
            sess['superadmin_active_college_id'] = college_a.id

        # Update College A settings via POST /superadmin/settings/update
        new_name_a = "Seshadripuram Institute of Higher Learning"
        new_principal_a = "Dr. Meera K. Rao Senior"
        new_tagline_a = "Leading Education Since 1973"
        new_map_a = "Seshadripuram Main Campus Bengaluru"

        resp = self.client.post('/superadmin/settings/update', data={
            'csrf_token': csrf_token,
            'college_id': college_a.id,
            'college_name': new_name_a,
            'short_name': 'SIHL',
            'tagline': new_tagline_a,
            'affiliation': 'Bengaluru City University',
            'accreditation': 'NAAC A++ Grade',
            'est_year': '1973',
            'alumni_count': '50,000+',
            'principal_name': new_principal_a,
            'principal_title': 'Ph.D, Senior Principal',
            'principal_message': 'Welcome to SIHL where we shape global leaders.',
            'trust_name': 'Seshadripuram Educational Trust',
            'trust_president': 'Sri N. R. Panditharadhya',
            'trustee_name': 'Dr. Wooday P. Krishna',
            'email_info': 'info@sihl.ac.in',
            'admissions_email': 'admissions@sihl.ac.in',
            'phone_primary': '+91 80 2295 5354',
            'address': '#27 Nagappa Street Seshadripuram',
            'city': 'Bengaluru',
            'state_pincode': 'Karnataka - 560020',
            'map_query': new_map_a,
            'hero_title': 'Excellence in Commerce and Tech',
            'hero_subtitle': 'Discover your future at SIHL.',
            'about_story': 'A heritage institution established in 1973.'
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)

        # 4. STRICT ISOLATION ASSERTION:
        # College A must have new values
        db.session.expire_all()
        refreshed_a = db.session.get(models.College, college_a.id)
        refreshed_b = db.session.get(models.College, college_b.id)

        print("\n--- Verifying Database Isolation ---")
        print(f"[A] Updated Name: '{refreshed_a.name}', Principal: '{refreshed_a.settings.principal_name}'")
        print(f"[B] Untouched Name: '{refreshed_b.name}', Principal: '{refreshed_b.settings.principal_name}'")

        self.assertEqual(refreshed_a.name, new_name_a, "College A name must be updated")
        self.assertEqual(refreshed_a.settings.principal_name, new_principal_a, "College A principal must be updated")

        # CRITICAL TEST: College B MUST NOT HAVE CHANGED AT ALL!
        self.assertEqual(refreshed_b.name, orig_b_name, "SECURITY BREACH: College B name was contaminated by College A update!")
        self.assertEqual(refreshed_b.settings.principal_name, orig_b_principal, "SECURITY BREACH: College B principal was contaminated by College A update!")
        self.assertNotEqual(refreshed_b.settings.principal_name, new_principal_a, "College B must not have College A's principal")

        # 5. Reverse Isolation Test: Update College B
        new_principal_b = "Dr. Fr. Abraham V. M."
        resp_b = self.client.post('/superadmin/settings/update', data={
            'csrf_token': csrf_token,
            'college_id': college_b.id,
            'college_name': 'Christ College Autonomous',
            'short_name': 'CCA',
            'tagline': 'Excellence and Service',
            'affiliation': 'Bangalore University',
            'accreditation': 'NAAC A+ Grade',
            'est_year': '1969',
            'alumni_count': '35,000+',
            'principal_name': new_principal_b,
            'principal_title': 'MA, Ph.D, Principal',
            'principal_message': 'Welcome to Christ College.',
            'trust_name': 'CMI Educational Trust',
            'trust_president': 'Fr. Rector',
            'trustee_name': 'Fr. Vice Chancellor',
            'email_info': 'info@christcollege.edu',
            'admissions_email': 'admissions@christcollege.edu',
            'phone_primary': '+91 80 4012 9100',
            'address': 'Hosur Road, Dharmaram College PO',
            'city': 'Bengaluru',
            'state_pincode': 'Karnataka - 560029',
            'map_query': 'Christ College Hosur Road Bengaluru',
            'hero_title': 'Excellence and Service',
            'hero_subtitle': 'Holistic education since 1969.',
            'about_story': 'Christ College was established in 1969.'
        }, follow_redirects=True)
        self.assertEqual(resp_b.status_code, 200)

        db.session.expire_all()
        refreshed_a_2 = db.session.get(models.College, college_a.id)
        refreshed_b_2 = db.session.get(models.College, college_b.id)

        print("\n--- Verifying Reverse Isolation ---")
        print(f"[A] After B update, College A Name: '{refreshed_a_2.name}', Principal: '{refreshed_a_2.settings.principal_name}'")
        print(f"[B] College B Name: '{refreshed_b_2.name}', Principal: '{refreshed_b_2.settings.principal_name}'")

        self.assertEqual(refreshed_b_2.settings.principal_name, new_principal_b)
        self.assertEqual(refreshed_a_2.settings.principal_name, new_principal_a, "SECURITY BREACH: College A was contaminated by College B update!")

        # 6. Frontend Dynamic Rendering Isolation Check via Public Routes
        print("\n--- Verifying Public Route Multi-Tenant Dynamic Rendering ---")
        # Clear session to act as anonymous visitor
        anon_client = self.app.test_client()

        # Visit College A site
        resp_view_a = anon_client.get('/?college=' + college_a.slug)
        self.assertEqual(resp_view_a.status_code, 200)
        content_a = resp_view_a.get_data(as_text=True)
        if "Dr. Meera K. Rao Senior" not in content_a:
            print(f"[DEBUG] 'Dr. Meera K. Rao Senior' not found in content_a. Sample: {content_a[:500]}")
        self.assertIn("Dr. Meera K. Rao Senior", content_a)
        self.assertNotIn("Dr. Fr. Abraham V. M.", content_a, "College A page leaked College B principal!")

        # Visit College B site via direct slug route
        resp_slug_b = anon_client.get('/c/' + college_b.slug, follow_redirects=True)
        self.assertEqual(resp_slug_b.status_code, 200)
        content_b = resp_slug_b.get_data(as_text=True)
        if "Christ College Autonomous" not in content_b or "Dr. Fr. Abraham V. M." not in content_b:
            print(f"[DEBUG] College B details missing in content_b. Sample: {content_b[:500]}")
        self.assertIn("Christ College Autonomous", content_b)
        self.assertIn("Dr. Fr. Abraham V. M.", content_b)
        self.assertNotIn("Dr. Meera K. Rao Senior", content_b, "College B page leaked College A principal!")

        print("\n>>> ALL MULTI-TENANT ISOLATION AND WHITE-LABELING TESTS PASSED PERFECTLY! <<<")

if __name__ == '__main__':
    unittest.main()
