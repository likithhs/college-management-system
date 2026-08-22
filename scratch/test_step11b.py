import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 11B: COURSE & CURRICULUM ADMIN MANAGEMENT  ")
print("==================================================")

college = seed_default_college()

# Reset academics admin_access to True for clean test state
cfg_init = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='academics').first()
if cfg_init:
    cfg_init.admin_access = True
    db.session.commit()

# 1. Unauthenticated Access Protection
print("\n[1/12] Testing unauthenticated admin access protection...")
res_unauth = client.post('/admin/course/add', data={'code': 'UNAUTH', 'name': 'Unauth Course', 'level': 'UG', 'duration': '3 Yrs', 'overview': 'Desc'})
assert res_unauth.status_code == 302 and 'login' in res_unauth.headers.get('Location', '')
print("  -> PASSED (Unauthenticated request redirected to /login)")

# Authenticate as College Admin
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})

# 2. Add New Course
print("\n[2/12] Testing POST /admin/course/add...")
res_add = client.post('/admin/course/add', data={
    'code': 'AIML',
    'name': 'B.Tech Artificial Intelligence & Machine Learning',
    'level': 'Undergraduate (UG)',
    'duration': '4 Years (8 Semesters)',
    'affiliation': 'Bengaluru City University',
    'overview': 'Specialized program in Deep Learning, Computer Vision, and Generative AI.',
    'eligibility': '10+2 Science Stream with Maths and Physics.'
}, follow_redirects=True)
assert res_add.status_code == 200

created_course = models.Course.query.filter_by(college_id=college.id, code='AIML').first()
assert created_course is not None, "Course AIML not found in database"
assert created_course.name == 'B.Tech Artificial Intelligence & Machine Learning'
print("  -> PASSED (New course created successfully in database)")

# 3. Duplicate Course Code Rejection
print("\n[3/12] Testing duplicate course code rejection...")
res_dup = client.post('/admin/course/add', data={
    'code': 'AIML',
    'name': 'Duplicate Course',
    'level': 'UG',
    'duration': '3 Yrs',
    'overview': 'Duplicate'
}, follow_redirects=True)
assert res_dup.status_code == 200
assert "already exists" in res_dup.data.decode('utf-8')
print("  -> PASSED (Duplicate course code rejected with flash warning)")

# 4. Add Learning Outcome
print("\n[4/12] Testing POST /admin/course/outcome/add/<course_id>...")
res_out = client.post(f'/admin/course/outcome/add/{created_course.id}', data={
    'content': 'Proficiency in Neural Networks, PyTorch, and TensorFlow.'
}, follow_redirects=True)
assert res_out.status_code == 200

outcomes = created_course.outcome_records
assert len(outcomes) == 1
assert outcomes[0].content == 'Proficiency in Neural Networks, PyTorch, and TensorFlow.'
print("  -> PASSED (Learning outcome added to course)")

# 5. Delete Learning Outcome
print("\n[5/12] Testing POST /admin/course/outcome/delete/<outcome_id>...")
outcome_id = outcomes[0].id
res_del_out = client.post(f'/admin/course/outcome/delete/{outcome_id}', follow_redirects=True)
assert res_del_out.status_code == 200
assert db.session.get(models.CourseOutcome, outcome_id) is None
print("  -> PASSED (Learning outcome deleted)")

# 6. Add Curriculum Semester
print("\n[6/12] Testing POST /admin/course/semester/add/<course_id>...")
res_sem = client.post(f'/admin/course/semester/add/{created_course.id}', data={
    'semester_name': 'Semester I'
}, follow_redirects=True)
assert res_sem.status_code == 200

semesters = created_course.semesters
assert len(semesters) == 1
assert semesters[0].semester_name == 'Semester I'
print("  -> PASSED (Curriculum Semester I added)")

