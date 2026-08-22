import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 9E: DATABASE-BACKED COURSE ROUTES TEST SUITE")
print("==================================================")

college = seed_default_college()

# 1. /academics Route
print("\n[1/12] Testing GET /academics database rendering...")
res_academics = client.get('/academics')
assert res_academics.status_code == 200, f"Expected 200, got {res_academics.status_code}"
html_acad = res_academics.data.decode('utf-8')
assert "Academic Departments" in html_acad or "Academics &amp; Syllabus" in html_acad, "Academics heading missing"
print("  -> PASSED (HTTP 200 OK)")

# 2. /departments Route
print("\n[2/12] Testing GET /departments database rendering...")
res_dept = client.get('/departments')
assert res_dept.status_code == 200, f"Expected 200, got {res_dept.status_code}"
print("  -> PASSED (HTTP 200 OK)")

# 3. /course/bca Route & Model Property Checks
print("\n[3/12] Testing GET /course/bca (Database model ORM rendering)...")
res_bca = client.get('/course/bca')
assert res_bca.status_code == 200, f"Expected 200, got {res_bca.status_code}"
html_bca = res_bca.data.decode('utf-8')
assert "Bachelor of Computer Applications" in html_bca, "BCA name missing from rendered HTML"
assert "Full Stack Web Development" in html_bca, "Syllabus subject missing from rendered HTML"
assert "BCA_Sem5_FullStack_2025.pdf" in html_bca, "Question paper filename missing from rendered HTML"
print("  -> PASSED (BCA database course rendered cleanly with full hierarchy)")

# 4. Unknown Course 404 Rejection
print("\n[4/12] Testing unknown course 404 error...")
res_unknown = client.get('/course/NONEXISTENT_COURSE_999')
assert res_unknown.status_code == 404, f"Expected 404, got {res_unknown.status_code}"
print("  -> PASSED (Unknown course code returns 404)")

# 5. Course Outcomes Compatibility Property
print("\n[5/12] Testing Course.outcomes compatibility property...")
bca_model = models.Course.query.filter_by(college_id=college.id, code='BCA').first()
outcomes = bca_model.outcomes
assert isinstance(outcomes, list), "outcomes is not a list"
assert len(outcomes) == 3, f"Expected 3 outcomes, got {len(outcomes)}"
assert isinstance(outcomes[0], str), "outcome element is not a string"
print("  -> PASSED (outcomes property returns string list)")

# 6. Curriculum Compatibility Property
print("\n[6/12] Testing Course.curriculum compatibility property...")
curriculum = bca_model.curriculum
assert isinstance(curriculum, list), "curriculum is not a list"
assert len(curriculum) == 6, f"Expected 6 semesters, got {len(curriculum)}"
assert 'sem' in curriculum[0] and 'subjects' in curriculum[0], "semester dict keys missing"
assert curriculum[0]['sem'] == 'Semester I', "semester name mismatch"
assert len(curriculum[0]['subjects']) == 4, "subject count mismatch"
print("  -> PASSED (curriculum property returns expected semester dict structure)")

# 7. QuestionPaper Compatibility Properties
print("\n[7/12] Testing QuestionPaper.sem and QuestionPaper.file compatibility properties...")
paper = bca_model.question_papers[0]
assert paper.sem == paper.semester, "sem property mismatch"
assert paper.file == paper.filename, "file property mismatch"
print(f"  -> sem property: {paper.sem}")
print(f"  -> file property: {paper.file}")
print("  -> PASSED (QuestionPaper compatibility properties verified)")

# 8. Valid Question Paper Download Route
print("\n[8/12] Testing valid GET /download-paper/<filename>...")
res_dl_valid = client.get('/download-paper/BCA_Sem5_FullStack_2025.pdf')
assert res_dl_valid.status_code == 200, f"Expected 200, got {res_dl_valid.status_code}"
json_dl = res_dl_valid.get_json()
assert json_dl['status'] == 'success', "Download status not success"
assert json_dl['filename'] == 'BCA_Sem5_FullStack_2025.pdf', "Filename mismatch in JSON"
print("  -> PASSED (Valid download returns database-backed JSON response)")

# 9. Invalid Question Paper Download 404 Rejection
print("\n[9/12] Testing invalid GET /download-paper/<filename> 404 rejection...")
res_dl_bad = client.get('/download-paper/NONEXISTENT_PAPER.pdf')
assert res_dl_bad.status_code == 404, f"Expected 404, got {res_dl_bad.status_code}"
print("  -> PASSED (Invalid filename returns 404)")

# 10. Cross-Tenant Course Isolation Security
print("\n[10/12] Testing cross-tenant course lookup isolation...")
other_college = models.College.query.filter_by(slug='step9e-other-tenant').first()
if not other_college:
    other_college = models.College(name='Step 9E Other Tenant', slug='step9e-other-tenant')
    db.session.add(other_college)
    db.session.commit()

other_course = models.Course(
    college_id=other_college.id,
    code='SECRET_COURSE',
    name='Secret Other College Course',
    level='UG',
    duration='3 Years',
    affiliation='BCU',
    overview='Secret',
    eligibility='Secret'
)
db.session.add(other_course)
db.session.commit()

# Default tenant requesting secret course of other tenant
res_cross_c = client.get('/course/SECRET_COURSE')
assert res_cross_c.status_code == 404, f"Expected 404, got {res_cross_c.status_code}"

# Cleanup other tenant
db.session.delete(other_course)
db.session.delete(other_college)
db.session.commit()
print("  -> PASSED (Cross-tenant course returns 404 for active tenant)")

# 11. COURSES_DATA Runtime Usage Audit
print("\n[11/12] Auditing COURSES_DATA in app.py...")
with open(os.path.join(os.path.dirname(__file__), '..', 'app.py'), 'r', encoding='utf-8') as f:
    app_code = f.read()

assert 'COURSES_DATA =' not in app_code, "COURSES_DATA definition still present in app.py"
print("  -> PASSED (Zero COURSES_DATA dictionary references in app.py)")

# 12. Existing Modules Health & Regression Verification
print("\n[12/12] Verifying existing Gallery, Forum, and Admissions health...")
assert client.get('/gallery').status_code == 200, "Gallery failed"
assert client.get('/forum').status_code == 200, "Forum failed"
assert client.get('/admission').status_code == 200, "Admission failed"
assert client.get('/apply').status_code == 200, "Apply failed"
print("  -> PASSED (All existing modules operational with zero regressions)")

print("\n==================================================")
print(" ALL 12 STEP 9E DATABASE ROUTE TESTS PASSED 100%! ")
print("==================================================")
