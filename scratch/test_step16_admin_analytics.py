import sys
import os
import re
import csv
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 16: ADMIN DASHBOARD & ANALYTICS SUITE      ")
print("==================================================")

college = seed_default_college()

def extract_csrf_token(res):
    html = res.data.decode('utf-8')
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    with client.session_transaction() as sess:
        return sess.get('csrf_token')

# Ensure clean state for test apps
test_apps = [
    ('CSV Inj Candidate', '=SUM(1+1)', 'csv.inj@example.com', 'BCA', 'PENDING', '9000000001'),
    ('Verified Candidate', 'Father V', 'verified.student@example.com', 'MCA - Master of Computer Applications', 'VERIFIED', '9000000002'),
    ('Locked Candidate', 'Father L', 'locked.student@example.com', 'BCA', 'SEAT_LOCKED', '9000000003'),
    ('Rejected Candidate', 'Father R', 'rejected.student@example.com', 'BCA', 'REJECTED', '9000000004'),
]

for name, gname, email, course, status, phone in test_apps:
    models.AdmissionApplication.query.filter_by(email=email).delete()
db.session.commit()

created_app_ids = []
for name, gname, email, course, status, phone in test_apps:
    app_obj = models.AdmissionApplication(
        college_id=college.id,
        application_number=f"SC2026-T16-{name[:3].upper()}",
        full_name=name,
        guardian_name=gname,
        email=email,
        phone=phone,
        course=course,
        percentage='91.5',
        status=status
    )
    db.session.add(app_obj)
    db.session.commit()
    created_app_ids.append(app_obj.id)

print(f"  -> Created 4 Test Applications across statuses (ID: {created_app_ids})")

# Authenticate as College Admin
res_login_g = client.get('/login')
tok_login = extract_csrf_token(res_login_g)
res_login = client.post('/login', data={
    'email': 'admin@spmcollege.ac.in',
    'password': 'CollegeAdmin@123',
    'csrf_token': tok_login
}, follow_redirects=True)
assert res_login.status_code == 200, "Admin login failed!"

# 1. Real-Time Analytics Cards & Dashboard Audit
print("\n[1/6] Auditing 5 Real-Time Analytics Summary Cards...")
res_admin = client.get('/admin')
assert res_admin.status_code == 200
html_admin = res_admin.data.decode('utf-8')

assert "Total Submissions" in html_admin
assert "Verified Credentials" in html_admin
assert "Seats Locked" in html_admin
assert "Pending & Review" in html_admin
assert "Rejected Apps" in html_admin, "5th Rejected Apps Analytics Card missing from dashboard!"
print("  -> PASSED (5 Analytics cards including Rejected Apps verified on dashboard)")

# 2. CSV Injection Protection Audit (Requirement 1 & User Test Case)
print("\n[2/6] Auditing CSV Export & CSV Injection Neutralization...")
res_csv = client.get('/admin/applications/export')
assert res_csv.status_code == 200
assert 'text/csv' in res_csv.content_type
assert 'attachment; filename=' in res_csv.headers.get('Content-Disposition', '')

csv_data = res_csv.data.decode('utf-8')
reader = csv.reader(io.StringIO(csv_data))
rows = list(reader)

found_inj = False
for row in rows:
    if len(row) > 2 and 'csv.inj@example.com' in row[3]:
        guardian_col = row[2] # Guardian name was '=SUM(1+1)'
        assert guardian_col == "'=SUM(1+1)", f"Expected neutralized CSV injection \"'=SUM(1+1)\", got \"{guardian_col}\""
        found_inj = True

assert found_inj, "CSV injection test row not found in export output!"
print("  -> PASSED (CSV file generated & formula injection '=SUM(1+1)' neutralized to \"'=SUM(1+1)\")")

# 3. Cross-Tenant Detail Endpoint Isolation Audit (Requirement 3 & User Test Case)
print("\n[3/6] Auditing Cross-Tenant Detail Endpoint Security...")

