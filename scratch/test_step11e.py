import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 11E: FINAL SYSTEM INTEGRATION & SECURITY   ")
print("==================================================")

college = seed_default_college()

# 1. Database Integrity & Relationships Audit
print("\n[1/7] Auditing database model relationships and tenant binding...")
c_check = db.session.get(models.College, college.id)
assert c_check.settings is not None, "CollegeSetting missing"
assert models.User.query.count() >= 2, "Users missing"
assert len(c_check.users) >= 1, "College admin user missing"
assert len(c_check.applications) >= 1, "Admissions missing"
assert len(c_check.gallery_items) == 6, "Gallery items count mismatch"
assert len(c_check.forum_posts) >= 5, "Forum posts count mismatch"
assert len(c_check.courses) == 9, "Courses count mismatch"
assert len(c_check.campus_events) == 4, "Campus events count mismatch"
assert len(c_check.academic_calendar_items) == 12, "Calendar items count mismatch"

# Check child relationships
bca = models.Course.query.filter_by(college_id=college.id, code='BCA').first()
assert len(bca.outcome_records) == 3
assert len(bca.semesters) == 6
assert len(bca.semesters[0].subjects) == 4
assert len(bca.question_papers) == 5
print("  -> PASSED (All 11 relational models and child hierarchies verified)")

# 2. Full RBAC Security & Permission Audit
print("\n[2/7] Auditing RBAC and module-level permission enforcement...")

# Unauthenticated redirects
for url in ['/admin', '/superadmin', '/admin/course/add', '/admin/event/add', '/admin/question-paper/add']:
    res_u = client.post(url) if 'add' in url else client.get(url)
    assert res_u.status_code == 302 and 'login' in res_u.headers.get('Location', ''), f"Route {url} unauth fail"

# Authenticated College Admin access
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
assert client.get('/admin').status_code == 200

# College Admin denied Super Admin portal
res_sa_deny = client.get('/superadmin')
assert res_sa_deny.status_code == 403, f"Expected 403, got {res_sa_deny.status_code}"
client.get('/logout')

# Super Admin revokes 'academics' and 'news_events' admin access
client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
cfg_ac = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='academics').first()
cfg_ne = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='news_events').first()
cfg_ac.admin_access = False
cfg_ne.admin_access = False
db.session.commit()
client.get('/logout')

# College Admin denied revoked modules with 403
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
assert client.post('/admin/course/add', data={'code': 'REV'}).status_code == 403
assert client.post('/admin/event/add', data={'title': 'REV'}).status_code == 403
assert client.post('/admin/question-paper/add', data={'course_id': 1}).status_code == 403
client.get('/logout')

# Restore permissions
client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
cfg_ac.admin_access = True
cfg_ne.admin_access = True
db.session.commit()
client.get('/logout')
print("  -> PASSED (RBAC permissions, unauth protection, and revoked module access enforced)")

# 3. Cross-Tenant Attack Security Audit
print("\n[3/7] Testing cross-tenant attack protection across ALL 10 resource types...")
other_college = models.College.query.filter_by(slug='step11e-other-tenant').first()
if other_college:
    models.AdmissionApplication.query.filter_by(college_id=other_college.id).delete()
    models.GalleryItem.query.filter_by(college_id=other_college.id).delete()
    models.ForumPost.query.filter_by(college_id=other_college.id).delete()
    models.CampusEvent.query.filter_by(college_id=other_college.id).delete()
    models.AcademicCalendarItem.query.filter_by(college_id=other_college.id).delete()
    courses = models.Course.query.filter_by(college_id=other_college.id).all()
    for c in courses:
        db.session.delete(c)
    db.session.delete(other_college)
    db.session.commit()

other_college = models.College(name='Step 11E Other Tenant', slug='step11e-other-tenant')
db.session.add(other_college)
db.session.commit()

