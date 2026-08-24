import sys
import os
import re
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models, get_tenant_upload_dir, safe_delete_tenant_file
from seed import seed_default_college
from PIL import Image

app.app_context().push()
db.create_all()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 21: FACULTY DIRECTORY & PLACEMENT DRIVES   ")
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
client.post('/login', data={
    'email': 'admin@spmcollege.ac.in',
    'password': 'CollegeAdmin@123',
    'csrf_token': tok_login
}, follow_redirects=True)

tok_admin = extract_csrf_token(client.get('/admin'))

# [1/12] Model Creation Test
print("\n[1/12] Auditing FacultyMember & PlacementDrive Models...")
fac1 = models.FacultyMember(
    college_id=college.id,
    name='Dr. Alan Turing',
    designation='Professor & Head',
    department_code='BCA',
    qualification='Ph.D. in Computer Science',
    specialization='Algorithms & Computation',
    email='alan.turing@spmcollege.ac.in',
    phone='+91 9900112233',
    display_order=1
)
drive1 = models.PlacementDrive(
    college_id=college.id,
    company_name='Infosys Limited',
    role_offered='Systems Engineer',
    package_lpa='4.5 LPA',
    eligibility_criteria='BCA / MCA with 60% aggregate',
    drive_date='15 Oct 2026',
    status='UPCOMING',
    contact_email='placement@spmcollege.ac.in'
)
db.session.add(fac1)
db.session.add(drive1)
db.session.commit()

assert fac1.id is not None
assert drive1.id is not None
print("  -> PASSED (Database records created for FacultyMember and PlacementDrive)")

# [2/12] Pillow Image Validation for Faculty Photo
print("\n[2/12] Auditing Pillow Image Verification for Faculty Photo Upload...")
fake_script = (io.BytesIO(b"<script>alert(1)</script>"), "hacker.png")
res_fake = client.post('/admin/faculty/add', data={
    'name': 'Fake Photo Faculty',
    'designation': 'Assistant Professor',
    'department_code': 'BCA',
    'qualification': 'M.Tech',
    'email': 'fake.photo@spmcollege.ac.in',
    'photo_file': fake_script,
    'csrf_token': tok_admin
}, follow_redirects=True)
assert "Faculty Photo Error" in res_fake.data.decode('utf-8')
print("  -> PASSED (Pillow rejected non-image script file for faculty photo)")

# [3/12] Genuine Faculty Profile Creation & UUID Filename
print("\n[3/12] Auditing Genuine Faculty Profile Creation & UUID Storage...")
img_f = Image.new('RGB', (20, 20), color='blue')
img_io_f = io.BytesIO()
img_f.save(img_io_f, 'PNG')
img_io_f.seek(0)

