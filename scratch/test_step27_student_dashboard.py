import sys
import os
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models, provision_student_from_application
from seed import seed_default_college
from rate_limiter import reset_rate_limiter

app.app_context().push()
db.create_all()
client = app.test_client(use_cookies=True)

print("==================================================")
print(" STEP 27: STUDENT AUTHENTICATION & PORTAL AUDIT   ")
print("==================================================")

college = seed_default_college()

def extract_csrf_token(res):
    html = res.data.decode('utf-8')
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    with client.session_transaction() as sess:
        return sess.get('csrf_token')

reset_rate_limiter()

# [1/10] Student Model & Password Hashing Unit Test
print("\n[1/10] Auditing Student Model & Password Hashing...")
s_unit = models.Student.query.filter_by(register_number='REG-UNIT-101').first()
if not s_unit:
    s_unit = models.Student(
        college_id=college.id,
        register_number='REG-UNIT-101',
        full_name='Unit Test Student',
        email='unit.student@example.com',
        course_code='BCA',
        semester='Semester 1',
        section='A',
        status='ACTIVE'
    )
    s_unit.set_password('SecurePass@123')
    db.session.add(s_unit)
    db.session.commit()

assert s_unit.check_password('SecurePass@123') is True
assert s_unit.check_password('WrongPass') is False
print("  -> PASSED (Student model password hashing & verification confirmed)")

# [2/10] Automatic Student Provisioning Helper Test
print("\n[2/10] Auditing Student Provisioning Helper...")
app_seat = models.AdmissionApplication.query.filter_by(application_number='SC2026-STEP27A').first()
if not app_seat:
    app_seat = models.AdmissionApplication(
        college_id=college.id,
        application_number='SC2026-STEP27A',
        full_name='Kavya Nair',
        guardian_name='Venugopal Nair',
        email='kavya.nair@example.com',
        phone='+91 9988776655',
        course='BCA',
        percentage=94.0,
        status='SEAT_LOCKED'
    )
    db.session.add(app_seat)
    db.session.commit()

student_p1, raw_pass1 = provision_student_from_application(app_seat, raw_password='KavyaStudent@123')
assert student_p1 is not None
assert student_p1.admission_application_id == app_seat.id
assert student_p1.email == 'kavya.nair@example.com'
print("  -> PASSED (Student account provisioned from SEAT_LOCKED application)")

# [3/10] Duplicate Provisioning Protection Test
print("\n[3/10] Auditing Duplicate Provisioning Protection...")
student_p2, raw_pass2 = provision_student_from_application(app_seat, raw_password='OtherPass@123')
assert student_p2.id == student_p1.id
assert raw_pass2 is None # Duplicate provisioning avoided!
assert models.Student.query.filter_by(admission_application_id=app_seat.id).count() == 1
print("  -> PASSED (Re-triggering provisioning helper strictly returned existing student record)")

# [4/10] Student Authentication & Session Initialization Test
print("\n[4/10] Auditing Student Login & Session Initialization...")
res_login_g = client.get('/student/login')
tok_s_login = extract_csrf_token(res_login_g)

res_s_auth = client.post('/student/login', data={
    'login_id': 'kavya.nair@example.com',
    'password': 'KavyaStudent@123',
    'csrf_token': tok_s_login
}, follow_redirects=True)
assert res_s_auth.status_code == 200

with client.session_transaction() as sess:
    s_access = sess.get('student_access')
    assert s_access is not None
    assert s_access['student_id'] == student_p1.id
print("  -> PASSED (Student authenticated & session initialized)")

# [5/10] Student Dashboard Rendering & Enrolled Data Test
print("\n[5/10] Auditing Student Dashboard Rendering...")
res_dash = client.get('/student/dashboard')
assert res_dash.status_code == 200
html_dash = res_dash.data.decode('utf-8')
assert 'Kavya Nair' in html_dash
assert student_p1.register_number in html_dash
assert 'Curriculum Subjects' in html_dash
print("  -> PASSED (Student Dashboard rendered enrolled course info cleanly)")

# [6/10] Profile Update Mutation Test
print("\n[6/10] Auditing Student Profile Update Mutation...")
tok_dash = extract_csrf_token(res_dash)
res_prof_upd = client.post('/student/profile/update', data={
    'phone': '+91 9999988888',
    'csrf_token': tok_dash
}, follow_redirects=True)
assert res_prof_upd.status_code == 200
db.session.refresh(student_p1)
assert student_p1.phone == '+91 9999988888'
print("  -> PASSED (Student contact info updated successfully)")

# [7/10] Student Access Isolation (Unauthenticated Access Blocked)
print("\n[7/10] Auditing Student Access Isolation...")
client.get('/student/logout')
res_anon_dash = client.get('/student/dashboard', follow_redirects=True)
assert 'Authentication required' in res_anon_dash.data.decode('utf-8')
print("  -> PASSED (Unauthenticated dashboard request redirected to student login)")

# [8/10] Suspended Account Access Rejection Test
print("\n[8/10] Auditing Suspended Student Account Rejection...")
student_p1.status = 'SUSPENDED'
db.session.commit()

tok_s_login2 = extract_csrf_token(client.get('/student/login'))
res_susp_login = client.post('/student/login', data={
    'login_id': 'kavya.nair@example.com',
    'password': 'KavyaStudent@123',
    'csrf_token': tok_s_login2
})
assert res_susp_login.status_code == 403
print("  -> PASSED (Suspended student login attempt strictly returned HTTP 403 Forbidden)")

student_p1.status = 'ACTIVE'
db.session.commit()

# [9/10] Student Login Rate Limiting Test (5 POSTs / minute)
print("\n[9/10] Auditing Student Login Rate Limiting...")
reset_rate_limiter('student_login')
tok_s_login3 = extract_csrf_token(client.get('/student/login'))

for i in range(1, 6):
    res_rl = client.post('/student/login', data={
        'login_id': 'kavya.nair@example.com',
        'password': 'WrongPassword123',
        'csrf_token': tok_s_login3
    })
    assert res_rl.status_code != 429

res_rl_blocked = client.post('/student/login', data={
    'login_id': 'kavya.nair@example.com',
    'password': 'WrongPassword123',
    'csrf_token': tok_s_login3
})
assert res_rl_blocked.status_code == 429
print("  -> PASSED (6th rapid student login attempt strictly returned HTTP 429)")

reset_rate_limiter('student_login')

# [10/10] Cleanup Temporary Test Data
print("\n[10/10] Cleaning Up Temporary Test Records...")
models.Student.query.filter_by(college_id=college.id).delete()
models.AdmissionApplication.query.filter_by(college_id=college.id).delete()
db.session.commit()
print("  -> PASSED (Temporary test records cleaned up)")

print("\n==================================================")
print(" ALL 10 STEP 27 STUDENT DASHBOARD TESTS PASSED!   ")
print("==================================================")
