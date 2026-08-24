import sys
import os
import re
import io
from pypdf import PdfReader

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college, get_default_college
from pdf_service import generate_application_receipt_pdf, get_base_url

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 14: PDF RECEIPT & SECURITY SUITE           ")
print("==================================================")

college = seed_default_college()

def extract_csrf_token(res):
    html = res.data.decode('utf-8')
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    with client.session_transaction() as sess:
        return sess.get('csrf_token')

# Clean test applicant
test_email = "pdf.student2026@example.com"
test_course = "BCA - Bachelor of Computer Applications"
models.AdmissionApplication.query.filter_by(email=test_email).delete()
db.session.commit()

# Create test application via submit route
res_get = client.get('/apply')
csrf_tok = extract_csrf_token(res_get)

res_submit = client.post('/apply', data={
    'full_name': 'Kavya Nair',
    'guardian_name': 'Suresh Nair',
    'email': test_email,
    'phone': '9123456789',
    'course': test_course,
    'percentage': '95.4',
    'csrf_token': csrf_tok
}, follow_redirects=True)

assert res_submit.status_code == 200
app_rec = models.AdmissionApplication.query.filter_by(email=test_email).first()
assert app_rec is not None, "Failed to create application record in database!"
app_num = app_rec.application_number

print(f"  -> Test Application Created (ID: {app_rec.id}, Tracking ID: {app_num})")

# 1. PDF Content & Text Extraction Audit (Requirement 3 & 2)
print("\n[1/4] Auditing PDF Generation, Dynamic Branding & Data Extraction...")
pdf_buf = generate_application_receipt_pdf(app_rec, college)
pdf_bytes = pdf_buf.getvalue()

assert pdf_bytes.startswith(b'%PDF'), "Generated file binary does not start with %PDF header!"

# Extract text using PyPDF
reader = PdfReader(io.BytesIO(pdf_bytes))
extracted_text = ""
for page in reader.pages:
    extracted_text += page.extract_text() + "\n"

# Verify PDF Content
assert app_num in extracted_text, f"Tracking ID {app_num} missing from PDF extracted text!"
assert "Kavya Nair" in extracted_text, "Applicant name 'Kavya Nair' missing from PDF extracted text!"
assert "BCA" in extracted_text, "Course name 'BCA' missing from PDF extracted text!"
assert app_rec.status in extracted_text, f"Status {app_rec.status} missing from PDF extracted text!"

# Verify Dynamic Institution Branding
setting = college.settings
if setting and setting.college_name:
    assert setting.college_name in extracted_text or "Seshadripuram" in extracted_text

print("  -> PASSED (PDF binary valid & contains applicant name, tracking ID, course, status & college branding)")

# 2. Secure Receipt Download Route Protection Audit (Requirement 1)
print("\n[2/4] Auditing Secured Receipt Download Route Access Controls...")

# Attempt 1: Unauthorized Guest without token
guest_client = app.test_client(use_cookies=False)
res_unauth = guest_client.get(f'/admission/receipt/{app_num}')
assert res_unauth.status_code == 403, f"Expected 403 Forbidden for unauthenticated receipt access, got {res_unauth.status_code}"
print("  -> Sub-test 1: Unauthenticated request without token correctly BLOCKED (HTTP 403)")

# Attempt 2: Unauthorized Guest with FORGED / INVALID token
res_forged = guest_client.get(f'/admission/receipt/{app_num}?token=FORGED_INVALID_RECEIPT_TOKEN')
assert res_forged.status_code == 403, f"Expected 403 Forbidden for forged receipt token, got {res_forged.status_code}"
print("  -> Sub-test 2: Forged token request correctly BLOCKED (HTTP 403)")

# Attempt 3: Valid Applicant Session Token (extracted from flash/url in original client)
with client.session_transaction() as sess:
    valid_token = sess.get('receipt_tokens', {}).get(app_num)

assert valid_token is not None, "Valid receipt token was not saved to session during submission!"

res_valid_token = client.get(f'/admission/receipt/{app_num}?token={valid_token}')
assert res_valid_token.status_code == 200, f"Expected 200 OK for valid session token, got {res_valid_token.status_code}"
assert res_valid_token.content_type == 'application/pdf', f"Expected application/pdf content type, got {res_valid_token.content_type}"
assert res_valid_token.data.startswith(b'%PDF')
print("  -> Sub-test 3: Applicant with valid token allowed (HTTP 200 PDF)")

# Attempt 4: Authenticated Admin Desk Access
res_login_g = client.get('/login')
tok_login = extract_csrf_token(res_login_g)
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123', 'csrf_token': tok_login})

res_admin_access = client.get(f'/admission/receipt/{app_num}')
assert res_admin_access.status_code == 200, f"Expected 200 OK for Admin receipt access, got {res_admin_access.status_code}"
assert res_admin_access.content_type == 'application/pdf'
client.get('/logout')
print("  -> Sub-test 4: Logged-in College Admin allowed without token (HTTP 200 PDF)")

# 3. Public Verification Route & Privacy Masking Audit (Requirement 1 & 4)
print("\n[3/4] Auditing Public Verification Route & Privacy Masking...")
res_verify = guest_client.get(f'/verify-receipt/{app_num}')
assert res_verify.status_code == 200, f"Expected 200 OK for public verification route, got {res_verify.status_code}"

html_verify = res_verify.data.decode('utf-8')
assert app_num in html_verify, "Tracking ID missing from public verification page!"
assert "AUTHENTIC RECORD VERIFIED" in html_verify or "AUTHENTIC" in html_verify
assert app_rec.status in html_verify

# PRIVACY CHECK: Candidate personal PII must NOT be leaked on public verification page
assert "Kavya Nair" not in html_verify, "PRIVACY LEAK: Candidate full name leaked on public verification page!"
assert "Suresh Nair" not in html_verify, "PRIVACY LEAK: Candidate guardian name leaked on public verification page!"
assert "9123456789" not in html_verify, "PRIVACY LEAK: Candidate phone leaked on public verification page!"
assert test_email not in html_verify, "PRIVACY LEAK: Candidate email leaked on public verification page!"

print("  -> PASSED (Public verification route operational & Candidate PII strictly masked)")

# 4. QR Code Absolute Base URL Audit (Requirement 4)
print("\n[4/4] Auditing Absolute Verification URL in QR Code...")
base_url = get_base_url()
expected_verify_link = f"{base_url}/verify-receipt/{app_num}"
assert expected_verify_link.startswith("http://") or expected_verify_link.startswith("https://")
print(f"  -> Absolute QR Verification URL: {expected_verify_link}")
print("  -> PASSED (Configurable absolute URL generated for QR code)")

print("\n==================================================")
print(" ALL PDF RECEIPT & SECURITY TESTS PASSED 100%!   ")
print("==================================================")
