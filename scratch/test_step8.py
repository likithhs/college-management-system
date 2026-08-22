import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 8C: ADMISSIONS WORKFLOW & REGRESSION SUITE ")
print("==================================================")

college = seed_default_college()

# 1. Valid Public Application Submission
print("\n[1/16] Testing valid public application submission via POST /apply...")
app_data_1 = {
    'full_name': 'Kavya Ramesh',
    'guardian_name': 'Ramesh Kumar',
    'email': 'kavya.ramesh@example.com',
    'phone': '9876543210',
    'course': 'BCA - Bachelor of Computer Applications',
    'percentage': '92.5'
}
res_apply_1 = client.post('/apply', data=app_data_1, follow_redirects=True)
assert res_apply_1.status_code == 200, f"Expected 200, got {res_apply_1.status_code}"
assert "submitted successfully" in res_apply_1.data.decode('utf-8'), "Success message missing"
print("  -> PASSED (Application submitted successfully)")

# 2. Invalid Course Rejection
print("\n[2/16] Testing invalid course rejection...")
app_data_bad_course = app_data_1.copy()
app_data_bad_course['email'] = 'bad.course@example.com'
app_data_bad_course['course'] = 'Fake Invalid Course 101'
res_bad_course = client.post('/apply', data=app_data_bad_course, follow_redirects=True)
assert "Validation Error" in res_bad_course.data.decode('utf-8'), "Invalid course not rejected"
print("  -> PASSED (Invalid course rejected)")

# 3. Invalid Percentage Rejection
print("\n[3/16] Testing invalid percentage rejection...")
app_data_bad_perc = app_data_1.copy()
app_data_bad_perc['email'] = 'bad.perc@example.com'
app_data_bad_perc['percentage'] = '105.0'
res_bad_perc = client.post('/apply', data=app_data_bad_perc, follow_redirects=True)
assert "Validation Error" in res_bad_perc.data.decode('utf-8'), "Out-of-bounds percentage not rejected"
print("  -> PASSED (Invalid percentage rejected)")

# 4. Duplicate Application Prevention
print("\n[4/16] Testing duplicate application submission prevention...")
res_dup = client.post('/apply', data=app_data_1, follow_redirects=True)
assert "Application Notice" in res_dup.data.decode('utf-8'), "Duplicate application not blocked"
print("  -> PASSED (Duplicate application blocked)")

# 5, 6 & 7. Record Verification in Database
print("\n[5/16 - 7/16] Verifying database record fields, initial status, and tenant binding...")
submitted_app = models.AdmissionApplication.query.filter_by(email=app_data_1['email']).first()
assert submitted_app is not None, "Submitted application record not found in DB"
assert submitted_app.application_number.startswith('SC2026-'), "Application number prefix invalid"
assert submitted_app.status == 'PENDING', f"Expected initial status PENDING, got {submitted_app.status}"
assert submitted_app.college_id == college.id, "College tenant mismatch"
print(f"  -> App ID: {submitted_app.application_number}")
print(f"  -> Initial Status: {submitted_app.status}")
print(f"  -> Tenant ID: {submitted_app.college_id}")
print("  -> PASSED (Record verified)")

# 8. Query in College Admin Dashboard
print("\n[8/16] Testing presence in College Admin dashboard query...")
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
res_admin_view = client.get('/admin')
assert res_admin_view.status_code == 200, f"Expected 200, got {res_admin_view.status_code}"
assert submitted_app.application_number in res_admin_view.data.decode('utf-8'), "App ID missing from admin table"
print("  -> PASSED (Application rendered in Admin portal table)")

# 9. Full Valid Lifecycle: PENDING -> UNDER_REVIEW -> VERIFIED -> SEAT_LOCKED
print("\n[9/16] Testing full valid lifecycle (PENDING -> UNDER_REVIEW -> VERIFIED -> SEAT_LOCKED)...")
app_id = submitted_app.id

# PENDING -> UNDER_REVIEW
client.post(f'/admin/admission/status/{app_id}', data={'status': 'UNDER_REVIEW'})
app_s1 = db.session.get(models.AdmissionApplication, app_id)
assert app_s1.status == 'UNDER_REVIEW', f"Expected UNDER_REVIEW, got {app_s1.status}"

# UNDER_REVIEW -> VERIFIED
client.post(f'/admin/admission/status/{app_id}', data={'status': 'VERIFIED'})
app_s2 = db.session.get(models.AdmissionApplication, app_id)
assert app_s2.status == 'VERIFIED', f"Expected VERIFIED, got {app_s2.status}"

# VERIFIED -> SEAT_LOCKED
client.post(f'/admin/admission/status/{app_id}', data={'status': 'SEAT_LOCKED'})
app_s3 = db.session.get(models.AdmissionApplication, app_id)
assert app_s3.status == 'SEAT_LOCKED', f"Expected SEAT_LOCKED, got {app_s3.status}"
print("  -> PASSED (PENDING -> UNDER_REVIEW -> VERIFIED -> SEAT_LOCKED)")

# 10. Rejection & Reopening Lifecycle: SEAT_LOCKED -> VERIFIED -> REJECTED -> UNDER_REVIEW
print("\n[10/16] Testing rejection & reopening lifecycle...")
# SEAT_LOCKED -> VERIFIED
client.post(f'/admin/admission/status/{app_id}', data={'status': 'VERIFIED'})
# VERIFIED -> REJECTED
client.post(f'/admin/admission/status/{app_id}', data={'status': 'REJECTED'})
app_rej = db.session.get(models.AdmissionApplication, app_id)
assert app_rej.status == 'REJECTED', f"Expected REJECTED, got {app_rej.status}"