# 7. Add Curriculum Subject
print("\n[7/12] Testing POST /admin/course/subject/add/<semester_id>...")
sem_id = semesters[0].id
res_subj = client.post(f'/admin/course/subject/add/{sem_id}', data={
    'subject_name': 'Linear Algebra & Neural Computing'
}, follow_redirects=True)
assert res_subj.status_code == 200

subjects = semesters[0].subjects
assert len(subjects) == 1
assert subjects[0].subject_name == 'Linear Algebra & Neural Computing'
print("  -> PASSED (Curriculum subject added)")

# 8. Cascade Deletion Behavior
print("\n[8/12] Testing cascade deletion behavior...")
sub_id = subjects[0].id
c_id = created_course.id

res_del_c = client.post(f'/admin/course/delete/{c_id}', follow_redirects=True)
assert res_del_c.status_code == 200

assert db.session.get(models.Course, c_id) is None
assert db.session.get(models.CurriculumSemester, sem_id) is None
assert db.session.get(models.CurriculumSubject, sub_id) is None
print("  -> PASSED (Deleting course cascades and deletes semesters & subjects)")

# 9. Cross-Tenant Attack Protection (returns HTTP 403)
print("\n[9/12] Testing cross-tenant attack protection...")
other_college = models.College.query.filter_by(slug='step11b-other-tenant').first()
if not other_college:
    other_college = models.College(name='Step 11B Other Tenant', slug='step11b-other-tenant')
    db.session.add(other_college)
    db.session.commit()

other_course = models.Course(
    college_id=other_college.id,
    code='SECRET_B',
    name='Other College Secret Course',
    level='UG',
    duration='3 Yrs',
    affiliation='BCU',
    overview='Secret',
    eligibility='Secret'
)
db.session.add(other_course)
db.session.commit()

res_cross_del = client.post(f'/admin/course/delete/{other_course.id}')
assert res_cross_del.status_code == 403, f"Expected 403, got {res_cross_del.status_code}"

db.session.delete(other_course)
db.session.delete(other_college)
db.session.commit()
print("  -> PASSED (Cross-tenant modification attempt blocked with HTTP 403)")

# 10. Module Admin Access Control (Revoked Access)
print("\n[10/12] Testing module admin access restriction when Super Admin revokes 'academics'...")
client.get('/logout')

try:
    # Super Admin revokes academics admin access
    client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
    cfg_acad = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='academics').first()
    cfg_acad.admin_access = False
    db.session.commit()
    client.get('/logout')

    # College Admin attempts action
    client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
    res_revoked = client.post('/admin/course/add', data={
        'code': 'REVOKED',
        'name': 'Revoked Course',
        'level': 'UG',
        'duration': '3 Yrs',
        'overview': 'Revoked'
    })
    assert res_revoked.status_code == 403, f"Expected 403, got {res_revoked.status_code}"
    assert models.Course.query.filter_by(college_id=college.id, code='REVOKED').first() is None
    print("  -> PASSED (Module access restriction enforced with HTTP 403 when Super Admin revokes permission)")
finally:
    # Always restore academics admin access
    client.get('/logout')
    client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
    cfg_acad = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='academics').first()
    if cfg_acad:
        cfg_acad.admin_access = True
        db.session.commit()
    client.get('/logout')

# 11. Admin Dashboard View
print("\n[11/12] Testing Admin Portal UI rendering...")
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
res_admin = client.get('/admin')
assert res_admin.status_code == 200
assert "Course &amp; Curriculum Management" in res_admin.data.decode('utf-8') or "Course & Curriculum Management" in res_admin.data.decode('utf-8')
client.get('/logout')
print("  -> PASSED (Course management section rendered on admin dashboard)")

# 12. Public Routes Health Verification
print("\n[12/12] Verifying public academic routes health...")
assert client.get('/academics').status_code == 200
assert client.get('/departments').status_code == 200
assert client.get('/course/bca').status_code == 200
print("  -> PASSED (Public course routes operational)")

print("\n==================================================")
print(" ALL 12 STEP 11B ADMIN MANAGEMENT TESTS PASSED 100%!")
print("==================================================")
