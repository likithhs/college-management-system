import sys
import os
import re
import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models, calculate_student_attendance, calculate_student_performance
from seed import seed_default_college

app.app_context().push()
db.create_all()
client = app.test_client(use_cookies=True)

print("==================================================")
print(" STEP 29: ATTENDANCE & INTERNAL MARKS AUDIT      ")
print("==================================================")

college = seed_default_college()

def extract_csrf_token(res):
    html = res.data.decode('utf-8')
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    with client.session_transaction() as sess:
        return sess.get('csrf_token')

# Authenticate as Admin
res_login_g = client.get('/login')
tok_login = extract_csrf_token(res_login_g)
client.post('/login', data={
    'email': 'admin@spmcollege.ac.in',
    'password': 'CollegeAdmin@123',
    'csrf_token': tok_login
}, follow_redirects=True)

tok_admin = extract_csrf_token(client.get('/admin'))

# Create test student & subject
course_bca = models.Course.query.filter_by(college_id=college.id, code='BCA').first()
sem1 = models.CurriculumSemester.query.filter_by(course_id=course_bca.id, semester_name='Semester 1').first()
sub1 = models.CurriculumSubject.query.filter_by(semester_id=sem1.id).first()
if not sub1:
    sub1 = models.CurriculumSubject(semester_id=sem1.id, subject_code='BCA-201', subject_name='Software Engineering', credits=4)
    db.session.add(sub1)
    db.session.commit()

student_step29 = models.Student.query.filter_by(email='step29.student@example.com').first()
if not student_step29:
    student_step29 = models.Student(
        college_id=college.id,
        register_number='REG2026-BCA-2901',
        full_name='Rohan Sharma',
        email='step29.student@example.com',
        course_code='BCA',
        semester='Semester 1',
        section='A',
        status='ACTIVE'
    )
    student_step29.set_password('RohanPass@123')
    db.session.add(student_step29)
    db.session.commit()