# REJECTED -> UNDER_REVIEW
client.post(f'/admin/admission/status/{app_id}', data={'status': 'UNDER_REVIEW'})
app_reopen = db.session.get(models.AdmissionApplication, app_id)
assert app_reopen.status == 'UNDER_REVIEW', f"Expected UNDER_REVIEW, got {app_reopen.status}"
print("  -> PASSED (Rejection & Reopening verified)")

# 11. Invalid Transition Rejection (UNDER_REVIEW -> SEAT_LOCKED)
print("\n[11/16] Testing illegal direct transition rejection...")
res_ill = client.post(f'/admin/admission/status/{app_id}', data={'status': 'SEAT_LOCKED'}, follow_redirects=True)
assert "Validation Error" in res_ill.data.decode('utf-8'), "Illegal transition was allowed"
print("  -> PASSED (Illegal transition blocked)")

# 12. admin_access = False RBAC Guard
print("\n[12/16] Testing admin_access = False RBAC guard...")
client.get('/logout')
client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
cfg = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='admission').first()
cfg.admin_access = False
db.session.commit()
client.get('/logout')

client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
res_rbac_denied = client.post(f'/admin/admission/status/{app_id}', data={'status': 'VERIFIED'})
assert res_rbac_denied.status_code == 403, f"Expected 403, got {res_rbac_denied.status_code}"
client.get('/logout')

# Restore admin_access
client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
cfg.admin_access = True
db.session.commit()
client.get('/logout')
print("  -> PASSED (HTTP 403 Forbidden on revoked admin_access)")

# 13. Cross-Tenant Application Modification Security
print("\n[13/16] Testing cross-tenant status modification protection...")
other_college = models.College.query.filter_by(slug='cross-tenant-adm-test-college').first()
if not other_college:
    other_college = models.College(name='Cross Tenant Adm Test College', slug='cross-tenant-adm-test-college')
    db.session.add(other_college)
    db.session.commit()

other_app = models.AdmissionApplication(
    college_id=other_college.id,
    application_number="SC2026-CROSS1",
    full_name="Cross Student",
    guardian_name="Cross Guardian",
    email="cross@example.com",
    phone="9876543210",
    course="BCA - Bachelor of Computer Applications",
    percentage=88.0,
    status="PENDING"
)
db.session.add(other_app)
db.session.commit()

client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
res_cross = client.post(f'/admin/admission/status/{other_app.id}', data={'status': 'UNDER_REVIEW'})
assert res_cross.status_code == 403, f"Expected 403, got {res_cross.status_code}"

# Cleanup cross tenant objects
db.session.delete(other_app)
db.session.delete(other_college)
db.session.commit()
client.get('/logout')
print("  -> PASSED (Cross tenant modification blocked with 403)")

# 14. Disabled Module Access Guard for /apply
print("\n[14/16] Testing disabled admission module guard for /apply...")
client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
cfg.enabled = False
db.session.commit()
client.get('/logout')

res_dis_apply = client.get('/apply')
assert res_dis_apply.status_code == 302, f"Expected 302 redirect, got {res_dis_apply.status_code}"

client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
cfg.enabled = True
db.session.commit()
client.get('/logout')
print("  -> PASSED (Disabled module redirects /apply requests)")

# 15. Database Persistence Check
print("\n[15/16] Testing database persistence across sessions...")
check_app = models.AdmissionApplication.query.filter_by(email=app_data_1['email']).first()
assert check_app is not None, "Application lost across session"
print("  -> PASSED (Application persisted in SQLite DB)")

# 16. Full Site-Wide Regression Check
print("\n[16/16] Testing site-wide regression across public & admin routes...")
public_routes = [
    ('/', 200, 'Home'),
    ('/about', 200, 'About Us'),
    ('/admission', 200, 'Admission'),
    ('/apply', 200, 'Apply'),
    ('/departments', 200, 'Departments'),
    ('/facilities', 200, 'Facilities'),
    ('/placements', 200, 'Placements'),
    ('/gallery', 200, 'Gallery'),
    ('/students-corner', 200, 'Students Corner'),
    ('/forum', 200, 'Community Forum'),
    ('/contact', 200, 'Contact Us')
]

for route, expected_code, name in public_routes:
    res_r = client.get(route)
    assert res_r.status_code == expected_code, f"Route {route} failed with status {res_r.status_code}"
    print(f"  -> {name} ({route}): HTTP {res_r.status_code} OK")

# Test College Admin route while logged in
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
res_adm = client.get('/admin')
assert res_adm.status_code == 200, f"Route /admin failed with status {res_adm.status_code}"
print("  -> College Admin (/admin): HTTP 200 OK")
client.get('/logout')

# Test Super Admin route while logged in
client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
res_sa = client.get('/superadmin')
assert res_sa.status_code == 200, f"Route /superadmin failed with status {res_sa.status_code}"
print("  -> Super Admin (/superadmin): HTTP 200 OK")
client.get('/logout')

# Clean up test application record
db.session.delete(submitted_app)
db.session.commit()

print("\n==================================================")
print(" ALL 16 STEP 8C REGRESSION TESTS PASSED 100%!   ")
print("==================================================")
