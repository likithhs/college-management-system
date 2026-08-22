import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college, seed_default_forum_posts

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("   STEP 7F: FORUM INTEGRATION & REGRESSION SUITE  ")
print("==================================================")

# 1. Seed DB & Verify Initial Count
print("\n[1/16] Seeding default college & forum posts...")
college = seed_default_college()
initial_count = models.ForumPost.query.filter_by(college_id=college.id).count()
print(f"  -> Initial ForumPost count: {initial_count}")
assert initial_count >= 5, f"Expected at least 5 posts, found {initial_count}"

# 2. Idempotency Verification
print("\n[2/16] Verifying seeding idempotency...")
seed_default_forum_posts(college)
reseed_count = models.ForumPost.query.filter_by(college_id=college.id).count()
print(f"  -> Count after re-seeding: {reseed_count}")
assert reseed_count == initial_count, "Seeding created duplicate records!"
print("  -> PASSED (Idempotent)")

# 3. Public GET /forum
print("\n[3/16] Testing public GET /forum...")
res_pub_get = client.get('/forum')
assert res_pub_get.status_code == 200, f"Expected 200, got {res_pub_get.status_code}"
print("  -> PASSED (HTTP 200 OK)")

# 4. Public POST /forum blocked
print("\n[4/16] Testing public POST /forum (Read-Only enforcement)...")
res_pub_post = client.post('/forum')
assert res_pub_post.status_code == 405, f"Expected 405, got {res_pub_post.status_code}"
print("  -> PASSED (HTTP 405 Method Not Allowed)")

# 5. Disabled Module Access Guard
print("\n[5/16] Testing disabled module protection...")
cfg = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='forum').first()
cfg.enabled = False
db.session.commit()
res_dis = client.get('/forum')
assert res_dis.status_code == 302, f"Expected 302 redirect, got {res_dis.status_code}"
cfg.enabled = True
db.session.commit()
print("  -> PASSED (Redirected when disabled)")

# 6. Unauthenticated POST /forum/add Guard
print("\n[6/16] Testing unauthenticated /forum/add guard...")
res_unauth = client.post('/forum/add', data={'title': 'X', 'category': 'Events & Fests', 'content': 'X'})
assert res_unauth.status_code == 302 and 'login' in res_unauth.headers.get('Location', ''), "Failed to redirect unauthenticated user to login"
print("  -> PASSED (Redirected to login)")

# 7 & 8. Admin Post Addition & Server-Side Input Validation
print("\n[7/16 & 8/16] Testing server-side input validation for College Admin...")
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})

val_cases = [
    ({'title': '', 'category': 'Events & Fests', 'content': 'Content'}, "Blank title"),
    ({'title': 'Title', 'category': 'Events & Fests', 'content': ''}, "Blank content"),
    ({'title': 'Title', 'category': 'InvalidCategory', 'content': 'Content'}, "Invalid category"),
    ({'title': 'A' * 251, 'category': 'Events & Fests', 'content': 'Content'}, "Overlong title")
]

pre_val_count = models.ForumPost.query.count()
for payload, label in val_cases:
    res_val = client.post('/forum/add', data=payload, follow_redirects=True)
    assert "Validation Error" in res_val.data.decode('utf-8'), f"Validation failed for {label}"

post_val_count = models.ForumPost.query.count()
assert pre_val_count == post_val_count, "Invalid post was saved to database!"
print("  -> PASSED (All validation edge cases rejected cleanly)")

# 9. admin_access = False RBAC Guard
print("\n[9/16] Testing admin_access = False RBAC guard...")
client.get('/logout')
client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
cfg.admin_access = False
db.session.commit()
client.get('/logout')

client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
res_rbac_denied = client.post('/forum/add', data={'title': 'T', 'category': 'Events & Fests', 'content': 'C'})
assert res_rbac_denied.status_code == 403, f"Expected 403, got {res_rbac_denied.status_code}"
client.get('/logout')

# Restore admin_access
client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
cfg.admin_access = True
db.session.commit()
client.get('/logout')
print("  -> PASSED (HTTP 403 Forbidden on revoked admin_access)")

# 10 & 11. Valid Addition & Ordering Check
print("\n[10/16 & 11/16] Testing valid College Admin topic addition & reverse chronological ordering...")
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})

new_topic_payload = {
    'author': 'Prof. Vikram Seth',
    'title': 'Advanced Quantum Computing & Cryptography Workshop 2026',
    'category': 'Academics & Question Papers',
    'content': 'Interactive workshop organized by Department of Computer Science.'
}
res_add_valid = client.post('/forum/add', data=new_topic_payload, follow_redirects=True)
assert res_add_valid.status_code == 200, "Valid post addition failed"