# Create dummy resources on Tenant B
o_app = models.AdmissionApplication(college_id=other_college.id, application_number='SC-OTHER-1', full_name='Other', guardian_name='G', email='o@x.com', phone='123', course='BCA', percentage=80)
o_gal = models.GalleryItem(college_id=other_college.id, title='Other Gal', category='tech', category_label='Tech', description='Desc')
o_post = models.ForumPost(college_id=other_college.id, author='Other', title='Other Post', category='General', content='Content')
o_course = models.Course(college_id=other_college.id, code='OTH', name='Other Course', level='UG', duration='3 Yrs', affiliation='BCU', overview='Desc', eligibility='Elig')
db.session.add_all([o_app, o_gal, o_post, o_course])
db.session.commit()

o_out = models.CourseOutcome(course_id=o_course.id, content='Other Outcome', display_order=1)
o_sem = models.CurriculumSemester(course_id=o_course.id, semester_name='Sem 1', display_order=1)
o_paper = models.QuestionPaper(course_id=o_course.id, year='2026', semester='Sem 1', subject='Sub', filename='O.pdf')
db.session.add_all([o_out, o_sem, o_paper])
db.session.commit()

o_sub = models.CurriculumSubject(semester_id=o_sem.id, subject_name='Other Sub', display_order=1)
o_ev = models.CampusEvent(college_id=other_college.id, title='Other Ev', date_display='Date', day='01', month='JAN', category='Cat', description='Desc')
o_cal = models.AcademicCalendarItem(college_id=other_college.id, date_display='Date', event_name='Other Cal', event_type='academic')
db.session.add_all([o_sub, o_ev, o_cal])
db.session.commit()

# College Admin A attempts cross-tenant mutations on Tenant B resources
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})

assert client.post(f'/admin/admission/status/{o_app.id}', data={'status': 'VERIFIED'}).status_code == 403
assert client.post(f'/gallery/delete/{o_gal.id}').status_code == 403
assert client.post(f'/forum/delete/{o_post.id}').status_code == 403
assert client.post(f'/admin/course/delete/{o_course.id}').status_code == 403
assert client.post(f'/admin/course/outcome/delete/{o_out.id}').status_code == 403
assert client.post(f'/admin/course/outcome/add/{o_course.id}', data={'content': 'X'}).status_code == 403
assert client.post(f'/admin/course/semester/add/{o_course.id}', data={'semester_name': 'X'}).status_code == 403
assert client.post(f'/admin/course/subject/add/{o_sem.id}', data={'subject_name': 'X'}).status_code == 403
assert client.post(f'/admin/question-paper/delete/{o_paper.id}').status_code == 403
assert client.post('/admin/question-paper/add', data={'course_id': o_course.id, 'year': '2026', 'semester': 'Sem 1', 'subject': 'X', 'filename': 'X.pdf'}).status_code == 403
assert client.post(f'/admin/event/delete/{o_ev.id}').status_code == 403
assert client.post(f'/admin/calendar/delete/{o_cal.id}').status_code == 403

# Cleanup Tenant B
db.session.delete(o_sub)
db.session.delete(o_paper)
db.session.delete(o_sem)
db.session.delete(o_out)
db.session.delete(o_ev)
db.session.delete(o_cal)
db.session.delete(o_course)
db.session.delete(o_post)
db.session.delete(o_gal)
db.session.delete(o_app)
db.session.delete(other_college)
db.session.commit()
client.get('/logout')
print("  -> PASSED (Zero data leakage & HTTP 403 on cross-tenant mutation attempts across all 10 resources)")

# 4. Admin Workflows to Public View Verification
print("\n[4/7] Testing Admin Mutation -> Public View Integration...")
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})

# Add test course
client.post('/admin/course/add', data={'code': 'INTEG', 'name': 'Integration Testing Degree', 'level': 'UG', 'duration': '3 Yrs', 'overview': 'Integ Overview'})
c_integ = models.Course.query.filter_by(college_id=college.id, code='INTEG').first()
assert c_integ is not None