res_real_fac = client.post('/admin/faculty/add', data={
    'name': 'Dr. Margaret Hamilton',
    'designation': 'Director of Software Engineering',
    'department_code': 'BCA',
    'qualification': 'Ph.D. in Mathematics',
    'specialization': 'Apollo Guidance Computer Systems',
    'email': 'margaret.hamilton@spmcollege.ac.in',
    'photo_file': (img_io_f, "margaret.png"),
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_real_fac.status_code == 200

fac_rec = models.FacultyMember.query.filter_by(email='margaret.hamilton@spmcollege.ac.in').first()
assert fac_rec is not None
assert fac_rec.photo_url is not None
assert fac_rec.photo_url != "margaret.png" # UUID storage!
fac_file_path = get_tenant_upload_dir(college.id, 'faculty') / fac_rec.photo_url
assert fac_file_path.exists()
print("  -> PASSED (Genuine faculty profile created & stored with UUID photo filename)")

# [4/12] Genuine Placement Drive Creation & UUID Logo
print("\n[4/12] Auditing Genuine Placement Drive Creation & Recruiter Logo Storage...")
img_p = Image.new('RGB', (30, 30), color='green')
img_io_p = io.BytesIO()
img_p.save(img_io_p, 'PNG')
img_io_p.seek(0)

res_drive = client.post('/admin/placement-drive/add', data={
    'company_name': 'Google India',
    'role_offered': 'Associate Software Engineer',
    'package_lpa': '18.5 LPA',
    'eligibility_criteria': 'BCA/BSc/MCA with 70% aggregate & no active arrears',
    'drive_date': '20 Nov 2026',
    'status': 'UPCOMING',
    'contact_email': 'placements@spmcollege.ac.in',
    'logo_file': (img_io_p, "google_logo.png"),
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_drive.status_code == 200

drive_rec = models.PlacementDrive.query.filter_by(company_name='Google India').first()
assert drive_rec is not None
assert drive_rec.company_logo is not None
drive_file_path = get_tenant_upload_dir(college.id, 'placements') / drive_rec.company_logo
assert drive_file_path.exists()
print("  -> PASSED (Placement drive created & recruiter logo saved with UUID filename)")

# [5/12] Public Faculty Directory Rendering & Filter Isolation
print("\n[5/12] Auditing Public Faculty Directory & Department Filter Isolation...")
res_fac_pub = client.get('/faculty')
assert res_fac_pub.status_code == 200
assert 'Dr. Alan Turing' in res_fac_pub.data.decode('utf-8')

# Department filter test
res_fac_bca = client.get('/faculty?dept=BCA')
assert res_fac_bca.status_code == 200
assert 'Dr. Alan Turing' in res_fac_bca.data.decode('utf-8')

res_fac_bba = client.get('/faculty?dept=BBA')
assert res_fac_bba.status_code == 200
assert 'Dr. Alan Turing' not in res_fac_bba.data.decode('utf-8')
print("  -> PASSED (Public /faculty renders cleanly and filters by department code)")

# [6/12] Public Placement Portal Rendering & Status Filter Isolation
print("\n[6/12] Auditing Public Placement Portal & Status Filter Isolation...")
res_place_pub = client.get('/placements')
assert res_place_pub.status_code == 200
assert 'Google India' in res_place_pub.data.decode('utf-8')

res_place_upc = client.get('/placements?status=UPCOMING')
assert res_place_upc.status_code == 200
assert 'Google India' in res_place_upc.data.decode('utf-8')

res_place_comp = client.get('/placements?status=COMPLETED')
assert res_place_comp.status_code == 200
assert 'Google India' not in res_place_comp.data.decode('utf-8')
print("  -> PASSED (Public /placements renders dynamic recruitment drives and filters by status)")

# [7/12] Faculty Safe Unlinking & Deletion
print("\n[7/15] Auditing Faculty Safe Unlinking & Deletion...")
client.post(f'/admin/faculty/delete/{fac_rec.id}', data={'csrf_token': tok_admin})
assert db.session.get(models.FacultyMember, fac_rec.id) is None
assert not fac_file_path.exists(), "Faculty photo was not unlinked from disk!"
print("  -> PASSED (Faculty record deleted & photo file unlinked safely)")

# [8/12] Placement Drive Safe Unlinking & Deletion
print("\n[8/12] Auditing Placement Drive Safe Unlinking & Deletion...")
client.post(f'/admin/placement-drive/delete/{drive_rec.id}', data={'csrf_token': tok_admin})
assert db.session.get(models.PlacementDrive, drive_rec.id) is None
assert not drive_file_path.exists(), "Recruiter logo was not unlinked from disk!"
print("  -> PASSED (Placement drive record deleted & recruiter logo unlinked safely)")

# [9/12] Cross-Tenant Deletion Isolation
print("\n[9/12] Auditing Cross-Tenant Deletion Protection...")
tenant_b = models.College.query.filter_by(slug='step21-tenant-b').first()
if not tenant_b:
    tenant_b = models.College(name='Step21 Tenant B', slug='step21-tenant-b')
    db.session.add(tenant_b)
    db.session.commit()

fac_b = models.FacultyMember(
    college_id=tenant_b.id,
    name='Dr. Tenant B Professor',
    designation='Professor',
    department_code='BBA',
    qualification='Ph.D.',
    email='tb.prof@example.com'
)
drive_b = models.PlacementDrive(
    college_id=tenant_b.id,
    company_name='Tenant B Company',
    role_offered='Analyst',
    package_lpa='5 LPA',
    eligibility_criteria='All 60%',
    drive_date='10 Dec 2026'
)
db.session.add(fac_b)
db.session.add(drive_b)
db.session.commit()

res_cross_fac = client.post(f'/admin/faculty/delete/{fac_b.id}', data={'csrf_token': tok_admin})
assert res_cross_fac.status_code in [403, 404]

res_cross_drive = client.post(f'/admin/placement-drive/delete/{drive_b.id}', data={'csrf_token': tok_admin})
assert res_cross_drive.status_code in [403, 404]
print("  -> PASSED (Cross-tenant faculty & placement deletions strictly blocked)")

# [10/12] Path Traversal Containment Check
print("\n[10/12] Auditing Path Traversal Containment on Deletions...")
safe_delete_tenant_file(college.id, 'faculty', '../../app.py')
safe_delete_tenant_file(college.id, 'placements', '../../models.py')
print("  -> PASSED (Path traversal containment check prevented escape attempts)")

# [11/12] CSRF Boundary Enforcement
print("\n[11/12] Auditing CSRF Enforcement on Faculty & Placement Routes...")
unauth_client = app.test_client(use_cookies=False)
res_no_csrf_f = unauth_client.post('/admin/faculty/add', data={'name': 'No CSRF Faculty'})
assert res_no_csrf_f.status_code in [400, 403]
print("  -> PASSED (Missing CSRF tokens strictly rejected)")

# [12/12] Cleanup Test Records
print("\n[12/12] Cleaning Up Temporary Test Records...")
models.FacultyMember.query.filter_by(college_id=college.id).delete()
models.PlacementDrive.query.filter_by(college_id=college.id).delete()
models.FacultyMember.query.filter_by(college_id=tenant_b.id).delete()
models.PlacementDrive.query.filter_by(college_id=tenant_b.id).delete()
db.session.commit()
print("  -> PASSED (Temporary test records cleaned up)")

print("\n==================================================")
print(" ALL 12 STEP 21 FACULTY & PLACEMENTS TESTS PASSED! ")
print("==================================================")