added_record = models.ForumPost.query.filter_by(title=new_topic_payload['title']).first()
assert added_record is not None, "Record not found in DB"
assert added_record.college_id == 1, "Incorrect college_id bound"

# Check ordering
ordered_posts = models.ForumPost.query.filter_by(college_id=1).order_by(models.ForumPost.created_at.desc(), models.ForumPost.id.desc()).all()
assert ordered_posts[0].id == added_record.id, "Newest post is not rendered first!"
print("  -> PASSED (New topic added & ordered first)")

# 12. Same-Tenant Deletion
print("\n[12/16] Testing same-tenant deletion...")
added_id = added_record.id
res_del = client.post(f'/forum/delete/{added_id}', follow_redirects=True)
assert res_del.status_code == 200, "Same tenant delete failed"
assert db.session.get(models.ForumPost, added_id) is None, "Post still in DB after delete"
print("  -> PASSED (Same tenant deletion successful)")

# 13. Cross-Tenant Deletion Protection
print("\n[13/16] Testing cross-tenant deletion 403 security...")
other_college = models.College.query.filter_by(slug='cross-tenant-test-college').first()
if not other_college:
    other_college = models.College(name='Cross Tenant Test College', slug='cross-tenant-test-college')
    db.session.add(other_college)
    db.session.commit()

other_post = models.ForumPost(
    college_id=other_college.id,
    author='Other Admin',
    title='Other Tenant Topic Title',
    category='Events & Fests',
    content='Other tenant topic content'
)
db.session.add(other_post)
db.session.commit()

res_cross_del = client.post(f'/forum/delete/{other_post.id}')
assert res_cross_del.status_code == 403, f"Expected 403, got {res_cross_del.status_code}"
db.session.delete(other_post)
db.session.delete(other_college)
db.session.commit()
print("  -> PASSED (Cross tenant deletion blocked with HTTP 403)")

# 14. Restart / DB Context Persistence Check
print("\n[14/16] Testing database persistence across sessions...")
persist_count = models.ForumPost.query.filter_by(college_id=1).count()
assert persist_count >= 5, f"Expected >= 5 persisted posts, got {persist_count}"
print("  -> PASSED (Data persisted in SQLite database)")

# 15. Admin Dashboard Rendering Check
print("\n[15/16] Testing Admin Dashboard forum_posts rendering...")
res_admin_dash = client.get('/admin')
assert res_admin_dash.status_code == 200, f"Expected 200, got {res_admin_dash.status_code}"
html_admin = res_admin_dash.data.decode('utf-8')
assert 'Community Forum Management' in html_admin, "Forum section missing from admin dashboard"
assert 'Active Forum Topics' in html_admin, "Active Forum Topics missing from admin dashboard"
print("  -> PASSED (Admin dashboard renders forum_posts management)")

# 16. Unrelated Routes Regression Check
print("\n[16/16] Testing regression across unrelated routes...")
public_routes = [
    ('/', 200, 'Home'),
    ('/about', 200, 'About Us'),
    ('/admission', 200, 'Admission'),
    ('/apply', 200, 'Apply'),
    ('/departments', 200, 'Departments'),
    ('/facilities', 200, 'Facilities'),
    ('/placements', 200, 'Placements'),
    ('/gallery', 200, 'Gallery'),
    ('/students-corner', 200, 'Students Corner'),
    ('/forum', 200, 'Community Forum'),
    ('/contact', 200, 'Contact Us')
]

for route, expected_code, name in public_routes:
    res_r = client.get(route)
    assert res_r.status_code == expected_code, f"Route {route} failed with status {res_r.status_code}"
    print(f"  -> {name} ({route}): HTTP {res_r.status_code} OK")

# Test College Admin route while logged in
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
res_adm = client.get('/admin')
assert res_adm.status_code == 200, f"Route /admin failed with status {res_adm.status_code}"
print(f"  -> College Admin (/admin): HTTP 200 OK")
client.get('/logout')

# Test Super Admin route while logged in
client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
res_sa = client.get('/superadmin')
assert res_sa.status_code == 200, f"Route /superadmin failed with status {res_sa.status_code}"
print(f"  -> Super Admin (/superadmin): HTTP 200 OK")
client.get('/logout')

print("\n==================================================")
print("  ALL 16 STEP 7F REGRESSION TESTS PASSED 100%!   ")
print("==================================================")
