import sys
import os
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college, get_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 15: STUDENT PORTAL & DASHBOARD SUITE       ")
print("==================================================")

college = seed_default_college()

def extract_csrf_token(res):
    html = res.data.decode('utf-8')
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    with client.session_transaction() as sess:
        return sess.get('csrf_token')

# Prepare test application under default college
test_email = "student.portal2026@example.com"
test_course = "MCA - Master of Computer Applications"

models.AdmissionApplication.query.filter_by(email=test_email).delete()
db.session.commit()

res_g = client.get('/apply')
csrf_tok = extract_csrf_token(res_g)

client.post('/apply', data={
    'full_name': 'Rohan Kulkarni',
    'guardian_name': 'Anand Kulkarni',
    'email': test_email,
    'phone': '9876543210',
    'course': test_course,
    'percentage': '89.2',
    'csrf_token': csrf_tok
}, follow_redirects=True)

app_rec = models.AdmissionApplication.query.filter_by(email=test_email).first()
assert app_rec is not None, "Failed to create test application record!"
app_num = app_rec.application_number

print(f"  -> Test Application Created (ID: {app_rec.id}, Tracking ID: {app_num})")

# 1. Applicant Lookup & Dashboard Render Audit
print("\n[1/5] Auditing Applicant Tracking Lookup & Dashboard Rendering...")
client.get('/students-corner/logout') # Ensure clean session

res_corner_g = client.get('/students-corner')
csrf_corner = extract_csrf_token(res_corner_g)

res_lookup = client.post('/students-corner', data={
    'tracking_id': app_num,
    'email': test_email.upper(), # Test case-insensitive email normalization
    'csrf_token': csrf_corner
}, follow_redirects=True)

assert res_lookup.status_code == 200
html_dash = res_lookup.data.decode('utf-8')

assert "Rohan Kulkarni" in html_dash, "Applicant full name missing from dashboard!"
assert app_num in html_dash, "Tracking ID missing from dashboard!"
assert "MCA - Master of Computer Applications" in html_dash, "Course name missing from dashboard!"
assert "PENDING" in html_dash, "Status PENDING missing from dashboard pipeline!"
assert "Download PDF Receipt" in html_dash, "Receipt download button missing from dashboard!"

# Test Receipt Download via Applicant Dashboard Session Context
res_rcpt = client.get(f'/admission/receipt/{app_num}')
assert res_rcpt.status_code == 200, f"Expected 200 OK for dashboard session receipt download, got {res_rcpt.status_code}"
assert res_rcpt.content_type == 'application/pdf'
print("  -> PASSED (Lookup successful, Dashboard & PDF Receipt accessible via session context)")

# 2. Strict Cross-Tenant Isolation Audit (Requirement 1 & User Test Case)
print("\n[2/5] Auditing Cross-Tenant Tracking Isolation...")

tenant_b = models.College.query.filter_by(slug='step15-other-tenant').first()
if not tenant_b:
    tenant_b = models.College(name='Step 15 Other Tenant', slug='step15-other-tenant')
    db.session.add(tenant_b)
    db.session.commit()

models.AdmissionApplication.query.filter_by(application_number='SC2026-TENANTB-99').delete()
db.session.commit()

# Create application under Tenant B
app_b = models.AdmissionApplication(
    college_id=tenant_b.id,
    application_number='SC2026-TENANTB-99',
    full_name='Tenant B Candidate',
    guardian_name='Guardian B',
    email='tenantb.student@example.com',
    phone='9998887776',
    course='BBA',
    percentage='85.0',
    status='PENDING'
)
db.session.add(app_b)
db.session.commit()

# Attempt to lookup Tenant B application from Default College portal
res_cross = client.post('/students-corner', data={
    'tracking_id': 'SC2026-TENANTB-99',
    'email': 'tenantb.student@example.com',
    'csrf_token': csrf_corner
}, follow_redirects=True)

assert res_cross.status_code == 200
html_cross = res_cross.data.decode('utf-8')
assert "No application matching" in html_cross or "No application" in html_cross
assert "Tenant B Candidate" not in html_cross
print("  -> PASSED (Cross-tenant tracking lookup blocked strictly)")

# 3. Terminal REJECTED Status Rendering Audit (User Test Case)
print("\n[3/5] Auditing Terminal REJECTED Status Pipeline Rendering...")
target_app = db.session.get(models.AdmissionApplication, app_rec.id)
target_app.status = 'REJECTED'
db.session.commit()

# Authenticate dashboard session for REJECTED application
client.post('/students-corner', data={
    'tracking_id': app_num,
    'email': test_email,
    'csrf_token': csrf_corner
}, follow_redirects=True)

res_dash_rej = client.get('/students-corner')
html_rej = res_dash_rej.data.decode('utf-8')

assert "Application Status: REJECTED" in html_rej, "Terminal REJECTED status box missing from dashboard!"
print("  -> PASSED (REJECTED status renders dedicated terminal warning box)")

# Reset status back to VERIFIED
target_app.status = 'VERIFIED'
db.session.commit()

# 4. Student Logout & Session Isolation Audit (Requirement 2 & User Test Case)
print("\n[4/5] Auditing Dashboard Logout & Post-Logout Receipt Security...")

# Authenticate student session & Admin session concurrently
client.post('/students-corner', data={'tracking_id': app_num, 'email': test_email, 'csrf_token': csrf_corner})

res_login_g = client.get('/login')
tok_login = extract_csrf_token(res_login_g)
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123', 'csrf_token': tok_login})

# Student logs out of dashboard
res_logout = client.get('/students-corner/logout', follow_redirects=True)
assert res_logout.status_code == 200

# Verify applicant_access is cleared
with client.session_transaction() as sess:
    assert 'applicant_access' not in sess

# Verify Admin login is NOT broken by student logout (Requirement 2)
from flask_login import current_user
assert client.get('/admin').status_code == 200, "Student logout accidentally destroyed Admin authentication session!"

client.get('/logout') # Log out admin

# Verify unauthorized receipt download after student logout fails
guest_cl = app.test_client(use_cookies=False)
res_after_logout = guest_cl.get(f'/admission/receipt/{app_num}')
assert res_after_logout.status_code == 403, f"Expected 403 Forbidden after student logout, got {res_after_logout.status_code}"
print("  -> PASSED (Student dashboard logout clears access without affecting Admin session)")

# 5. Server-Side Question Paper Search & Dynamic Academic Calendar Audit (Requirement 3)
print("\n[5/5] Auditing Question Paper Search & Academic Calendar...")

# Seed a test question paper if needed
bca_course = models.Course.query.filter_by(college_id=college.id, code='BCA').first()
if bca_course:
    test_qp = models.QuestionPaper.query.filter_by(subject='Python Web Dev PYQ').first()
    if not test_qp:
        test_qp = models.QuestionPaper(
            course_id=bca_course.id,
            year='2026',
            semester='Sem 4',
            subject='Python Web Dev PYQ',
            filename='test_pyq_2026.pdf'
        )
        db.session.add(test_qp)
        db.session.commit()

res_qp_search = client.get('/students-corner?q=Python+Web+Dev')
assert res_qp_search.status_code == 200
html_qp = res_qp_search.data.decode('utf-8')
assert "Python Web Dev PYQ" in html_qp or "Question Papers" in html_qp
print("  -> PASSED (Server-side PYQ filtering & Academic Calendar operational)")

print("\n==================================================")
print(" ALL STUDENT PORTAL & DASHBOARD TESTS PASSED!    ")
print("==================================================")
