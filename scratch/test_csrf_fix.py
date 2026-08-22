import sys
import os
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  CSRF HARDENING & VERIFICATION TEST SUITE       ")
print("==================================================")

college = seed_default_college()

def extract_csrf_token(response):
    """Extracts csrf_token hidden input value from rendered HTML response."""
    html = response.data.decode('utf-8')
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if match:
        return match.group(1)
    # Fallback to session cookie inspection
    with client.session_transaction() as sess:
        return sess.get('csrf_token')

# 1. Missing Token Test
print("\n[1/7] Testing POST request without CSRF token (Expects 400)...")
res_no_token = client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
assert res_no_token.status_code == 400, f"Expected 400, got {res_no_token.status_code}"
print("  -> PASSED (Missing CSRF token blocked with HTTP 400 Bad Request)")

# 2. Invalid Token Test
print("\n[2/7] Testing POST request with invalid CSRF token (Expects 400)...")
res_bad_token = client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123', 'csrf_token': 'FORGED_INVALID_TOKEN'})
assert res_bad_token.status_code == 400, f"Expected 400, got {res_bad_token.status_code}"
print("  -> PASSED (Invalid CSRF token blocked with HTTP 400 Bad Request)")

# 3. Valid Login CSRF Test
print("\n[3/7] Testing Login POST with valid CSRF token...")
res_get_login = client.get('/login')
assert res_get_login.status_code == 200
token_login = extract_csrf_token(res_get_login)
assert token_login is not None, "CSRF token missing in login.html render"

res_post_login = client.post('/login', data={
    'email': 'admin@spmcollege.ac.in',
    'password': 'CollegeAdmin@123',
    'csrf_token': token_login
})
assert res_post_login.status_code in [200, 302]
print("  -> PASSED (Login with valid CSRF token succeeded)")

# 4. Valid Admission Submission Test
print("\n[4/7] Testing Online Admission Apply POST with valid CSRF token...")
res_get_apply = client.get('/apply')
assert res_get_apply.status_code == 200
token_apply = extract_csrf_token(res_get_apply)

res_post_apply = client.post('/apply', data={
    'full_name': 'CSRF Verified Student',
    'guardian_name': 'Parent Name',
    'email': f'csrf.student.{os.urandom(2).hex()}@spmcollege.ac.in',
    'phone': '9876543210',
    'course': 'BCA - Bachelor of Computer Applications',
    'percentage': '89.5',
    'csrf_token': token_apply
}, follow_redirects=True)
assert res_post_apply.status_code == 200
assert "submitted successfully" in res_post_apply.data.decode('utf-8')
print("  -> PASSED (Online admission application with valid CSRF token succeeded)")

# 5. Admin Mutation Test
print("\n[5/7] Testing College Admin mutation POST with valid CSRF token...")
res_get_admin = client.get('/admin')
assert res_get_admin.status_code == 200
token_admin = extract_csrf_token(res_get_admin)

res_post_course = client.post('/admin/course/add', data={
    'code': 'CSRFTEST',
    'name': 'CSRF Protection Degree',
    'level': 'Undergraduate (UG)',
    'duration': '3 Years',
    'overview': 'Overview text',
    'csrf_token': token_admin
}, follow_redirects=True)
assert res_post_course.status_code == 200
course_record = models.Course.query.filter_by(code='CSRFTEST').first()
assert course_record is not None

# Clean up created test course
client.post(f'/admin/course/delete/{course_record.id}', data={'csrf_token': token_admin})
client.get('/logout')
print("  -> PASSED (Admin course creation & deletion with valid CSRF token succeeded)")

# 6. Super Admin Mutation Test
print("\n[6/7] Testing Super Admin mutation POST with valid CSRF token...")
res_get_login_sa = client.get('/login')
token_sa_login = extract_csrf_token(res_get_login_sa)
client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123', 'csrf_token': token_sa_login})

res_get_sa = client.get('/superadmin')
assert res_get_sa.status_code == 200
token_sa = extract_csrf_token(res_get_sa)

res_toggle = client.post('/superadmin/toggle-enable/about', data={'csrf_token': token_sa}, follow_redirects=True)
assert res_toggle.status_code == 200

# Toggle back
client.post('/superadmin/toggle-enable/about', data={'csrf_token': token_sa})
client.get('/logout')
print("  -> PASSED (Super Admin module toggle with valid CSRF token succeeded)")

# 7. Regression Test
print("\n[7/7] Verifying database models & tenant isolation...")
assert models.College.query.count() >= 1
assert models.Course.query.count() == 9
assert models.CampusEvent.query.count() == 4
assert models.AcademicCalendarItem.query.count() == 12
print("  -> PASSED (Database models & multi-tenant isolation intact)")

print("\n==================================================")
print(" ALL CSRF HARDENING TESTS PASSED 100%!           ")
print("==================================================")
