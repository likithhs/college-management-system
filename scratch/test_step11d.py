import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 11D: QUESTION PAPER ADMIN MANAGEMENT       ")
print("==================================================")

college = seed_default_college()

# Reset academics admin_access to True for clean test state
cfg_init = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='academics').first()
if cfg_init:
    cfg_init.admin_access = True
    db.session.commit()

# 1. Unauthenticated Access Protection
print("\n[1/11] Testing unauthenticated admin access protection...")
res_unauth = client.post('/admin/question-paper/add', data={'course_id': 1, 'year': '2026', 'semester': 'Sem 1', 'subject': 'Test', 'filename': 'Test.pdf'})
assert res_unauth.status_code == 302 and 'login' in res_unauth.headers.get('Location', '')
print("  -> PASSED (Unauthenticated request redirected to /login)")

# Authenticate as College Admin
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})

# Resolve target course (BCA)
bca_course = models.Course.query.filter_by(college_id=college.id, code='BCA').first()
assert bca_course is not None, "BCA course missing"

# 2. Add New Question Paper
print("\n[2/11] Testing POST /admin/question-paper/add...")
res_add_qp = client.post('/admin/question-paper/add', data={
    'course_id': bca_course.id,
    'year': '2026',
    'semester': 'Sem 6',
    'subject': 'Quantum Computing & AI',
    'filename': 'BCA_Sem6_Quantum_2026.pdf'
}, follow_redirects=True)
assert res_add_qp.status_code == 200

created_paper = models.QuestionPaper.query.filter_by(filename='BCA_Sem6_Quantum_2026.pdf').first()
assert created_paper is not None, "Question paper missing from database"
assert created_paper.course_id == bca_course.id
assert created_paper.subject == 'Quantum Computing & AI'
print("  -> PASSED (New question paper entry created successfully)")

# 3. Required Field Validation
print("\n[3/11] Testing required field validation...")
res_val_bad = client.post('/admin/question-paper/add', data={
    'course_id': bca_course.id,
    'year': '',
    'semester': 'Sem 1',
    'subject': 'Incomplete',
    'filename': ''
}, follow_redirects=True)
assert res_val_bad.status_code == 200
assert "Validation Error" in res_val_bad.data.decode('utf-8')
print("  -> PASSED (Validation error displayed for missing fields)")

# 4. Public Course Page & Download Route Rendering
print("\n[4/11 & 10/11] Verifying public rendering on /course/bca & /download-paper/<filename>...")
res_course_view = client.get('/course/bca')
assert res_course_view.status_code == 200
assert "BCA_Sem6_Quantum_2026.pdf" in res_course_view.data.decode('utf-8')

res_dl_view = client.get('/download-paper/BCA_Sem6_Quantum_2026.pdf')
assert res_dl_view.status_code == 200
json_dl = res_dl_view.get_json()
assert json_dl['filename'] == 'BCA_Sem6_Quantum_2026.pdf'
print("  -> PASSED (Question paper renders on public course detail page & download API)")

# 5. Delete Question Paper
print("\n[5/11] Testing POST /admin/question-paper/delete/<paper_id>...")
paper_id = created_paper.id
res_del_qp = client.post(f'/admin/question-paper/delete/{paper_id}', follow_redirects=True)
assert res_del_qp.status_code == 200
assert db.session.get(models.QuestionPaper, paper_id) is None
print("  -> PASSED (Question paper deleted from database)")

# 6 & 7. Cross-Tenant Attack Protection (returns HTTP 403)
print("\n[6/11 & 7/11] Testing cross-tenant attack protection...")
other_college = models.College.query.filter_by(slug='step11d-other-tenant').first()
if not other_college:
    other_college = models.College(name='Step 11D Other Tenant', slug='step11d-other-tenant')
    db.session.add(other_college)
    db.session.commit()

other_course = models.Course(college_id=other_college.id, code='OTHER_CS', name='Other Course', level='UG', duration='3 Yrs', affiliation='BCU', overview='Desc', eligibility='Elig')
db.session.add(other_course)
db.session.commit()

other_paper = models.QuestionPaper(course_id=other_course.id, year='2026', semester='Sem 1', subject='Secret Subject', filename='Secret_2026.pdf')
db.session.add(other_paper)
db.session.commit()

# Cross-tenant paper addition attempt
res_cross_add = client.post('/admin/question-paper/add', data={
    'course_id': other_course.id,
    'year': '2026',
    'semester': 'Sem 1',
    'subject': 'Attacker Paper',
    'filename': 'Attacker.pdf'
})
assert res_cross_add.status_code == 403, f"Expected 403 for cross-tenant add, got {res_cross_add.status_code}"

# Cross-tenant paper deletion attempt
res_cross_del = client.post(f'/admin/question-paper/delete/{other_paper.id}')
assert res_cross_del.status_code == 403, f"Expected 403 for cross-tenant delete, got {res_cross_del.status_code}"

db.session.delete(other_paper)
db.session.delete(other_course)
db.session.delete(other_college)
db.session.commit()
print("  -> PASSED (Cross-tenant question paper additions & deletions blocked with HTTP 403)")

# 8. Module Admin Access Control (Revoked Access)
print("\n[8/11] Testing module admin access restriction when Super Admin revokes 'academics'...")
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
    res_revoked = client.post('/admin/question-paper/add', data={
        'course_id': bca_course.id,
        'year': '2026',
        'semester': 'Sem 1',
        'subject': 'Revoked Paper',
        'filename': 'Revoked.pdf'
    })
    assert res_revoked.status_code == 403, f"Expected 403, got {res_revoked.status_code}"
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

# 9. Invalid Paper ID 404 Rejection
print("\n[9/11] Testing invalid paper ID 404 rejection...")
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
res_404_del = client.post('/admin/question-paper/delete/999999')
assert res_404_del.status_code == 404, f"Expected 404, got {res_404_del.status_code}"
print("  -> PASSED (Deleting non-existent paper returns HTTP 404)")

# 11. Public Routes Health Check
print("\n[11/11] Verifying public academic routes health...")
assert client.get('/academics').status_code == 200
assert client.get('/departments').status_code == 200
assert client.get('/course/bca').status_code == 200
print("  -> PASSED (Public course & academics routes operational)")

print("\n==================================================")
print(" ALL 11 STEP 11D ADMIN MANAGEMENT TESTS PASSED 100%!")
print("==================================================")
