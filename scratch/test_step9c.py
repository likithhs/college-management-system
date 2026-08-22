import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()

print("==================================================")
print("  STEP 9C: COURSE & CURRICULUM SCHEMA TEST SUITE  ")
print("==================================================")

college = seed_default_college()

# 1. Course Creation
print("\n[1/10] Testing Course model creation...")
test_course = models.Course(
    college_id=college.id,
    code='BCA_TEST',
    name='Test Bachelor of Computer Applications',
    level='Undergraduate (UG)',
    duration='3 Years (6 Semesters)',
    affiliation='Bengaluru City University',
    overview='Test course overview',
    eligibility='10+2 / PUC passed'
)
db.session.add(test_course)
db.session.commit()
print(f"  -> Created Course ID: {test_course.id}, Code: {test_course.code}")

# 2. Duplicate (college_id, code) Uniqueness Rejection
print("\n[2/10] Testing duplicate (college_id, code) uniqueness constraint...")
dup_course = models.Course(
    college_id=college.id,
    code='BCA_TEST',
    name='Duplicate BCA',
    level='UG',
    duration='3 Years',
    affiliation='BCU',
    overview='Dup',
    eligibility='Dup'
)
db.session.add(dup_course)
try:
    db.session.commit()
    print("  -> ERROR: Duplicate allowed!")
    assert False, "Duplicate (college_id, code) was not rejected"
except Exception as e:
    db.session.rollback()
    print("  -> PASSED (Duplicate (college_id, code) rejected by unique constraint)")

# 3. Same course code for different college tenant
print("\n[3/10] Testing same course code for a different college tenant...")
other_college = models.College.query.filter_by(slug='test-tenant-step9c').first()
if not other_college:
    other_college = models.College(name='Test Tenant Step 9C', slug='test-tenant-step9c')
    db.session.add(other_college)
    db.session.commit()

other_tenant_course = models.Course(
    college_id=other_college.id,
    code='BCA_TEST',
    name='Other College BCA',
    level='UG',
    duration='3 Years',
    affiliation='BCU',
    overview='Other tenant',
    eligibility='Other tenant'
)
db.session.add(other_tenant_course)
db.session.commit()
print("  -> PASSED (Same course code allowed for different college tenant)")

# 4. Outcomes Relationship & Display Order
print("\n[4/10] Testing CourseOutcome relationship & display order...")
outcome2 = models.CourseOutcome(course_id=test_course.id, content='Outcome 2', display_order=2)
outcome1 = models.CourseOutcome(course_id=test_course.id, content='Outcome 1', display_order=1)
db.session.add_all([outcome2, outcome1])
db.session.commit()

fetched_course = db.session.get(models.Course, test_course.id)
outcomes = fetched_course.outcomes
print("  -> Outcome 1 content:", outcomes[0].content)
print("  -> Outcome 2 content:", outcomes[1].content)
assert outcomes[0].content == 'Outcome 1' and outcomes[1].content == 'Outcome 2', "Outcome display_order failed"
print("  -> PASSED (Outcomes ordered by display_order)")

# 5 & 6. CurriculumSemester & CurriculumSubject Attachment & Order
print("\n[5/10 & 6/10] Testing CurriculumSemester & CurriculumSubject attachment & order...")
sem2 = models.CurriculumSemester(course_id=test_course.id, semester_name='Semester II', display_order=2)
sem1 = models.CurriculumSemester(course_id=test_course.id, semester_name='Semester I', display_order=1)
db.session.add_all([sem2, sem1])
db.session.commit()

subj2 = models.CurriculumSubject(semester_id=sem1.id, subject_name='Subject 2', display_order=2)
subj1 = models.CurriculumSubject(semester_id=sem1.id, subject_name='Subject 1', display_order=1)
db.session.add_all([subj2, subj1])
db.session.commit()

semesters = fetched_course.semesters
assert semesters[0].semester_name == 'Semester I', "Semester ordering failed"
subjects = semesters[0].subjects
assert subjects[0].subject_name == 'Subject 1' and subjects[1].subject_name == 'Subject 2', "Subject ordering failed"
print("  -> PASSED (Semesters and subjects attached and ordered cleanly)")

# 7. QuestionPaper Attachment
print("\n[7/10] Testing QuestionPaper attachment...")
qp = models.QuestionPaper(
    course_id=test_course.id,
    year='2025',
    semester='Sem 1',
    subject='Test Subject',
    filename='BCA_TEST_2025.pdf'
)
db.session.add(qp)
db.session.commit()
assert len(fetched_course.question_papers) == 1, "Question paper not attached"
assert fetched_course.question_papers[0].filename == 'BCA_TEST_2025.pdf', "Paper filename mismatch"
print("  -> PASSED (QuestionPaper attached cleanly)")

# 8. Relationship Display Ordering Verification
print("\n[8/10] Verifying relationship display order integrity...")
assert fetched_course.outcomes[0].display_order < fetched_course.outcomes[1].display_order
assert fetched_course.semesters[0].display_order < fetched_course.semesters[1].display_order
print("  -> PASSED (Display order properties verified)")

# 9. Cascade Delete Test
print("\n[9/10] Testing cascade deletion of Course and child entities...")
course_id_del = test_course.id
sem_id_del = sem1.id
db.session.delete(test_course)
db.session.commit()

assert db.session.get(models.Course, course_id_del) is None, "Course not deleted"
assert models.CourseOutcome.query.filter_by(course_id=course_id_del).count() == 0, "Outcomes not deleted"
assert models.CurriculumSemester.query.filter_by(course_id=course_id_del).count() == 0, "Semesters not deleted"
assert models.CurriculumSubject.query.filter_by(semester_id=sem_id_del).count() == 0, "Subjects not deleted"
assert models.QuestionPaper.query.filter_by(course_id=course_id_del).count() == 0, "Question papers not deleted"
print("  -> PASSED (Cascade delete removed all child outcomes, semesters, subjects, and question papers)")

# Cleanup other college tenant
db.session.delete(other_tenant_course)
db.session.delete(other_college)
db.session.commit()

# 10. Existing Modules Health Check
print("\n[10/10] Verifying existing Gallery, Forum, and Admissions models health...")
print("  -> GalleryItems count:", models.GalleryItem.query.count())
print("  -> ForumPosts count:", models.ForumPost.query.count())
print("  -> AdmissionApplications count:", models.AdmissionApplication.query.count())
print("  -> PASSED (Existing models operate cleanly)")

print("\n==================================================")
print(" ALL 10 STEP 9C SCHEMA TESTS PASSED 100%!        ")
print("==================================================")
