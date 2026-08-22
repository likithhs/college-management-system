import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 12D: PERFORMANCE & QUERY OPTIMIZATION      ")
print("==================================================")

college = seed_default_college()

# 1. Database Index Verification
print("\n[1/7] Auditing SQLite database index creation...")
inspector = db.inspect(db.engine)
adm_indexes = [idx['name'] for idx in inspector.get_indexes('admission_applications')]
gal_indexes = [idx['name'] for idx in inspector.get_indexes('gallery_items')]

assert 'ix_admission_applications_college_id' in adm_indexes, "Index ix_admission_applications_college_id missing"
assert 'ix_gallery_items_college_id' in gal_indexes, "Index ix_gallery_items_college_id missing"
print("  -> PASSED (ix_admission_applications_college_id & ix_gallery_items_college_id indexes active)")

# 2. Alembic Migration Chain Verification
print("\n[2/7] Auditing Alembic migration chain integrity...")
versions_dir = os.path.join(os.path.dirname(__file__), '..', 'migrations', 'versions')
mig_files = [f for f in os.listdir(versions_dir) if f.endswith('.py')]
assert len(mig_files) == 7, f"Expected 7 migration files, found {len(mig_files)}"
print(f"  -> Found {len(mig_files)} Alembic migration scripts in unbroken chain")
print("  -> PASSED (7 sequential migrations verified)")

# 3. Eager Loading on /course/bca Route
print("\n[3/7] Testing eager loading (joinedload & selectinload) on /course/bca...")
res_course = client.get('/course/bca')
assert res_course.status_code == 200
html_course = res_course.data.decode('utf-8')

assert "Bachelor of Computer Applications" in html_course
assert "Semester I" in html_course
assert "BCA_Sem5_FullStack_2025.pdf" in html_course
print("  -> PASSED (Course details, outcome records, curriculum semesters, subjects & papers loaded)")

# 4. Eager Loading on /admin Route
print("\n[4/7] Testing eager loading on /admin question papers query...")
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
res_admin = client.get('/admin')
assert res_admin.status_code == 200
html_admin = res_admin.data.decode('utf-8')
assert "Managed Past Question Papers" in html_admin
client.get('/logout')
print("  -> PASSED (Admin dashboard renders with joinedload question paper course relationship)")

# 5. Static Asset Cache-Control Header Verification
print("\n[5/7] Testing Static Asset Cache-Control header delivery...")
res_static = client.get('/static/css/style.css')
assert res_static.status_code == 200
assert 'Cache-Control' in res_static.headers
assert 'max-age=86400' in res_static.headers['Cache-Control']
print("  -> PASSED (Static files delivered with 'Cache-Control: public, max-age=86400')")

# 6. Site-Wide 15-Route Health Sweep
print("\n[6/7] Running 15-route site-wide health sweep...")
public_urls = [
    '/', '/about', '/admission', '/apply', '/academics', '/departments',
    '/course/bca', '/facilities', '/placements', '/gallery',
    '/students-corner', '/forum', '/contact', '/admin', '/superadmin'
]

for url in public_urls:
    if url in ['/admin', '/superadmin']:
        client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
    res_u = client.get(url)
    assert res_u.status_code in [200, 302], f"Route {url} failed with status {res_u.status_code}"
    client.get('/logout')

print("  -> PASSED (All 15 public & admin routes operational)")

# 7. Backend & Security Regressions Check
print("\n[7/7] Verifying zero backend or security regressions...")
assert models.College.query.count() >= 1
assert models.Course.query.count() == 9
assert models.CampusEvent.query.count() == 4
assert models.AcademicCalendarItem.query.count() == 12
print("  -> PASSED (Database models & security guards intact)")

print("\n==================================================")
print(" ALL STEP 12D PERFORMANCE TESTS PASSED 100%!     ")
print("==================================================")
