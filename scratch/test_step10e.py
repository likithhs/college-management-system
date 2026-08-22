import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 10E: FINAL SYSTEM INTEGRATION & REGRESSION ")
print("==================================================")

college = seed_default_college()

# 1. Database Integrity Audit
print("\n[1/6] Auditing database record counts and tenant binding...")
ev_count = models.CampusEvent.query.filter_by(college_id=college.id).count()
cal_count = models.AcademicCalendarItem.query.filter_by(college_id=college.id).count()
c_count = models.Course.query.filter_by(college_id=college.id).count()
g_count = models.GalleryItem.query.filter_by(college_id=college.id).count()
f_count = models.ForumPost.query.filter_by(college_id=college.id).count()
a_count = models.AdmissionApplication.query.filter_by(college_id=college.id).count()

print(f"  -> Campus Events: {ev_count} (Expected: 4)")
print(f"  -> Academic Calendar Items: {cal_count} (Expected: 12)")
print(f"  -> Academic Courses: {c_count} (Expected: 9)")
print(f"  -> Gallery Items: {g_count} (Expected: 6)")
print(f"  -> Forum Posts: {f_count} (Expected: >= 5)")
print(f"  -> Admissions Applications: {a_count} (Expected: >= 1)")

assert ev_count == 4, f"Expected 4 events, got {ev_count}"
assert cal_count == 12, f"Expected 12 calendar items, got {cal_count}"
assert c_count == 9, f"Expected 9 courses, got {c_count}"
assert g_count == 6, f"Expected 6 gallery items, got {g_count}"
assert f_count >= 5, f"Expected >= 5 forum posts, got {f_count}"
assert a_count >= 1, f"Expected >= 1 admissions app, got {a_count}"
print("  -> PASSED (Database record counts and tenant binding verified)")

# 2. Homepage Integration Audit
print("\n[2/6] Testing full homepage integration & rendering...")
res_home = client.get('/')
assert res_home.status_code == 200, f"Expected 200, got {res_home.status_code}"
html_home = res_home.data.decode('utf-8')

assert "TechVanguard Hackathon 2026" in html_home
assert "Annual Sports Meet" in html_home
assert "Cultural Fest - Utsav 2026" in html_home
assert "Campus Placement Drive" in html_home
assert "Odd Semester Classes Begin" in html_home
assert "Annual Convocation Ceremony" in html_home
print("  -> PASSED (All events & calendar items rendered cleanly on homepage)")

# 3. Multi-Tenant Isolation Audit
print("\n[3/6] Testing multi-tenant data isolation across all modules...")
tenant_b = models.College.query.filter_by(slug='step10e-tenant-b').first()
if not tenant_b:
    tenant_b = models.College(name='Step 10E Tenant B', slug='step10e-tenant-b')
    db.session.add(tenant_b)
    db.session.commit()

# Seed records under Tenant B
ev_b = models.CampusEvent(college_id=tenant_b.id, title='TENANT B EVENT', date_display='Jan 1, 2030', day='01', month='JAN', category='B', description='Tenant B', display_order=1)
cal_b = models.AcademicCalendarItem(college_id=tenant_b.id, date_display='Jan 1, 2030', event_name='TENANT B CALENDAR ITEM', event_type='academic', display_order=1)
c_b = models.Course(college_id=tenant_b.id, code='TENANT_B_CS', name='Tenant B Course', level='UG', duration='3 Yrs', affiliation='BCU', overview='B', eligibility='B')
g_b = models.GalleryItem(college_id=tenant_b.id, title='TENANT B GALLERY', category='tech', category_label='Tech', description='B')
f_b = models.ForumPost(college_id=tenant_b.id, author='Student B', title='TENANT B FORUM POST', category='General', content='Content B')
db.session.add_all([ev_b, cal_b, c_b, g_b, f_b])
db.session.commit()

# Verify active tenant views do not expose Tenant B data
res_home_b = client.get('/')
html_b = res_home_b.data.decode('utf-8')
assert "TENANT B EVENT" not in html_b
assert "TENANT B CALENDAR ITEM" not in html_b

res_course_b = client.get('/course/TENANT_B_CS')
assert res_course_b.status_code == 404

res_gal_b = client.get('/gallery')
assert "TENANT B GALLERY" not in res_gal_b.data.decode('utf-8')

res_forum_b = client.get('/forum')
assert "TENANT B FORUM POST" not in res_forum_b.data.decode('utf-8')

# Cleanup Tenant B
db.session.delete(ev_b)
db.session.delete(cal_b)
db.session.delete(c_b)
db.session.delete(g_b)
db.session.delete(f_b)
db.session.delete(tenant_b)
db.session.commit()
print("  -> PASSED (Zero cross-tenant data leakage across all 6 dynamic modules)")

# 4. Module Matrix Toggle Audit
print("\n[4/6] Testing ModuleConfig site-wide toggles...")
client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})

# Toggle news_events module OFF
cfg_news = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='news_events').first()
cfg_news.enabled = False
db.session.commit()

res_news_off = client.get('/')
assert "Upcoming Events" not in res_news_off.data.decode('utf-8'), "Disabled news_events module still rendered"

# Restore news_events module
cfg_news.enabled = True
db.session.commit()
client.get('/logout')
print("  -> PASSED (ModuleConfig toggle controls homepage events rendering dynamically)")

# 5. Security, RBAC & Protection Audit
print("\n[5/6] Testing authentication, RBAC, and cross-tenant security guards...")

# Unauthenticated admin protection
res_unauth = client.get('/admin')
assert res_unauth.status_code == 302 and 'login' in res_unauth.headers.get('Location', '')

# Authenticated College Admin access
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
assert client.get('/admin').status_code == 200

# Non-SuperAdmin trying /superadmin
res_ca_sa = client.get('/superadmin')
assert res_ca_sa.status_code == 403, f"Expected 403, got {res_ca_sa.status_code}"
client.get('/logout')

# Platform Super Admin access
client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
assert client.get('/superadmin').status_code == 200
client.get('/logout')
print("  -> PASSED (Security, RBAC, and protected portals operate flawlessly)")

# 6. Full Site-Wide Route Health Audit
print("\n[6/6] Auditing site-wide route health...")
routes = [
    ('/', 'Homepage'),
    ('/about', 'About Us'),
    ('/admission', 'Admission Portal'),
    ('/apply', 'Online Apply Form'),
    ('/academics', 'Academics & Syllabus'),
    ('/departments', 'Departments'),
    ('/course/bca', 'Course Detail BCA'),
    ('/facilities', 'Facilities'),
    ('/placements', 'Placements'),
    ('/gallery', 'Gallery'),
    ('/students-corner', 'Students Corner'),
    ('/forum', 'Community Forum'),
    ('/contact', 'Contact Us')
]

for url, name in routes:
    res_r = client.get(url)
    assert res_r.status_code == 200, f"Route {url} failed with {res_r.status_code}"
    print(f"  -> {name} ({url}): HTTP 200 OK")
print("  -> PASSED (All 13 public routes return HTTP 200 OK)")

print("\n==================================================")
print(" ALL STEP 10E INTEGRATION & REGRESSION TESTS PASSED ")
print("==================================================")
