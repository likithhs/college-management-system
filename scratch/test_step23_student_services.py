import sys
import os
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college
from pdf_service import generate_provisional_admission_letter

app.app_context().push()
db.create_all()
client = app.test_client(use_cookies=True)

print("==================================================")
print(" STEP 23: ADVANCED STUDENT SERVICES & DIGITAL CAMPUS ")
print("==================================================")

college = seed_default_college()

def extract_csrf_token(res):
    html = res.data.decode('utf-8')
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    with client.session_transaction() as sess:
        return sess.get('csrf_token')

# [1/14] Provisional Admission Letter PDF Generation Unit Test
print("\n[1/14] Auditing Provisional Admission Letter PDF Generation...")
app_verif = models.AdmissionApplication.query.filter_by(application_number='SC2026-STEP23A').first()
if not app_verif:
    app_verif = models.AdmissionApplication(
        college_id=college.id,
        application_number='SC2026-STEP23A',
        full_name='Aarav Sharma',
        guardian_name='Rajesh Sharma',
        email='aarav.sharma@example.com',
        phone='+91 9876543210',
        course='BCA',
        percentage=92.5,
        status='VERIFIED'
    )
    db.session.add(app_verif)
    db.session.commit()

pdf_buf = generate_provisional_admission_letter(app_verif, college)
pdf_bytes = pdf_buf.getvalue()
assert pdf_bytes.startswith(b'%PDF'), "Generated Provisional Admission Letter is not a valid PDF binary!"
print("  -> PASSED (Provisional Admission Letter PDF binary generated successfully)")

# [2/14] Access Control - Unauthenticated Applicant Attempt Blocked
print("\n[2/14] Auditing Access Control: Unauthenticated Request Blocked...")
res_unauth = client.get(f'/admission/provisional-letter/{app_verif.application_number}')
assert res_unauth.status_code == 403
print("  -> PASSED (Unauthenticated request strictly returned HTTP 403 Forbidden)")

# [3/14] Access Control - Applicant Session Access & PDF Download
print("\n[3/14] Auditing Applicant Session Verification & PDF Receipt Download...")
res_corner_g = client.get('/students-corner')
tok_corner = extract_csrf_token(res_corner_g)

res_login = client.post('/students-corner', data={
    'tracking_id': app_verif.application_number,
    'email': 'aarav.sharma@example.com',
    'csrf_token': tok_corner
}, follow_redirects=True)
assert res_login.status_code == 200

# Download Provisional Letter in valid session
res_pdf_app = client.get(f'/admission/provisional-letter/{app_verif.application_number}')
assert res_pdf_app.status_code == 200
assert res_pdf_app.mimetype == 'application/pdf'
assert res_pdf_app.data.startswith(b'%PDF')
print("  -> PASSED (Authenticated applicant downloaded Provisional Admission Letter PDF)")

# [4/14] Applicant Session Ownership Isolation
print("\n[4/14] Auditing Session Ownership Isolation (Applicant A cannot download Applicant B's letter)...")
app_verif_b = models.AdmissionApplication.query.filter_by(application_number='SC2026-STEP23B').first()
if not app_verif_b:
    app_verif_b = models.AdmissionApplication(
        college_id=college.id,
        application_number='SC2026-STEP23B',
        full_name='Bhavya Patel',
        guardian_name='Suresh Patel',
        email='bhavya.patel@example.com',
        phone='+91 9876543211',
        course='BBA',
        percentage=88.0,
        status='SEAT_LOCKED'
    )
    db.session.add(app_verif_b)
    db.session.commit()

# Current session belongs to Applicant A (Aarav Sharma). Try downloading Applicant B's letter.
res_cross_pdf = client.get(f'/admission/provisional-letter/{app_verif_b.application_number}')
assert res_cross_pdf.status_code == 403
print("  -> PASSED (Applicant A downloading Applicant B's letter strictly returned 403 Forbidden)")

