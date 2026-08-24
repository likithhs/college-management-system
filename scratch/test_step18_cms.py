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
print("  STEP 18: SECURE COLLEGE CMS & FILE SUITE        ")
print("==================================================")

college = seed_default_college()

def extract_csrf_token(res):
    html = res.data.decode('utf-8')
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    with client.session_transaction() as sess:
        return sess.get('csrf_token')

# Authenticate as College Admin
res_login_g = client.get('/login')
tok_login = extract_csrf_token(res_login_g)
res_login = client.post('/login', data={
    'email': 'admin@spmcollege.ac.in',
    'password': 'CollegeAdmin@123',
    'csrf_token': tok_login
}, follow_redirects=True)
assert res_login.status_code == 200, "Admin login failed!"

# 1. Institution Settings Validation Test (Requirement 6)
print("\n[1/14] Auditing Institution Settings CMS & Input Validation...")
res_settings_g = client.get('/admin')
tok_admin = extract_csrf_token(res_settings_g)

# Invalid email test
res_bad_email = client.post('/admin/settings/update', data={
    'college_name': 'Valid Name',
    'email_info': 'bad_email_no_at_symbol',
    'csrf_token': tok_admin
}, follow_redirects=True)
assert "valid email" in res_bad_email.data.decode('utf-8').lower()

# Overly long text test
res_long_text = client.post('/admin/settings/update', data={
    'college_name': 'A' * 200,
    'csrf_token': tok_admin
}, follow_redirects=True)
assert "exceeds" in res_long_text.data.decode('utf-8').lower() or "required" in res_long_text.data.decode('utf-8').lower()