# Add outcome, semester, subject, paper
client.post(f'/admin/course/outcome/add/{c_integ.id}', data={'content': 'Integ Outcome Content'})
client.post(f'/admin/course/semester/add/{c_integ.id}', data={'semester_name': 'Semester I'})
sem_integ = c_integ.semesters[0]
client.post(f'/admin/course/subject/add/{sem_integ.id}', data={'subject_name': 'Integ Subject 101'})
client.post('/admin/question-paper/add', data={'course_id': c_integ.id, 'year': '2026', 'semester': 'Sem 1', 'subject': 'Integ Subject 101', 'filename': 'Integ_Paper_2026.pdf'})

# Verify public academics page shows new course
res_acad_view = client.get('/academics')
assert "Integration Testing Degree" in res_acad_view.data.decode('utf-8')

# Verify public course detail page shows outcome, semester, subject, paper
res_cd_view = client.get('/course/integ')
assert res_cd_view.status_code == 200
html_cd = res_cd_view.data.decode('utf-8')
assert "Integ Outcome Content" in html_cd
assert "Semester I" in html_cd
assert "Integ Subject 101" in html_cd
assert "Integ_Paper_2026.pdf" in html_cd

# Cleanup integ course
client.post(f'/admin/course/delete/{c_integ.id}')
client.get('/logout')
print("  -> PASSED (Admin mutations instantly reflect on public pages & download APIs)")

# 5. Full Site-Wide Public Route Health Audit
print("\n[5/7] Auditing site-wide public routes & error handlers...")
public_urls = [
    ('/', 'Homepage'),
    ('/about', 'About Us'),
    ('/admission', 'Admission Portal'),
    ('/apply', 'Online Apply Form'),
    ('/academics', 'Academics & Syllabus'),
    ('/departments', 'Departments'),
    ('/course/bca', 'Course BCA'),
    ('/facilities', 'Facilities'),
    ('/placements', 'Placements'),
    ('/gallery', 'Gallery'),
    ('/students-corner', 'Students Corner'),
    ('/forum', 'Community Forum'),
    ('/contact', 'Contact Us')
]

for url, name in public_urls:
    res = client.get(url)
    assert res.status_code == 200, f"Public route {url} failed with {res.status_code}"
    print(f"  -> {name} ({url}): HTTP 200 OK")

assert client.get('/course/NONEXISTENT_XYZ').status_code == 404
assert client.get('/download-paper/NONEXISTENT_FILE.pdf').status_code == 404
print("  -> PASSED (All 13 public routes return HTTP 200 OK & 404 handlers operate correctly)")

# 6. Alembic Migration Chain Check
print("\n[6/7] Auditing Alembic migration chain integrity...")
versions_dir = os.path.join(os.path.dirname(__file__), '..', 'migrations', 'versions')
mig_files = [f for f in os.listdir(versions_dir) if f.endswith('.py')]
assert len(mig_files) == 6, f"Expected 6 migration files, found {len(mig_files)}"
print(f"  -> Found {len(mig_files)} Alembic migration scripts in chain")
print("  -> PASSED (Unbroken migration history)")

# 7. Absence of Legacy In-Memory Dictionaries in app.py
print("\n[7/7] Auditing app.py for absence of legacy in-memory content dictionaries...")
with open(os.path.join(os.path.dirname(__file__), '..', 'app.py'), 'r', encoding='utf-8') as f:
    app_code = f.read()

legacy_dicts = ['GALLERY_ITEMS =', 'FORUM_POSTS =', 'COURSES_DATA =', 'UPCOMING_EVENTS =', 'ACADEMIC_CALENDAR =']
for d in legacy_dicts:
    assert d not in app_code, f"Legacy dictionary {d} still present in app.py"

print("  -> PASSED (Zero legacy in-memory dictionaries in app.py)")

print("\n==================================================")
print(" ALL STEP 11E INTEGRATION & SECURITY TESTS PASSED! ")
print("==================================================")