# [5/14] Invalid Status Rejection (PENDING / UNDER_REVIEW / REJECTED)
print("\n[5/14] Auditing Invalid Application Status Rejection...")
app_pending = models.AdmissionApplication.query.filter_by(application_number='SC2026-PENDING').first()
if not app_pending:
    app_pending = models.AdmissionApplication(
        college_id=college.id,
        application_number='SC2026-PENDING',
        full_name='Pending Student',
        guardian_name='Guardian P',
        email='pending@example.com',
        phone='9988776655',
        course='BCA',
        percentage=75.0,
        status='PENDING'
    )
    db.session.add(app_pending)
    db.session.commit()

# Authenticate as pending student
client.post('/students-corner', data={
    'tracking_id': app_pending.application_number,
    'email': 'pending@example.com',
    'csrf_token': tok_corner
}, follow_redirects=True)

res_pending_pdf = client.get(f'/admission/provisional-letter/{app_pending.application_number}')
assert res_pending_pdf.status_code == 403
print("  -> PASSED (Pending application letter request strictly returned 403 Forbidden)")

# Re-authenticate as Applicant A
client.post('/students-corner', data={
    'tracking_id': app_verif.application_number,
    'email': 'aarav.sharma@example.com',
    'csrf_token': tok_corner
}, follow_redirects=True)

# [6/14] Document Request Submission from Session Context
print("\n[6/14] Auditing Student Document Request Submission...")
models.StudentDocumentRequest.query.filter_by(application_number=app_verif.application_number).delete()
db.session.commit()

tok_corner2 = extract_csrf_token(client.get('/students-corner'))
res_doc_sub = client.post('/students-corner/document-request', data={
    'document_type': 'Bonafide Certificate',
    'reason': 'Passport application verification at RPO',
    'csrf_token': tok_corner2
}, follow_redirects=True)
assert res_doc_sub.status_code == 200

doc_req = models.StudentDocumentRequest.query.filter_by(application_number=app_verif.application_number).first()
assert doc_req is not None
assert doc_req.student_name == app_verif.full_name # Derived strictly from session!
assert doc_req.status == 'PENDING'
print("  -> PASSED (Student document request submitted & applicant identity populated from session)")

# [7/14] Admin Status Update with Remarks & Notification
print("\n[7/14] Auditing Admin Document Request Status Transition...")
client.get('/student-logout') # Logout applicant session

res_login_g = client.get('/login')
tok_login = extract_csrf_token(res_login_g)
client.post('/login', data={
    'email': 'admin@spmcollege.ac.in',
    'password': 'CollegeAdmin@123',
    'csrf_token': tok_login
}, follow_redirects=True)

tok_admin = extract_csrf_token(client.get('/admin'))

