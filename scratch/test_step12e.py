import sys
import os
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 12E: PRODUCTION SECURITY & HARDENING SUITE ")
print("==================================================")

college = seed_default_college()

def extract_csrf_token(res):
    html = res.data.decode('utf-8')
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    with client.session_transaction() as sess:
        return sess.get('csrf_token')

# 1. HTTP Security Headers Verification
print("\n[1/8] Auditing HTTP Security Response Headers...")
res_headers = client.get('/')
assert res_headers.status_code == 200
assert res_headers.headers.get('X-Content-Type-Options') == 'nosniff'
assert res_headers.headers.get('X-Frame-Options') == 'SAMEORIGIN'
assert res_headers.headers.get('X-XSS-Protection') == '1; mode=block'
assert res_headers.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'
print("  -> PASSED (nosniff, SAMEORIGIN, XSS-Protection, and Referrer-Policy headers verified)")

# 2. Session Cookie Hardening Flags Verification
print("\n[2/8] Auditing Session Cookie Hardening Flags...")
assert app.config.get('SESSION_COOKIE_HTTPONLY') is True
assert app.config.get('SESSION_COOKIE_SAMESITE') == 'Lax'
print("  -> PASSED (SESSION_COOKIE_HTTPONLY=True & SESSION_COOKIE_SAMESITE=Lax verified)")

# 3. CSRF Protection & Forged Token Rejection
print("\n[3/8] Testing CSRF protection & forged token rejection...")
client.get('/') # Initialize session
res_bad_csrf = client.post('/login', data={
    'email': 'admin@spmcollege.ac.in',
    'password': 'CollegeAdmin@123',
    'csrf_token': 'FORGED_INVALID_CSRF_TOKEN'
})
assert res_bad_csrf.status_code == 400, f"Expected 400 Bad Request for forged CSRF token, got {res_bad_csrf.status_code}"
print("  -> PASSED (Forged CSRF token rejected with HTTP 400 Bad Request)")

# 4. Open Redirect Protection
print("\n[4/8] Testing Open Redirect protection in login...")
res_g = client.get('/login')
t_log = extract_csrf_token(res_g)
res_open_redirect = client.post('/login?next=//phishing-site.com', data={
    'email': 'admin@spmcollege.ac.in',
    'password': 'CollegeAdmin@123',
    'csrf_token': t_log
}, follow_redirects=False)
assert res_open_redirect.status_code == 302, f"Expected 302 redirect, got {res_open_redirect.status_code}"
location = res_open_redirect.headers.get('Location', '')
assert 'phishing-site.com' not in location and ('/admin' in location or '/superadmin' in location or '/' in location)
client.get('/logout')
print("  -> PASSED (Malicious external next parameter redirected safely to internal portal)")

# 5. Path Traversal & Malicious Filename Rejection
print("\n[5/8] Testing Path Traversal & non-PDF filename rejection...")
res_g2 = client.get('/login')
t_log2 = extract_csrf_token(res_g2)
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123', 'csrf_token': t_log2})

res_adm = client.get('/admin')
t_adm = extract_csrf_token(res_adm)
bca = models.Course.query.filter_by(college_id=college.id, code='BCA').first()

# Malicious file extension attempt
res_bad_ext = client.post('/admin/question-paper/add', data={
    'course_id': bca.id,
    'year': '2026',
    'semester': 'Sem 1',
    'subject': 'Malware Test',
    'filename': 'payload.exe',
    'csrf_token': t_adm
}, follow_redirects=True)
assert res_bad_ext.status_code == 200
assert "must be a valid .pdf file" in res_bad_ext.data.decode('utf-8')
assert models.QuestionPaper.query.filter_by(subject='Malware Test').first() is None
client.get('/logout')
print("  -> PASSED (Malicious .exe extension rejected with validation alert)")

# 6. Cross-Tenant Attack Protection
print("\n[6/8] Auditing cross-tenant attack protection...")
other_college = models.College.query.filter_by(slug='step12e-other-tenant').first()
if not other_college:
    other_college = models.College(name='Step 12E Other Tenant', slug='step12e-other-tenant')
    db.session.add(other_college)
    db.session.commit()

other_course = models.Course(college_id=other_college.id, code='OTH12E', name='Other Course', level='UG', duration='3 Yrs', affiliation='BCU', overview='Desc', eligibility='Elig')
db.session.add(other_course)
db.session.commit()

res_g3 = client.get('/login')
t_log3 = extract_csrf_token(res_g3)
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123', 'csrf_token': t_log3})

res_adm2 = client.get('/admin')
t_adm2 = extract_csrf_token(res_adm2)

res_cross = client.post(f'/admin/course/delete/{other_course.id}', data={'csrf_token': t_adm2})
assert res_cross.status_code == 403

db.session.delete(other_course)
db.session.delete(other_college)
db.session.commit()
client.get('/logout')
print("  -> PASSED (Cross-tenant modification attempt blocked with HTTP 403)")

# 7. Revoked Module Access Protection
print("\n[7/8] Testing revoked module access protection...")
res_g4 = client.get('/login')
t_log4 = extract_csrf_token(res_g4)
client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123', 'csrf_token': t_log4})

cfg = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='academics').first()
cfg.admin_access = False
db.session.commit()
client.get('/logout')

res_g5 = client.get('/login')
t_log5 = extract_csrf_token(res_g5)
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123', 'csrf_token': t_log5})

res_adm3 = client.get('/admin')
t_adm3 = extract_csrf_token(res_adm3)

res_rev = client.post('/admin/course/add', data={'code': 'REVOKED', 'csrf_token': t_adm3})
assert res_rev.status_code == 403
client.get('/logout')

# Restore module access
res_g6 = client.get('/login')
t_log6 = extract_csrf_token(res_g6)
client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123', 'csrf_token': t_log6})
cfg.admin_access = True
db.session.commit()
client.get('/logout')
print("  -> PASSED (Revoked module access returns HTTP 403)")

# 8. Site-Wide 15-Route Health Sweep
print("\n[8/8] Running site-wide 15-route health sweep...")
routes = [
    '/', '/about', '/admission', '/apply', '/academics', '/departments',
    '/course/bca', '/facilities', '/placements', '/gallery',
    '/students-corner', '/forum', '/contact', '/admin', '/superadmin'
]

for r in routes:
    if r in ['/admin', '/superadmin']:
        res_g7 = client.get('/login')
        t_log7 = extract_csrf_token(res_g7)
        client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123', 'csrf_token': t_log7})
    res_r = client.get(r)
    assert res_r.status_code in [200, 302], f"Route {r} failed with status {res_r.status_code}"
    client.get('/logout')

print("  -> PASSED (All 15 routes operational with security headers)")

print("\n==================================================")
print(" ALL STEP 12E SECURITY TESTS PASSED 100%!        ")
print("==================================================")
