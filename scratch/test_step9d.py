import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college, seed_default_courses

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 9D: IDEMPOTENT COURSE SEEDING TEST SUITE   ")
print("==================================================")

# 1. Trigger Seeding
college = seed_default_college()

# 2. Check Database Record Counts
print("\n[1/8] Verifying seeded database record counts...")
course_count = models.Course.query.filter_by(college_id=college.id).count()
outcome_count = models.CourseOutcome.query.join(models.Course).filter(models.Course.college_id == college.id).count()
sem_count = models.CurriculumSemester.query.join(models.Course).filter(models.Course.college_id == college.id).count()
subj_count = models.CurriculumSubject.query.join(models.CurriculumSemester).join(models.Course).filter(models.Course.college_id == college.id).count()
paper_count = models.QuestionPaper.query.join(models.Course).filter(models.Course.college_id == college.id).count()

print(f"  -> Courses count: {course_count} (Expected: 9)")
print(f"  -> CourseOutcomes count: {outcome_count} (Expected: 14)")
print(f"  -> CurriculumSemesters count: {sem_count} (Expected: 36)")
print(f"  -> CurriculumSubjects count: {subj_count} (Expected: 136)")
print(f"  -> QuestionPapers count: {paper_count} (Expected: 19)")

assert course_count == 9, f"Expected 9 courses, got {course_count}"
assert outcome_count == 14, f"Expected 14 outcomes, got {outcome_count}"
assert sem_count == 36, f"Expected 36 semesters, got {sem_count}"
assert subj_count == 136, f"Expected 136 subjects, got {subj_count}"
assert paper_count == 19, f"Expected 19 papers, got {paper_count}"
print("  -> PASSED (All record counts match expected values)")

# 3. Test Idempotency (Run seed_default_courses second time)
print("\n[2/8] Testing idempotency (running seed_default_courses a second time)...")
seed_default_courses(college)
c_count_2 = models.Course.query.filter_by(college_id=college.id).count()
o_count_2 = models.CourseOutcome.query.join(models.Course).filter(models.Course.college_id == college.id).count()
s_count_2 = models.CurriculumSemester.query.join(models.Course).filter(models.Course.college_id == college.id).count()
sub_count_2 = models.CurriculumSubject.query.join(models.CurriculumSemester).join(models.Course).filter(models.Course.college_id == college.id).count()
p_count_2 = models.QuestionPaper.query.join(models.Course).filter(models.Course.college_id == college.id).count()

assert c_count_2 == course_count, "Course count changed on re-seed"
assert o_count_2 == outcome_count, "Outcome count changed on re-seed"
assert s_count_2 == sem_count, "Semester count changed on re-seed"
assert sub_count_2 == subj_count, "Subject count changed on re-seed"
assert p_count_2 == paper_count, "Paper count changed on re-seed"
print("  -> PASSED (Zero duplicate records created on second seeding run)")

# 4. Verify Tenant Ownership Binding
print("\n[3/8] Verifying tenant ownership binding...")
courses = models.Course.query.filter_by(college_id=college.id).all()
for c in courses:
    assert c.college_id == college.id, f"Course {c.code} bound to wrong tenant"
print("  -> PASSED (All 9 courses bound to default college tenant)")

# 5. Verify BCA Data Integrity in Database
print("\n[4/8] Verifying BCA database details...")
bca_db = models.Course.query.filter_by(college_id=college.id, code='BCA').first()
assert bca_db is not None, "BCA not found in DB"
assert len(bca_db.outcomes) == 3, f"Expected 3 outcomes for BCA, got {len(bca_db.outcomes)}"
assert len(bca_db.semesters) == 6, f"Expected 6 semesters for BCA, got {len(bca_db.semesters)}"
assert len(bca_db.question_papers) == 5, f"Expected 5 papers for BCA, got {len(bca_db.question_papers)}"
print(f"  -> BCA Outcomes: {len(bca_db.outcomes)}")
print(f"  -> BCA Semesters: {len(bca_db.semesters)}")
print(f"  -> BCA Question Papers: {len(bca_db.question_papers)}")
print("  -> PASSED (BCA database hierarchy verified)")

# 6. Verify Unmodified Existing Routes Compatibility
print("\n[5/8 - 8/8] Verifying existing routes remain unaffected and functional...")
res_dept = client.get('/departments')
assert res_dept.status_code == 200, f"Expected 200, got {res_dept.status_code}"

res_c_bca = client.get('/course/bca')
assert res_c_bca.status_code == 200, f"Expected 200, got {res_c_bca.status_code}"

res_dl = client.get('/download-paper/BCA_Sem5_FullStack_2025.pdf')
assert res_dl.status_code == 200, f"Expected 200, got {res_dl.status_code}"

res_adm = client.get('/admission')
assert res_adm.status_code == 200, f"Expected 200, got {res_adm.status_code}"

print("  -> /departments: HTTP 200 OK")
print("  -> /course/bca: HTTP 200 OK")
print("  -> /download-paper/BCA_Sem5_FullStack_2025.pdf: HTTP 200 OK")
print("  -> /admission: HTTP 200 OK")
print("  -> PASSED (Existing routes completely functional)")

print("\n==================================================")
print(" ALL 8 STEP 9D SEEDING TESTS PASSED 100%!        ")
print("==================================================")