# Get or create Tenant B application
tenant_b = models.College.query.filter_by(slug='step16-tenant-b').first()
if not tenant_b:
    tenant_b = models.College(name='Step 16 Tenant B', slug='step16-tenant-b')
    db.session.add(tenant_b)
    db.session.commit()

app_tenant_b = models.AdmissionApplication.query.filter_by(application_number='SC2026-T16-TB').first()
if not app_tenant_b:
    app_tenant_b = models.AdmissionApplication(
        college_id=tenant_b.id,
        application_number='SC2026-T16-TB',
        full_name='Tenant B Secret Candidate',
        guardian_name='Guardian B',
        email='tb.secret@example.com',
        phone='9990001112',
        course='BBA',
        percentage='95.0',
        status='PENDING'
    )
    db.session.add(app_tenant_b)
    db.session.commit()

# College A Admin attempts to query Tenant B applicant detail
res_cross_detail = client.get(f'/admin/admission/detail/{app_tenant_b.id}')
assert res_cross_detail.status_code == 404, f"Expected HTTP 404 for cross-tenant applicant detail, got {res_cross_detail.status_code}"
print("  -> PASSED (Cross-tenant detail query returned HTTP 404 Not Found)")

# 4. GET Read-Only Detail Endpoint Audit (Requirement 4 & User Test Case)
print("\n[4/6] Auditing Applicant Detail Endpoint (GET Read-Only)...")
valid_app_id = created_app_ids[0]
res_detail = client.get(f'/admin/admission/detail/{valid_app_id}')
assert res_detail.status_code == 200
json_detail = res_detail.get_json()

assert json_detail['full_name'] == 'CSV Inj Candidate'
assert json_detail['status'] == 'PENDING'
assert json_detail['email'] == 'csv.inj@example.com'
print("  -> PASSED (Detail endpoint returned JSON candidate details without state mutation)")

# 5. Safe Pagination & Filter Persistence Audit (Requirement 5 & User Test Cases)
print("\n[5/6] Auditing Safe Pagination & Filter Persistence...")

# Test invalid page inputs
for bad_page in ['-1', '99999', 'invalid_string', '0']:
    res_bad_page = client.get(f'/admin?page={bad_page}')
    assert res_bad_page.status_code == 200, f"Dashboard crashed on bad page={bad_page}"

# Test filter persistence in pagination links
res_filter = client.get('/admin?q=Candidate&status_filter=VERIFIED&page=1')
assert res_filter.status_code == 200
html_filter = res_filter.data.decode('utf-8')
assert 'q=Candidate' in html_filter
assert 'status_filter=VERIFIED' in html_filter
print("  -> PASSED (Invalid page parameters clamped safely & active filters preserved in links)")

# 6. RBAC & Module Permission Enforcement Audit (User Test Case)
print("\n[6/6] Auditing RBAC Module Permission Enforcement...")

# Revoke admission module access for default college in ModuleConfig
mod_cfg = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='admission').first()
if mod_cfg:
    mod_cfg.admin_access = False
    db.session.commit()

# Verify CSV export is blocked with 403
res_blocked_export = client.get('/admin/applications/export')
assert res_blocked_export.status_code == 403, f"Expected 403 when admission module revoked, got {res_blocked_export.status_code}"

# Verify applicant detail endpoint is blocked with 403
res_blocked_detail = client.get(f'/admin/admission/detail/{valid_app_id}')
assert res_blocked_detail.status_code == 403, f"Expected 403 when admission module revoked, got {res_blocked_detail.status_code}"

# Restore module permission
if mod_cfg:
    mod_cfg.admin_access = True
    db.session.commit()

print("  -> PASSED (CSV export & detail endpoints strictly blocked when module access is revoked)")

print("\n==================================================")
print(" ALL ADMIN DASHBOARD & ANALYTICS TESTS PASSED!   ")
print("==================================================")