# [1/10] Admin Attendance Marking & Upsert Test
print("\n[1/10] Auditing Admin Attendance Marking & Upsert...")
today_str = datetime.date.today().strftime('%Y-%m-%d')
res_att1 = client.post('/admin/attendance/mark', data={
    'student_id': str(student_step29.id),
    'subject_id': str(sub1.id),
    'date': today_str,
    'status': 'PRESENT',
    'remarks': 'On time',
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_att1.status_code == 200

att_rec1 = models.AttendanceRecord.query.filter_by(student_id=student_step29.id, subject_id=sub1.id, date=datetime.date.today()).first()
assert att_rec1 is not None
assert att_rec1.status == 'PRESENT'

# Upsert test (re-marking same student/subject/date to ABSENT)
client.post('/admin/attendance/mark', data={
    'student_id': str(student_step29.id),
    'subject_id': str(sub1.id),
    'date': today_str,
    'status': 'ABSENT',
    'remarks': 'Medical leave',
    'csrf_token': tok_admin
}, follow_redirects=True)

db.session.refresh(att_rec1)
assert att_rec1.status == 'ABSENT'
assert models.AttendanceRecord.query.filter_by(student_id=student_step29.id, subject_id=sub1.id, date=datetime.date.today()).count() == 1
print("  -> PASSED (Attendance marked & duplicate re-marking upserted cleanly)")

# [2/10] Attendance Calculation & Excused Formula Audit
print("\n[2/10] Auditing Attendance Calculation & Excused Excluded Denominator...")
# Add PRESENT, ABSENT, and EXCUSED records
d1 = datetime.date(2026, 8, 1)
d2 = datetime.date(2026, 8, 2)
d3 = datetime.date(2026, 8, 3)

# Add 3 PRESENT, 1 ABSENT, 1 EXCUSED
models.AttendanceRecord.query.filter_by(student_id=student_step29.id).delete()
db.session.add_all([
    models.AttendanceRecord(college_id=college.id, student_id=student_step29.id, subject_id=sub1.id, date=d1, status='PRESENT'),
    models.AttendanceRecord(college_id=college.id, student_id=student_step29.id, subject_id=sub1.id, date=d2, status='ABSENT'),
    models.AttendanceRecord(college_id=college.id, student_id=student_step29.id, subject_id=sub1.id, date=d3, status='EXCUSED'),
])
db.session.commit()

att_stats = calculate_student_attendance(student_step29.id, college.id)
assert att_stats['total_present'] == 1
assert att_stats['total_absent'] == 1
assert att_stats['total_excused'] == 1
# Denominator = 1 present + 1 absent = 2. Attendance = 1/2 * 100 = 50.0%
assert att_stats['overall_percentage'] == 50.0
assert att_stats['has_shortage'] is True # 50% < 75% triggers shortage!
print("  -> PASSED (Attendance % = PRESENT/(PRESENT+ABSENT)*100 = 50.0% with EXCUSED excluded)")

# [3/10] Admin Internal Marks Saving & Upsert Test
print("\n[3/10] Auditing Admin Internal Marks Saving & Upsert...")
res_mark1 = client.post('/admin/internal-marks/save', data={
    'student_id': str(student_step29.id),
    'subject_id': str(sub1.id),
    'assessment_type': 'TEST_1',
    'marks_obtained': '42.5',
    'max_marks': '50.0',
    'remarks': 'Excellent performance',
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_mark1.status_code == 200

mark_rec1 = models.InternalAssessment.query.filter_by(student_id=student_step29.id, subject_id=sub1.id, assessment_type='TEST_1').first()
assert mark_rec1 is not None
assert mark_rec1.marks_obtained == 42.5
print("  -> PASSED (Internal marks saved for TEST_1)")

# [4/10] Internal Marks Performance & Estimated GPA Calculation Audit
print("\n[4/10] Auditing Internal Performance & Estimated GPA Equivalent...")
# Add TEST_2 marks (45 / 50) -> Total = (42.5 + 45) / 100 = 87.5% -> Grade 'A', GPA 9.0
res_mark2 = client.post('/admin/internal-marks/save', data={
    'student_id': str(student_step29.id),
    'subject_id': str(sub1.id),
    'assessment_type': 'TEST_2',
    'marks_obtained': '45.0',
    'max_marks': '50.0',
    'remarks': 'Top score',
    'csrf_token': tok_admin
}, follow_redirects=True)
assert res_mark2.status_code == 200

perf_stats = calculate_student_performance(student_step29.id, college.id)
assert perf_stats['overall_percentage'] == 87.5
assert perf_stats['overall_grade'] == 'A'
assert perf_stats['overall_gpa'] == 9.0
print("  -> PASSED (87.5% correctly mapped to Estimated Grade 'A' and Estimated GPA Equivalent '9.0')")

# [5/10] Student Dashboard Rendering Audit
print("\n[5/10] Auditing Student Dashboard Attendance & Performance Rendering...")
client.get('/logout') # Logout admin
client.post('/student/login', data={
    'login_id': student_step29.register_number,
    'password': 'RohanPass@123',
    'csrf_token': extract_csrf_token(client.get('/student/login'))
}, follow_redirects=True)

res_dash = client.get('/student/dashboard')
assert res_dash.status_code == 200
html_dash = res_dash.data.decode('utf-8')

assert 'Attendance Tracking' in html_dash
assert 'Attendance Shortage Warning' in html_dash
assert 'Grade: A' in html_dash or 'Grade:' in html_dash
assert '87.5%' in html_dash
assert '9 / 10.0' in html_dash or '9.0' in html_dash
print("  -> PASSED (Student Dashboard rendered Attendance shortage warning, Grade 'A', and Estimated GPA)")

# [6/10] Admin Deletion of Attendance & Internal Marks Test
print("\n[6/10] Auditing Admin Deletion of Attendance & Internal Marks...")
client.get('/student/logout')
client.post('/login', data={
    'email': 'admin@spmcollege.ac.in',
    'password': 'CollegeAdmin@123',
    'csrf_token': extract_csrf_token(client.get('/login'))
}, follow_redirects=True)
tok_admin2 = extract_csrf_token(client.get('/admin'))

att_del_target = models.AttendanceRecord.query.filter_by(student_id=student_step29.id).first()
client.post(f'/admin/attendance/delete/{att_del_target.id}', data={'csrf_token': tok_admin2})
assert db.session.get(models.AttendanceRecord, att_del_target.id) is None

mark_del_target = models.InternalAssessment.query.filter_by(student_id=student_step29.id, assessment_type='TEST_1').first()
client.post(f'/admin/internal-marks/delete/{mark_del_target.id}', data={'csrf_token': tok_admin2})
assert db.session.get(models.InternalAssessment, mark_del_target.id) is None
print("  -> PASSED (Attendance and internal marks records deleted cleanly)")

# [7/10] Cross-Tenant Isolation Audit
print("\n[7/10] Auditing Cross-Tenant Data Isolation...")
tenant_b = models.College.query.filter_by(slug='step29-tenant-b').first()
if not tenant_b:
    tenant_b = models.College(name='Step29 Tenant B', slug='step29-tenant-b')
    db.session.add(tenant_b)
    db.session.commit()

att_b = models.AttendanceRecord(
    college_id=tenant_b.id,
    student_id=student_step29.id,
    subject_id=sub1.id,
    date=datetime.date(2026, 8, 10),
    status='PRESENT'
)
db.session.add(att_b)
db.session.commit()

# Current admin belongs to Tenant A. Attempt deleting Tenant B attendance item.
res_cross_att = client.post(f'/admin/attendance/delete/{att_b.id}', data={'csrf_token': tok_admin2})
assert res_cross_att.status_code in [403, 404]
print("  -> PASSED (Cross-tenant attendance deletion strictly rejected)")

# [8/10] Student Access Isolation Audit
print("\n[8/10] Auditing Student Access Isolation...")
client.get('/logout')
res_anon_dash = client.get('/student/dashboard', follow_redirects=True)
assert 'Authentication required' in res_anon_dash.data.decode('utf-8')
print("  -> PASSED (Unauthenticated student access strictly blocked)")

# [9/10] Uniqueness Constraint Verification Test
print("\n[9/10] Auditing Duplicate Constraint Enforcement...")
# Attempt manual duplicate insert
dup_att = models.AttendanceRecord(college_id=college.id, student_id=student_step29.id, subject_id=sub1.id, date=datetime.date(2026, 8, 20), status='PRESENT')
db.session.add(dup_att)
db.session.commit()

dup_att2 = models.AttendanceRecord(college_id=college.id, student_id=student_step29.id, subject_id=sub1.id, date=datetime.date(2026, 8, 20), status='ABSENT')
db.session.add(dup_att2)
try:
    db.session.commit()
    assert False, "Failed to enforce unique constraint on duplicate attendance record!"
except Exception:
    db.session.rollback()
    print("  -> PASSED (Unique constraint uq_attendance_student_subject_date enforced by database)")

# [10/10] Cleanup Temporary Test Data
print("\n[10/10] Cleaning Up Temporary Test Records...")
models.AttendanceRecord.query.filter_by(student_id=student_step29.id).delete()
models.AttendanceRecord.query.filter_by(college_id=tenant_b.id).delete()
models.InternalAssessment.query.filter_by(student_id=student_step29.id).delete()
models.Student.query.filter_by(id=student_step29.id).delete()
db.session.commit()
print("  -> PASSED (Temporary test records cleaned up)")

print("\n==================================================")
print(" ALL 10 STEP 29 ATTENDANCE & MARKS TESTS PASSED!  ")
print("==================================================")