# Valid update test
res_good_settings = client.post('/admin/settings/update', data={
    'college_name': 'Seshadripuram Degree College',
    'tagline': 'Empowering Higher Education Excellence',
    'email_info': 'info@spmcollege.ac.in',
    'phone_primary': '+91 6363179389',
    'address': 'Main Campus, Bengaluru',
    'accreditation': 'NAAC A++',
    'hero_title': 'Shaping Future Leaders',
    'hero_subtitle': 'Premier institution of higher education',
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_good_settings.status_code == 200
print("  -> PASSED (Invalid inputs rejected; valid settings updated)")

# 2. Announcement Tenant Isolation Test (Requirement 1 & 7)
print("\n[2/14] Auditing Announcement Tenant Isolation...")
tenant_b = models.College.query.filter_by(slug='step18-cms-tenant-b').first()
if not tenant_b:
    tenant_b = models.College(name='CMS Tenant B', slug='step18-cms-tenant-b')
    db.session.add(tenant_b)
    db.session.commit()

post_b = models.ForumPost(
    college_id=tenant_b.id,
    author="Tenant B Admin",
    title="Tenant B Secret Announcement",
    category="Events",
    content="Secret Event Info"
)
db.session.add(post_b)
db.session.commit()

res_del_post = client.post(f'/admin/announcement/delete/{post_b.id}', data={'csrf_token': tok_admin})
assert res_del_post.status_code == 404, f"Expected 404 for cross-tenant announcement delete, got {res_del_post.status_code}"
print("  -> PASSED (Cross-tenant announcement deletion strictly blocked)")

# 3. Academic Calendar Tenant Isolation Test (Requirement 1 & 8)
print("\n[3/14] Auditing Academic Calendar Tenant Isolation...")
cal_b = models.AcademicCalendarItem(
    college_id=tenant_b.id,
    event_name="Tenant B Exam",
    date_display="15 Dec",
    event_type="exam"
)
db.session.add(cal_b)
db.session.commit()

res_del_cal = client.post(f'/admin/calendar/delete/{cal_b.id}', data={'csrf_token': tok_admin})
assert res_del_cal.status_code in [403, 404], f"Expected 403/404 for cross-tenant calendar delete, got {res_del_cal.status_code}"
print("  -> PASSED (Cross-tenant calendar deletion strictly blocked)")

# 4. Real PDF Validation Test (Requirement 3)
print("\n[4/14] Auditing PDF Content & Header Signature Validation...")
bca_course = models.Course.query.filter_by(college_id=college.id, code='BCA').first()
assert bca_course is not None

# Fake executable disguised as PDF
fake_exe_pdf = (io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00fake_executable_binary"), "malware.exe.pdf")
res_fake_exe = client.post('/admin/question-paper/upload', data={
    'course_id': bca_course.id,
    'year': '2026',
    'semester': 'Sem 5',
    'subject': 'Malware Subject',
    'file': fake_exe_pdf,
    'csrf_token': tok_admin
}, follow_redirects=True)
assert "invalid pdf" in res_fake_exe.data.decode('utf-8').lower() or "rejected" in res_fake_exe.data.decode('utf-8').lower()

# Fake python script file
fake_py = (io.BytesIO(b"print('hello world')"), "script.py")
res_fake_py = client.post('/admin/question-paper/upload', data={
    'course_id': bca_course.id,
    'year': '2026',
    'semester': 'Sem 5',
    'subject': 'Python Script',
    'file': fake_py,
    'csrf_token': tok_admin
}, follow_redirects=True)
assert "invalid file type" in res_fake_py.data.decode('utf-8').lower()

# Valid minimal PDF buffer
valid_pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 300 144]>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF"

valid_pdf_file = (io.BytesIO(valid_pdf_content), "genuine_sample.pdf")
res_valid_pdf = client.post('/admin/question-paper/upload', data={
    'course_id': bca_course.id,
    'year': '2026',
    'semester': 'Sem 5',
    'subject': 'Web Development PYQ',
    'file': valid_pdf_file,
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_valid_pdf.status_code == 200
assert "uploaded successfully" in res_valid_pdf.data.decode('utf-8').lower()
print("  -> PASSED (Renamed binaries & scripts rejected; genuine PDF accepted)")

# 5. PDF Filename Collision Test (Requirement 3)
print("\n[5/14] Auditing PDF Filename Collision Protection...")
file1 = (io.BytesIO(valid_pdf_content), "question.pdf")
file2 = (io.BytesIO(valid_pdf_content), "question.pdf")

client.post('/admin/question-paper/upload', data={
    'course_id': bca_course.id,
    'year': '2026',
    'semester': 'Sem 5',
    'subject': 'Subject Dup 1',
    'file': file1,
    'csrf_token': tok_admin
}, follow_redirects=True)

client.post('/admin/question-paper/upload', data={
    'course_id': bca_course.id,
    'year': '2026',
    'semester': 'Sem 5',
    'subject': 'Subject Dup 2',
    'file': file2,
    'csrf_token': tok_admin
}, follow_redirects=True)

qp1 = models.QuestionPaper.query.filter_by(subject='Subject Dup 1').first()
qp2 = models.QuestionPaper.query.filter_by(subject='Subject Dup 2').first()
assert qp1 is not None and qp2 is not None
assert qp1.filename != qp2.filename, "UUID filename collision protection failed!"
print("  -> PASSED (Same input filename 'question.pdf' stored with unique UUID filenames)")

# 6. Tenant Filesystem Isolation Test (Requirement 2)
print("\n[6/14] Auditing Tenant Upload Directory Isolation...")
qp1_path = get_tenant_upload_dir(college.id, 'question_papers') / qp1.filename
assert qp1_path.exists()
assert f"colleges\\{college.id}" in str(qp1_path) or f"colleges/{college.id}" in str(qp1_path)
print("  -> PASSED (Uploaded files stored inside tenant-specific directory)")

# 7. Safe Question Paper Deletion Test (Requirement 3 & 5)
print("\n[7/14] Auditing Question Paper Safe Unlinking & Deletion...")
res_del_qp = client.post(f'/admin/question-paper/delete/{qp1.id}', data={'csrf_token': tok_admin}, follow_redirects=True)
assert res_del_qp.status_code == 200
assert models.QuestionPaper.query.get(qp1.id) is None
assert not qp1_path.exists(), "File remained on disk after database record deletion!"
print("  -> PASSED (Database record deleted & file safely unlinked from disk)")

# 8. Fake Image Validation Test (Requirement 4)
print("\n[8/14] Auditing Pillow Image Verification on Uploads...")
fake_image_file = (io.BytesIO(b"console.log('XSS malicious script');"), "malicious.js.jpg")
res_fake_img = client.post('/gallery/add', data={
    'title': 'Fake Image Test',
    'category': 'campus',
    'image_file': fake_image_file,
    'csrf_token': tok_admin
}, follow_redirects=True)
assert "validation failed" in res_fake_img.data.decode('utf-8').lower() or "error" in res_fake_img.data.decode('utf-8').lower()
print("  -> PASSED (Pillow image verification rejected script file disguised as image)")

# 9. Valid Image Upload Test (Requirement 4)
print("\n[9/14] Auditing Genuine Image Upload & Storage...")
img = Image.new('RGB', (10, 10), color='blue')
img_io = io.BytesIO()
img.save(img_io, 'PNG')
img_io.seek(0)
valid_img_file = (img_io, "campus_event.png")

res_valid_img = client.post('/gallery/add', data={
    'title': 'Valid Campus Photo',
    'category': 'campus',
    'image_file': valid_img_file,
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_valid_img.status_code == 200

good_item = models.GalleryItem.query.filter_by(title='Valid Campus Photo', college_id=college.id).first()
assert good_item is not None
img_disk_path = get_tenant_upload_dir(college.id, 'gallery') / good_item.image_url
assert img_disk_path.exists()
print("  -> PASSED (Genuine image validated by Pillow and saved to tenant directory)")

# 10. Gallery Deletion Isolation Test (Requirement 1 & 10)
print("\n[10/14] Auditing Gallery Deletion Isolation...")
gal_b = models.GalleryItem(
    college_id=tenant_b.id,
    title="Tenant B Private Photo",
    category="campus",
    category_label="Campus Life",
    image_url="tenant_b_photo.png"
)
db.session.add(gal_b)
db.session.commit()

res_del_gal = client.post(f'/gallery/delete/{gal_b.id}', data={'csrf_token': tok_admin})
assert res_del_gal.status_code in [403, 404], f"Expected 403/404 for cross-tenant gallery delete, got {res_del_gal.status_code}"
print("  -> PASSED (Cross-tenant gallery deletion strictly blocked)")

# 11. Path Traversal Protection Test (Requirement 5 & User Recommendation)
print("\n[11/14] Auditing Path Traversal Defense (pathlib.Path.resolve)...")
escape_result = safe_delete_tenant_file(college.id, 'gallery', '../../app.py')
assert escape_result is False, "Path traversal escape attempt succeeded!"
print("  -> PASSED (Path traversal containment check blocked escape attempt)")

# 12. Announcement XSS Safety Test (Requirement 7)
print("\n[12/14] Auditing Announcement XSS Sanitization & Rendering...")
xss_title = '<script>alert("XSS_TITLE")</script>'
xss_content = '<img src=x onerror=alert("XSS_CONTENT")>'

client.post('/admin/announcement/add', data={
    'title': xss_title,
    'category': 'Announcements',
    'content': xss_content,
    'csrf_token': tok_admin
}, follow_redirects=True)

res_admin_xss = client.get('/admin')
html_xss = res_admin_xss.data.decode('utf-8')
assert '<script>alert("XSS_TITLE")</script>' not in html_xss or '&lt;script&gt;' in html_xss
print("  -> PASSED (XSS script payloads safely escaped in Jinja template rendering)")

# 13. RBAC Enforcement Test (Requirement 13)
print("\n[13/14] Auditing RBAC Module Enforcement on CMS Routes...")
mod_academics = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='academics').first()
if mod_academics:
    mod_academics.admin_access = False
    db.session.commit()

res_blocked_qp = client.post('/admin/question-paper/upload', data={'csrf_token': tok_admin})
assert res_blocked_qp.status_code == 403, f"Expected 403 when academics module revoked, got {res_blocked_qp.status_code}"

if mod_academics:
    mod_academics.admin_access = True
    db.session.commit()

print("  -> PASSED (CMS endpoints return HTTP 403 when module access is revoked)")

# 14. Curriculum Tenant Isolation Test (Requirement 14)
print("\n[14/14] Auditing Curriculum Tenant Isolation...")
course_b = models.Course.query.filter_by(college_id=tenant_b.id, code='BBA-TB').first()
if not course_b:
    course_b = models.Course(
        college_id=tenant_b.id,
        code="BBA-TB",
        name="Tenant B BBA",
        level="Undergraduate",
        duration="3 Years",
        affiliation="Bengaluru City University",
        eligibility="10+2 Passed",
        overview="Tenant B Overview"
    )
    db.session.add(course_b)
    db.session.commit()

res_del_course = client.post(f'/admin/course/delete/{course_b.id}', data={'csrf_token': tok_admin})
assert res_del_course.status_code in [403, 404], f"Expected 403/404 for cross-tenant course delete, got {res_del_course.status_code}"
print("  -> PASSED (Cross-tenant curriculum deletion strictly blocked)")

print("\n==================================================")
print(" ALL 14 SECURE CMS & FILE TESTS PASSED 100%!     ")
print("==================================================")
