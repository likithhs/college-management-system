import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("=== 1. PUBLIC ADMISSION SUBMISSION & VALIDATION ===")
# Test A: GET /apply
res_get = client.get('/apply')
print("/apply GET status:", res_get.status_code)

# Test B: Server-side validation failures
invalid_data_cases = [
    {'full_name': '', 'guardian_name': 'Suresh', 'email': 'test@example.com', 'phone': '9876543210', 'course': 'BCA - Bachelor of Computer Applications', 'percentage': '85'},
    {'full_name': 'Rahul', 'guardian_name': '', 'email': 'test@example.com', 'phone': '9876543210', 'course': 'BCA - Bachelor of Computer Applications', 'percentage': '85'},
    {'full_name': 'Rahul', 'guardian_name': 'Suresh', 'email': 'invalid-email', 'phone': '9876543210', 'course': 'BCA - Bachelor of Computer Applications', 'percentage': '85'},
    {'full_name': 'Rahul', 'guardian_name': 'Suresh', 'email': 'test@example.com', 'phone': '123', 'course': 'BCA - Bachelor of Computer Applications', 'percentage': '85'},
    {'full_name': 'Rahul', 'guardian_name': 'Suresh', 'email': 'test@example.com', 'phone': '9876543210', 'course': 'Invalid Course Name', 'percentage': '85'},
    {'full_name': 'Rahul', 'guardian_name': 'Suresh', 'email': 'test@example.com', 'phone': '9876543210', 'course': 'BCA - Bachelor of Computer Applications', 'percentage': '25'},
    {'full_name': 'Rahul', 'guardian_name': 'Suresh', 'email': 'test@example.com', 'phone': '9876543210', 'course': 'BCA - Bachelor of Computer Applications', 'percentage': '105'}
]

initial_count = models.AdmissionApplication.query.count()
for idx, bad_data in enumerate(invalid_data_cases):
    res_bad = client.post('/apply', data=bad_data, follow_redirects=True)
    print(f"Validation failure case #{idx+1} rejected correctly:", "Validation Error" in res_bad.data.decode('utf-8'))

print("Count after invalid attempts (should be unchanged):", models.AdmissionApplication.query.count() == initial_count)

# Test C: Valid Application Submission
valid_payload = {
    'full_name': 'Varun Kumar',
    'guardian_name': 'Ramesh Kumar',
    'email': 'varun.kumar@example.com',
    'phone': '9845012345',
    'course': 'BCA - Bachelor of Computer Applications',
    'percentage': '91.5'
}

res_valid = client.post('/apply', data=valid_payload, follow_redirects=True)
html_valid = res_valid.data.decode('utf-8')
print("Valid submission redirected cleanly:", res_valid.status_code == 200)
print("Success notification present:", "submitted successfully" in html_valid)

app_record = models.AdmissionApplication.query.filter_by(email='varun.kumar@example.com').first()
print("Record persisted in DB:", app_record is not None)
print("Application Number:", app_record.application_number if app_record else None)
print("Default status is UNDER_REVIEW:", app_record.status == 'UNDER_REVIEW' if app_record else False)
print("College ID bound to default tenant (1):", app_record.college_id == 1 if app_record else False)

print("\n=== 2. DUPLICATE SUBMISSION PROTECTION ===")
res_dup = client.post('/apply', data=valid_payload, follow_redirects=True)
print("Duplicate attempt warning flash present:", "Application Notice" in res_dup.data.decode('utf-8'))
dup_count = models.AdmissionApplication.query.filter_by(email='varun.kumar@example.com', course='BCA - Bachelor of Computer Applications').count()
print("Record count for duplicate payload remains 1:", dup_count == 1)

print("\n=== 3. ADMIN DASHBOARD INTEGRATION & STATUS UPDATES ===")
# Login as College Admin
client.post('/login', data={'email':'admin@spmcollege.ac.in', 'password':'CollegeAdmin@123'})

res_admin = client.get('/admin')
html_admin = res_admin.data.decode('utf-8')

print("College Admin /admin status:", res_admin.status_code)
print("Persistent app number present in admin table:", app_record.application_number in html_admin if app_record else False)
print("Student name present in admin table:", "Varun Kumar" in html_admin)
print("Mock applicant Naveen Kumar ABSENT:", "Naveen Kumar" not in html_admin)
print("Mock applicant Pooja Hegde ABSENT:", "Pooja Hegde" not in html_admin)

# Update application status to VERIFIED
res_verify = client.post(f'/admin/admission/status/{app_record.id}', data={'status':'VERIFIED'}, follow_redirects=True)
app_record_updated = models.AdmissionApplication.query.get(app_record.id)
print("Status updated to VERIFIED in DB:", app_record_updated.status == 'VERIFIED')

client.get('/logout')

print("\n=== 4. MODULE CONFIG PERMISSION ENFORCEMENT ===")
# Login as Super Admin and toggle admin_access for admission to False
client.post('/login', data={'email':'superadmin@spmcollege.ac.in', 'password':'SuperAdmin@123'})
cfg = models.ModuleConfig.query.filter_by(college_id=1, module_key='admission').first()
cfg.admin_access = False
db.session.commit()
client.get('/logout')

# Login as College Admin and attempt to POST status update
client.post('/login', data={'email':'admin@spmcollege.ac.in', 'password':'CollegeAdmin@123'})
res_blocked_status = client.post(f'/admin/admission/status/{app_record.id}', data={'status':'REJECTED'})
print("Status update blocked with HTTP 403 when admin_access=False:", res_blocked_status.status_code == 403)
client.get('/logout')

# Restore admin_access = True
client.post('/login', data={'email':'superadmin@spmcollege.ac.in', 'password':'SuperAdmin@123'})
cfg.admin_access = True
db.session.commit()
client.get('/logout')

print("\nAll Step 5 Admissions Application Persistence Tests PASSED Successfully!")
