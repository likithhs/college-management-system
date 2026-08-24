import sys
import os
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college, get_default_college
from email_service import mail_outbox, clear_outbox, send_applicant_confirmation_email

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 13: EMAIL NOTIFICATION SYSTEM SUITE        ")
print("==================================================")

college = seed_default_college()

def extract_csrf_token(res):
    html = res.data.decode('utf-8')
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    with client.session_transaction() as sess:
        return sess.get('csrf_token')

# 1. Application Submission Email Notifications
print("\n[1/4] Auditing Application Submission Email Triggers & Outbox...")
clear_outbox()

test_email = "ananya.sharma2026@example.com"
test_course = "BCA - Bachelor of Computer Applications"

# Ensure test application isolation
models.AdmissionApplication.query.filter_by(email=test_email, course=test_course).delete()
db.session.commit()

# Initialize session & token
res_get = client.get('/apply')
csrf_tok = extract_csrf_token(res_get)

res_post = client.post('/apply', data={
    'full_name': 'Ananya Sharma',
    'guardian_name': 'Ramesh Sharma',
    'email': test_email,
    'phone': '9876543210',
    'course': test_course,
    'percentage': '92.5',
    'csrf_token': csrf_tok
}, follow_redirects=True)

assert res_post.status_code == 200, f"Expected 200 OK, got {res_post.status_code}"

# Verify DB Record
app_rec = models.AdmissionApplication.query.filter_by(email=test_email, course=test_course).first()
assert app_rec is not None, "AdmissionApplication record was not saved to database!"
print(f"  -> DB Record verified (ID: {app_rec.id}, Tracking ID: {app_rec.application_number})")

# Verify Mail Outbox (Expect 2 emails: Student Confirmation + Admin Alert)
assert len(mail_outbox) == 2, f"Expected 2 emails in outbox, got {len(mail_outbox)}"

student_mail = next((m for m in mail_outbox if m.type == 'applicant_confirmation'), None)
admin_mail = next((m for m in mail_outbox if m.type == 'admin_notification'), None)

assert student_mail is not None, "Applicant confirmation email missing from outbox!"
assert admin_mail is not None, "Admin notification email missing from outbox!"

assert test_email in student_mail.recipients, f"Expected recipient {test_email}, got {student_mail.recipients}"
assert app_rec.application_number in student_mail.subject, "Tracking ID missing from applicant email subject!"
assert "Ananya Sharma" in student_mail.body or "Ananya Sharma" in (student_mail.html or ''), "Student name missing from applicant email!"

admin_contact_email = (college.settings.email_info if college.settings else None) or 'admin@spmcollege.ac.in'
assert admin_contact_email in admin_mail.recipients or 'admin@spmcollege.ac.in' in admin_mail.recipients
assert app_rec.application_number in admin_mail.subject, "Tracking ID missing from admin email subject!"

print("  -> PASSED (Student confirmation & Admin alert emails correctly formatted & captured in mail_outbox)")

# 2. Application Status Update Email Notifications
print("\n[2/4] Auditing Status Transition Email Triggers...")

# Log in as Admin
res_login_g = client.get('/login')
tok_login = extract_csrf_token(res_login_g)
client.post('/login', data={
    'email': 'admin@spmcollege.ac.in',
    'password': 'CollegeAdmin@123',
    'csrf_token': tok_login
})

transitions = [
    ('PENDING', 'UNDER_REVIEW'),
    ('UNDER_REVIEW', 'VERIFIED'),
    ('VERIFIED', 'SEAT_LOCKED')
]

for current_s, next_s in transitions:
    clear_outbox()
    res_adm = client.get('/admin')
    tok_adm = extract_csrf_token(res_adm)
    
    res_status = client.post(f'/admin/admission/status/{app_rec.id}', data={
        'status': next_s,
        'csrf_token': tok_adm
    }, follow_redirects=True)
    
    assert res_status.status_code == 200
    
    # Check DB
    updated_rec = db.session.get(models.AdmissionApplication, app_rec.id)
    assert updated_rec.status == next_s, f"DB status failed to update to {next_s}"
    
    # Check Outbox
    assert len(mail_outbox) == 1, f"Expected 1 status update email for {current_s} -> {next_s}, got {len(mail_outbox)}"
    status_mail = mail_outbox[0]
    assert test_email in status_mail.recipients
    assert next_s in status_mail.body or next_s in (status_mail.html or '') or next_s.replace('_', ' ') in status_mail.subject
    print(f"  -> Transition {current_s} -> {next_s}: Email verified in outbox")

client.get('/logout')

# 3. Unchanged Status Duplicate Email Protection
print("\n[3/4] Testing Unchanged Status Duplicate Email Prevention...")
clear_outbox()

# Re-login as Admin
res_login_g2 = client.get('/login')
tok_login2 = extract_csrf_token(res_login_g2)
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123', 'csrf_token': tok_login2})

res_adm2 = client.get('/admin')
tok_adm2 = extract_csrf_token(res_adm2)

# Attempt to update to same status (SEAT_LOCKED -> SEAT_LOCKED)
res_same = client.post(f'/admin/admission/status/{app_rec.id}', data={
    'status': 'SEAT_LOCKED',
    'csrf_token': tok_adm2
}, follow_redirects=True)

assert res_same.status_code == 200
assert len(mail_outbox) == 0, f"Expected 0 emails for unchanged status, got {len(mail_outbox)}"
print("  -> PASSED (Zero duplicate emails sent when status remains unchanged)")

client.get('/logout')

# 4. SMTP Exception & Failure Resilience Test
print("\n[4/4] Auditing SMTP Failure Resilience...")

# We will temporarily replace _dispatch_email with a function that throws an error
import email_service

models.AdmissionApplication.query.filter_by(email='resilience.test@example.com').delete()
db.session.commit()

original_dispatch = email_service._dispatch_email

def broken_dispatch(*args, **kwargs):
    raise RuntimeError("Simulated SMTP Transport Connection Exception!")

email_service._dispatch_email = broken_dispatch

try:
    res_get3 = client.get('/apply')
    tok3 = extract_csrf_token(res_get3)
    
    res_fail_test = client.post('/apply', data={
        'full_name': 'Resilience Candidate',
        'guardian_name': 'Parent Name',
        'email': 'resilience.test@example.com',
        'phone': '9988776655',
        'course': 'BBA - Bachelor of Business Administration',
        'percentage': '88.0',
        'csrf_token': tok3
    }, follow_redirects=True)
    
    # Must return HTTP 200 and flash success, NOT crash with 500
    assert res_fail_test.status_code == 200, f"Submission crashed with status code {res_fail_test.status_code}"
    
    # DB Record MUST still exist
    saved_resilient = models.AdmissionApplication.query.filter_by(email='resilience.test@example.com').first()
    assert saved_resilient is not None, "Application submission failed to save to database when email dispatch failed!"
    assert saved_resilient.application_number.startswith('SC')
    print("  -> PASSED (Database submission succeeded seamlessly despite SMTP transport exception)")

finally:
    # Restore original dispatch
    email_service._dispatch_email = original_dispatch

print("\n==================================================")
print(" ALL EMAIL NOTIFICATION & OUTBOX TESTS PASSED!   ")
print("==================================================")
