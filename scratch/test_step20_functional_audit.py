import sys
import os
import re
import io
import uuid
from pathlib import Path
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models, get_tenant_upload_dir, safe_delete_tenant_file
from seed import seed_default_college

app.app_context().push()
db.create_all()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 20: COMPLETE FUNCTIONAL & NAVIGATION SUITE ")
print("==================================================")

college = seed_default_college()

def extract_csrf_token(res):
    html = res.data.decode('utf-8')
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    with client.session_transaction() as sess:
        return sess.get('csrf_token')

# [1/15] Public Visitor Journey Audit
print("\n[1/15] Auditing Public Visitor Journey & Pages...")
public_pages = [
    '/', '/about', '/departments', '/facilities', '/placements',
    '/gallery', '/forum', '/contact', '/apply', '/students-corner'
]

for p in public_pages:
    res = client.get(p)
    assert res.status_code == 200, f"Public page {p} returned status {res.status_code}"

print(f"  -> PASSED (Audited {len(public_pages)} public visitor pages; all returned HTTP 200 OK)")

# [2/15] Template Navigation & url_for Link Audit
print("\n[2/15] Auditing Template url_for Links & Navigation Targets...")
endpoint_names = set(app.view_functions.keys())
url_for_pattern = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]")

broken_endpoints = set()
for tmpl_file in os.listdir(os.path.join(app.root_path, 'templates')):
    if tmpl_file.endswith('.html'):
        with open(os.path.join(app.root_path, 'templates', tmpl_file), 'r', encoding='utf-8') as f:
            content = f.read()
            matches = url_for_pattern.findall(content)
            for ep in matches:
                if ep != 'static' and ep not in endpoint_names:
                    broken_endpoints.add((tmpl_file, ep))

assert len(broken_endpoints) == 0, f"Found broken url_for references in templates: {broken_endpoints}"
print("  -> PASSED (All template url_for references match registered Flask endpoints)")

# [3/15] Applicant Submission Journey
print("\n[3/15] Auditing Applicant Online Application Submission Journey...")
sub_email = "student.step20@example.com"
models.AdmissionApplication.query.filter_by(email=sub_email).delete()
models.Notification.query.filter_by(recipient_email=sub_email).delete()
db.session.commit()

res_apply_g = client.get('/apply')
tok_apply = extract_csrf_token(res_apply_g)

res_sub = client.post('/apply', data={
    'full_name': 'Step20 Applicant',
    'guardian_name': 'Guardian Step20',
    'email': sub_email,
    'phone': '9988112233',
    'course': 'BCA',
    'percentage': '91.5',
    'csrf_token': tok_apply
}, follow_redirects=True)
assert res_sub.status_code == 200

app_rec = models.AdmissionApplication.query.filter_by(email=sub_email).first()
assert app_rec is not None
app_num = app_rec.application_number

# Verify notification triggers
notif_rec = models.Notification.query.filter_by(recipient_email=sub_email, application_number=app_num).first()
assert notif_rec is not None
print("  -> PASSED (Application submitted, DB record created, and notifications triggered)")

# [4/15] Applicant Tracking & Session Journey
print("\n[4/15] Auditing Applicant Tracking & Session Context...")
res_corner_g = client.get('/students-corner')
tok_corner = extract_csrf_token(res_corner_g)

res_lookup = client.post('/students-corner', data={
    'tracking_id': app_num,
    'email': sub_email,
    'csrf_token': tok_corner
}, follow_redirects=True)
assert res_lookup.status_code == 200
assert "Step20 Applicant" in res_lookup.data.decode('utf-8')
print("  -> PASSED (Applicant tracking lookup succeeded & session context established)")

# [5/15] Applicant Receipt PDF & Notification Journey
print("\n[5/15] Auditing Applicant Receipt PDF & Notification Endpoints...")
with client.session_transaction() as sess:
    receipt_tokens = sess.get('receipt_tokens', {})
    valid_token = receipt_tokens.get(app_num)

res_pdf = client.get(f'/admission/receipt/{app_num}?token={valid_token}')
assert res_pdf.status_code == 200
assert res_pdf.mimetype == 'application/pdf'

res_notif_list = client.get('/notifications/list')
assert res_notif_list.status_code == 200
assert len(res_notif_list.get_json()) >= 1
print("  -> PASSED (PDF receipt binary downloaded & notifications retrieved)")

# [6/15] Applicant Logout Security
print("\n[6/15] Auditing Applicant Logout Security...")
client.get('/students-corner/logout')
res_post_logout = client.get('/notifications/list')
assert len(res_post_logout.get_json()) == 0, "Notifications accessible after logout!"
print("  -> PASSED (Applicant logout cleared session context)")

