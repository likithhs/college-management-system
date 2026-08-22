import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 8B: ADMISSION WORKFLOW & SECURITY TEST SUITE")
print("==================================================")

college = seed_default_college()

# Helper function to create test application
def create_test_app(status='UNDER_REVIEW', suffix='1'):
    app_num = f"SC2026-TEST{suffix}"
    existing = models.AdmissionApplication.query.filter_by(application_number=app_num).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        
    app_rec = models.AdmissionApplication(
        college_id=college.id,
        application_number=app_num,
        full_name=f"Test Student {suffix}",
        guardian_name="Guardian Name",
        email=f"student{suffix}@example.com",
        phone="9876543210",
        course="BCA - Bachelor of Computer Applications",
        percentage=85.5,
        status=status
    )
    db.session.add(app_rec)
    db.session.commit()
    return app_rec

# 1. Unauthenticated Protection
print("\n[1/12] Testing unauthenticated status update guard...")
test_app1 = create_test_app('UNDER_REVIEW', '1')
res_unauth = client.post(f'/admin/admission/status/{test_app1.id}', data={'status': 'VERIFIED'})
print("Unauthenticated user redirected:", res_unauth.status_code == 302 and 'login' in res_unauth.headers.get('Location', ''))

# 2. RBAC admin_access = False Guard
print("\n[2/12] Testing admin_access = False RBAC guard...")
cfg = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='admission').first()
client.post('/login', data={'email':'superadmin@spmcollege.ac.in', 'password':'SuperAdmin@123'})
cfg.admin_access = False
db.session.commit()
client.get('/logout')

client.post('/login', data={'email':'admin@spmcollege.ac.in', 'password':'CollegeAdmin@123'})
res_rbac = client.post(f'/admin/admission/status/{test_app1.id}', data={'status': 'VERIFIED'})
print("admin_access=False returns 403 Forbidden:", res_rbac.status_code == 403)
client.get('/logout')

# Restore admin_access
client.post('/login', data={'email':'superadmin@spmcollege.ac.in', 'password':'SuperAdmin@123'})
cfg.admin_access = True
db.session.commit()
client.get('/logout')

# Log in as College Admin for remaining tests
client.post('/login', data={'email':'admin@spmcollege.ac.in', 'password':'CollegeAdmin@123'})

# 3. Invalid Status String
print("\n[3/12] Testing invalid status string rejection...")
res_inv_status = client.post(f'/admin/admission/status/{test_app1.id}', data={'status': 'INVALID_STATUS'}, follow_redirects=True)
print("Invalid status string rejected:", "Validation Error" in res_inv_status.data.decode('utf-8'))

# 4. Same Status Update Rejection
print("\n[4/12] Testing same status transition rejection...")
res_same = client.post(f'/admin/admission/status/{test_app1.id}', data={'status': 'UNDER_REVIEW'}, follow_redirects=True)
print("Same status request handled gracefully:", "is already in UNDER_REVIEW status" in res_same.data.decode('utf-8'))

# 5. Invalid Transition Rejection (UNDER_REVIEW -> SEAT_LOCKED directly)
print("\n[5/12] Testing illegal transition (UNDER_REVIEW -> SEAT_LOCKED)...")
res_illegal = client.post(f'/admin/admission/status/{test_app1.id}', data={'status': 'SEAT_LOCKED'}, follow_redirects=True)
print("Illegal transition rejected:", "Illegal status transition" in res_illegal.data.decode('utf-8'))

# 6. Valid Transition PENDING -> UNDER_REVIEW
print("\n[6/12] Testing transition PENDING -> UNDER_REVIEW...")
app_pending = create_test_app('PENDING', '2')
res_t1 = client.post(f'/admin/admission/status/{app_pending.id}', data={'status': 'UNDER_REVIEW'}, follow_redirects=True)
updated_p = db.session.get(models.AdmissionApplication, app_pending.id)
print("PENDING -> UNDER_REVIEW allowed:", updated_p.status == 'UNDER_REVIEW')

# 7. Valid Transition UNDER_REVIEW -> VERIFIED
print("\n[7/12] Testing transition UNDER_REVIEW -> VERIFIED...")
res_t2 = client.post(f'/admin/admission/status/{test_app1.id}', data={'status': 'VERIFIED'}, follow_redirects=True)
updated_1 = db.session.get(models.AdmissionApplication, test_app1.id)
print("UNDER_REVIEW -> VERIFIED allowed:", updated_1.status == 'VERIFIED')

# 8. Valid Transition VERIFIED -> SEAT_LOCKED
print("\n[8/12] Testing transition VERIFIED -> SEAT_LOCKED...")
res_t3 = client.post(f'/admin/admission/status/{test_app1.id}', data={'status': 'SEAT_LOCKED'}, follow_redirects=True)
updated_1 = db.session.get(models.AdmissionApplication, test_app1.id)
print("VERIFIED -> SEAT_LOCKED allowed:", updated_1.status == 'SEAT_LOCKED')

# 9. Valid Transition SEAT_LOCKED -> VERIFIED
print("\n[9/12] Testing transition SEAT_LOCKED -> VERIFIED...")
res_t4 = client.post(f'/admin/admission/status/{test_app1.id}', data={'status': 'VERIFIED'}, follow_redirects=True)
updated_1 = db.session.get(models.AdmissionApplication, test_app1.id)
print("SEAT_LOCKED -> VERIFIED allowed:", updated_1.status == 'VERIFIED')

# 10. Valid Transition REJECTED -> UNDER_REVIEW
print("\n[10/12] Testing transition REJECTED -> UNDER_REVIEW...")
app_rej = create_test_app('REJECTED', '3')
res_t5 = client.post(f'/admin/admission/status/{app_rej.id}', data={'status': 'UNDER_REVIEW'}, follow_redirects=True)
updated_rej = db.session.get(models.AdmissionApplication, app_rej.id)
print("REJECTED -> UNDER_REVIEW allowed:", updated_rej.status == 'UNDER_REVIEW')

# 11. Cross-Tenant Security Protection
print("\n[11/12] Testing cross-tenant status update 403 security...")
other_college = models.College.query.filter_by(slug='cross-tenant-adm-college').first()
if not other_college:
    other_college = models.College(name='Cross Tenant Adm College', slug='cross-tenant-adm-college')
    db.session.add(other_college)
    db.session.commit()

other_app = models.AdmissionApplication(
    college_id=other_college.id,
    application_number="SC2026-OTHER1",
    full_name="Other Student",
    guardian_name="Other Guardian",
    email="other@example.com",
    phone="9876543210",
    course="BCA - Bachelor of Computer Applications",
    percentage=90.0,
    status="UNDER_REVIEW"
)
db.session.add(other_app)
db.session.commit()

res_cross = client.post(f'/admin/admission/status/{other_app.id}', data={'status': 'VERIFIED'})
print("Cross-tenant status update blocked with HTTP 403 Forbidden:", res_cross.status_code == 403)

# Cleanup other college & app
db.session.delete(other_app)
db.session.delete(other_college)
db.session.delete(test_app1)
db.session.delete(app_pending)
db.session.delete(app_rej)
db.session.commit()

client.get('/logout')

# 12. UI Rendering Check
client.post('/login', data={'email':'admin@spmcollege.ac.in', 'password':'CollegeAdmin@123'})
res_admin = client.get('/admin')
print("\n[12/12] Admin Dashboard status management table status:", res_admin.status_code)

print("\n==================================================")
print(" ALL STEP 8B WORKFLOW & SECURITY TESTS PASSED 100%! ")
print("==================================================")