res_admin_status = client.post(f'/admin/document-request/status/{doc_req.id}', data={
    'status': 'ISSUED',
    'admin_remarks': 'Approved and issued by Registrar Desk.',
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_admin_status.status_code == 200

db.session.refresh(doc_req)
assert doc_req.status == 'ISSUED'
assert doc_req.admin_remarks == 'Approved and issued by Registrar Desk.'
print("  -> PASSED (Admin updated document request status to ISSUED with remarks)")

# [8/14] Invalid Status Validation on Document Requests
print("\n[8/14] Auditing Invalid Status Rejection on Document Requests...")
res_inv_status = client.post(f'/admin/document-request/status/{doc_req.id}', data={
    'status': 'HACKED_STATUS',
    'csrf_token': tok_admin
}, follow_redirects=True)
assert "Invalid document request status" in res_inv_status.data.decode('utf-8')
print("  -> PASSED (Invalid status 'HACKED_STATUS' rejected)")

# [9/14] Event Registration & Unique Code Generation
print("\n[9/14] Auditing Campus Event Registration & Code Generation...")
models.EventRegistration.query.filter_by(college_id=college.id).delete()
db.session.commit()

event1 = models.CampusEvent.query.filter_by(college_id=college.id).first()
if not event1:
    event1 = models.CampusEvent(
        college_id=college.id,
        title='Annual Tech Symposium 2026',
        date_display='15 Nov 2026',
        day='15',
        month='NOV',
        category='Hackathon',
        description='24-hour coding competition and tech keynote'
    )
    db.session.add(event1)
    db.session.commit()

res_event_reg1 = client.post(f'/events/register/{event1.id}', data={
    'participant_name': 'Rohan Das',
    'participant_email': 'rohan.das@example.com',
    'participant_phone': '+91 9911223344',
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_event_reg1.status_code == 200

reg1 = models.EventRegistration.query.filter_by(participant_email='rohan.das@example.com').first()
assert reg1 is not None
assert reg1.registration_code.startswith('EVT-')
print("  -> PASSED (Event registration succeeded & unique code 'EVT-...' generated)")

# [10/14] Registration Code Uniqueness Test
print("\n[10/14] Auditing Registration Code Uniqueness...")
res_event_reg2 = client.post(f'/events/register/{event1.id}', data={
    'participant_name': 'Sneha Rao',
    'participant_email': 'sneha.rao@example.com',
    'participant_phone': '+91 9911223355',
    'csrf_token': tok_admin
}, follow_redirects=True)

reg2 = models.EventRegistration.query.filter_by(participant_email='sneha.rao@example.com').first()
assert reg2 is not None
assert reg1.registration_code != reg2.registration_code
print("  -> PASSED (Multiple event registrations generated distinct registration codes)")

# [11/14] Duplicate Registration Prevention
print("\n[11/14] Auditing Duplicate Event Registration Prevention...")
res_dup_reg = client.post(f'/events/register/{event1.id}', data={
    'participant_name': 'Rohan Das Duplicate',
    'participant_email': 'rohan.das@example.com',
    'participant_phone': '+91 9911223344',
    'csrf_token': tok_admin
}, follow_redirects=True)
assert "already registered" in res_dup_reg.data.decode('utf-8')
print("  -> PASSED (Duplicate registration attempt for same email rejected)")

# [12/14] Event Registration Verification Route
print("\n[12/14] Auditing Event Registration Verification Route...")
res_verif_evt = client.get(f'/verify-event-registration/{reg1.registration_code}')
assert res_verif_evt.status_code == 200
html_evt = res_verif_evt.data.decode('utf-8')
assert 'EVENT REGISTRATION PASS' in html_evt or 'Event Registration Pass' in html_evt
assert 'rohan.das@example.com' not in html_evt # Masked email PII protection!
print("  -> PASSED (Event registration verification page rendered with masked PII)")

# [13/14] Cross-Tenant Isolation Audit
print("\n[13/14] Auditing Cross-Tenant Isolation on Document Requests...")
tenant_b = models.College.query.filter_by(slug='step23-tenant-b').first()
if not tenant_b:
    tenant_b = models.College(name='Step23 Tenant B', slug='step23-tenant-b')
    db.session.add(tenant_b)
    db.session.commit()

doc_b = models.StudentDocumentRequest(
    college_id=tenant_b.id,
    application_number='TB-APP-101',
    student_name='Tenant B Student',
    email='tb.student@example.com',
    document_type='Bonafide Certificate',
    reason='Test reason',
    status='PENDING'
)
db.session.add(doc_b)
db.session.commit()

# Current admin belongs to Tenant A. Attempt modifying Tenant B's doc request status.
res_cross_doc = client.post(f'/admin/document-request/status/{doc_b.id}', data={
    'status': 'ISSUED',
    'csrf_token': tok_admin
})
assert res_cross_doc.status_code == 404
print("  -> PASSED (Cross-tenant document status update strictly returned 404 Not Found)")

# [14/14] Cleanup Test Records
print("\n[14/14] Cleaning Up Temporary Test Records...")
models.AdmissionApplication.query.filter_by(college_id=college.id).delete()
models.StudentDocumentRequest.query.filter_by(college_id=college.id).delete()
models.StudentDocumentRequest.query.filter_by(college_id=tenant_b.id).delete()
models.EventRegistration.query.filter_by(college_id=college.id).delete()
db.session.commit()
print("  -> PASSED (Temporary test records cleaned up)")

print("\n==================================================")
print(" ALL 14 STEP 23 STUDENT SERVICES TESTS PASSED!   ")
print("==================================================")