# [7/15] College Admin Login & Dashboard Analytics
print("\n[7/15] Auditing College Admin Login & Dashboard Analytics...")
res_login_g = client.get('/login')
tok_login = extract_csrf_token(res_login_g)

res_admin_login = client.post('/login', data={
    'email': 'admin@spmcollege.ac.in',
    'password': 'CollegeAdmin@123',
    'csrf_token': tok_login
}, follow_redirects=True)
assert res_admin_login.status_code == 200
assert "Admissions Management" in res_admin_login.data.decode('utf-8')
print("  -> PASSED (College Admin authenticated & Dashboard rendered)")

# [8/15] Admin Search, Filter & Detail Endpoint
print("\n[8/15] Auditing Admin Search, Filters & Applicant Detail Endpoint...")
res_search = client.get(f'/admin?q={app_num}')
assert res_search.status_code == 200
assert app_num in res_search.data.decode('utf-8')

res_detail = client.get(f'/admin/admission/detail/{app_rec.id}')
assert res_detail.status_code == 200
assert res_detail.get_json()['full_name'] == 'Step20 Applicant'
print("  -> PASSED (Search/filtering operational & read-only detail JSON fetched)")

# [9/15] Admin Status Transition & Notifications
print("\n[9/15] Auditing Admin Application Status Transition...")
tok_admin = extract_csrf_token(client.get('/admin'))
res_status = client.post(f'/admin/admission/status/{app_rec.id}', data={
    'status': 'UNDER_REVIEW',
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_status.status_code == 200
db.session.refresh(app_rec)
assert app_rec.status == 'UNDER_REVIEW'
print("  -> PASSED (Status transition updated application state)")

# [10/15] Admin CSV Export
print("\n[10/15] Auditing Admin CSV Export Endpoint...")
res_csv = client.get('/admin/applications/export')
assert res_csv.status_code == 200
assert res_csv.mimetype == 'text/csv'
assert 'Step20 Applicant' in res_csv.data.decode('utf-8')
print("  -> PASSED (CSV export generated with proper headers)")

# [11/15] CMS Functional Journeys with Isolated Test Records & Unlink Cleanup
print("\n[11/15] Auditing CMS Journeys with Isolated Test Data Cleanup...")

# Announcement CMS
res_ann = client.post('/admin/announcement/add', data={
    'title': 'Temp Audit Announcement',
    'category': 'Announcements',
    'content': 'Temp Content for Audit',
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_ann.status_code == 200
test_post = models.ForumPost.query.filter_by(title='Temp Audit Announcement').first()
assert test_post is not None

# Delete test announcement
client.post(f'/admin/announcement/delete/{test_post.id}', data={'csrf_token': tok_admin})
assert db.session.get(models.ForumPost, test_post.id) is None

# Calendar CMS
res_cal = client.post('/admin/calendar/add', data={
    'event_name': 'Temp Audit Calendar Event',
    'date_display': '20 Dec',
    'event_type': 'event',
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_cal.status_code == 200
test_cal = models.AcademicCalendarItem.query.filter_by(event_name='Temp Audit Calendar Event').first()
assert test_cal is not None

# Delete test calendar event
client.post(f'/admin/calendar/delete/{test_cal.id}', data={'csrf_token': tok_admin})
assert db.session.get(models.AcademicCalendarItem, test_cal.id) is None

# Question Paper CMS
bca_course = models.Course.query.filter_by(college_id=college.id, code='BCA').first()
valid_pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 300 144]>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF"
pdf_file = (io.BytesIO(valid_pdf_content), "audit_test.pdf")

res_qp = client.post('/admin/question-paper/upload', data={
    'course_id': bca_course.id,
    'year': '2026',
    'semester': 'Sem 6',
    'subject': 'Temp Audit Subject',
    'file': pdf_file,
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_qp.status_code == 200
test_qp = models.QuestionPaper.query.filter_by(subject='Temp Audit Subject').first()
assert test_qp is not None
qp_disk_path = get_tenant_upload_dir(college.id, 'question_papers') / test_qp.filename
assert qp_disk_path.exists()

# Delete test question paper
client.post(f'/admin/question-paper/delete/{test_qp.id}', data={'csrf_token': tok_admin})
assert db.session.get(models.QuestionPaper, test_qp.id) is None
assert not qp_disk_path.exists(), "Test PDF file was not unlinked from disk!"

# Gallery CMS
img = Image.new('RGB', (10, 10), color='green')
img_io = io.BytesIO()
img.save(img_io, 'PNG')
img_io.seek(0)
img_file = (img_io, "audit_gallery.png")

res_gal = client.post('/gallery/add', data={
    'title': 'Temp Audit Gallery Image',
    'category': 'campus',
    'image_file': img_file,
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_gal.status_code == 200
test_gal = models.GalleryItem.query.filter_by(title='Temp Audit Gallery Image').first()
assert test_gal is not None
gal_disk_path = get_tenant_upload_dir(college.id, 'gallery') / test_gal.image_url
assert gal_disk_path.exists()

# Delete test gallery image
client.post(f'/gallery/delete/{test_gal.id}', data={'csrf_token': tok_admin})
assert db.session.get(models.GalleryItem, test_gal.id) is None
assert not gal_disk_path.exists(), "Test gallery image was not unlinked from disk!"

print("  -> PASSED (All CMS modules verified & temporary test data/files unlinked completely)")

# [12/15] Super Admin Journey with Permission State Restoration (Requirement 3)
print("\n[12/15] Auditing Super Admin Journey & Permission Restoration...")
client.get('/logout')

res_sa_login = client.post('/login', data={
    'email': 'superadmin@spmcollege.ac.in',
    'password': 'SuperAdmin@123',
    'csrf_token': tok_login
}, follow_redirects=True)
assert res_sa_login.status_code == 200

res_sa_page = client.get('/superadmin')
assert res_sa_page.status_code == 200

mod_cfg = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='academics').first()
assert mod_cfg is not None
initial_access = mod_cfg.admin_access

try:
    # Toggle module access
    tok_sa = extract_csrf_token(res_sa_page)
    client.post('/superadmin/toggle-admin/academics', data={'csrf_token': tok_sa})
    db.session.refresh(mod_cfg)
    assert mod_cfg.admin_access == (not initial_access)
finally:
    # Guarantee state restoration!
    mod_cfg.admin_access = initial_access
    db.session.commit()
    db.session.refresh(mod_cfg)
    assert mod_cfg.admin_access == initial_access

print("  -> PASSED (Super Admin portal verified & module permission state restored 100%)")

# [13/15] CSRF Security Boundary Audit
print("\n[13/15] Auditing CSRF Validation on Mutations...")
unauth_client = app.test_client(use_cookies=False)
res_no_csrf = unauth_client.post('/admin/settings/update', data={'college_name': 'Hacked Name'})
assert res_no_csrf.status_code in [400, 403]
print("  -> PASSED (State mutations strictly reject missing CSRF tokens)")

# [14/15] Cross-Tenant Isolation Audit
print("\n[14/15] Auditing Cross-Tenant Data Isolation...")
tenant_b = models.College.query.filter_by(slug='step20-tenant-b').first()
if not tenant_b:
    tenant_b = models.College(name='Step20 Tenant B', slug='step20-tenant-b')
    db.session.add(tenant_b)
    db.session.commit()

app_b = models.AdmissionApplication.query.filter_by(application_number='SC2026-ST20B').first()
if not app_b:
    app_b = models.AdmissionApplication(
        college_id=tenant_b.id,
        application_number='SC2026-ST20B',
        full_name='Tenant B Student',
        guardian_name='Guardian B',
        email='student.b@example.com',
        phone='9900112233',
        course='BBA',
        percentage='85.0',
        status='PENDING'
    )
    db.session.add(app_b)
    db.session.commit()

# Authenticate as College Admin for Tenant A
client.post('/login', data={
    'email': 'admin@spmcollege.ac.in',
    'password': 'CollegeAdmin@123',
    'csrf_token': tok_login
}, follow_redirects=True)

res_cross_detail = client.get(f'/admin/admission/detail/{app_b.id}')
assert res_cross_detail.status_code == 404, f"Expected 404 for cross-tenant applicant detail query, got {res_cross_detail.status_code}"
print("  -> PASSED (Cross-tenant detail queries strictly return HTTP 404 Not Found)")

# [15/15] Route 500 Error Sweep
print("\n[15/15] Auditing All Registered Flask Routes for Unexpected 500 Errors...")
rules = [r for r in app.url_map.iter_rules() if 'GET' in r.methods and not r.arguments]

errors_500 = []
for r in rules:
    try:
        res = client.get(r.rule)
        if res.status_code == 500:
            errors_500.append(r.rule)
    except Exception as e:
        errors_500.append(f"{r.rule}: {str(e)}")

assert len(errors_500) == 0, f"Found 500 errors on routes: {errors_500}"
print(f"  -> PASSED (Audited {len(rules)} GET routes; zero HTTP 500 errors found)")

print("\n==================================================")
print(" ALL 15 FUNCTIONAL AUDIT SECTIONS PASSED 100%!   ")
print("==================================================")
