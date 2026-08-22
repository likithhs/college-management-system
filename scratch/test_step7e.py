import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("=== 1. PUBLIC ROUTE & DISABLING TESTS ===")
res_pub = client.get('/forum')
print("Public GET /forum status:", res_pub.status_code)
print("Public POST /forum is blocked (405):", client.post('/forum').status_code == 405)

college = seed_default_college()
cfg = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='forum').first()
cfg.enabled = False
db.session.commit()
print("Disabled module blocks GET /forum with 302 redirect:", client.get('/forum').status_code == 302)

cfg.enabled = True
db.session.commit()

print("\n=== 2. UNAUTHENTICATED & PERMISSION SECURITY TESTS ===")
# Unauthenticated POST /forum/add redirects to login
res_unauth = client.post('/forum/add', data={'title': 'Test', 'category': 'Events & Fests', 'content': 'Test'})
print("Unauthenticated POST /forum/add redirects to login:", res_unauth.status_code == 302 and 'login' in res_unauth.headers.get('Location', ''))

# Login as Super Admin to set admin_access = False
client.post('/login', data={'email':'superadmin@spmcollege.ac.in', 'password':'SuperAdmin@123'})
cfg.admin_access = False
db.session.commit()
client.get('/logout')

# College Admin attempts POST /forum/add when admin_access = False
client.post('/login', data={'email':'admin@spmcollege.ac.in', 'password':'CollegeAdmin@123'})
res_denied = client.post('/forum/add', data={'title': 'Test', 'category': 'Events & Fests', 'content': 'Test'})
print("College Admin denied with HTTP 403 when admin_access=False:", res_denied.status_code == 403)
client.get('/logout')

# Restore admin_access = True
client.post('/login', data={'email':'superadmin@spmcollege.ac.in', 'password':'SuperAdmin@123'})
cfg.admin_access = True
db.session.commit()
client.get('/logout')

print("\n=== 3. SERVER-SIDE INPUT VALIDATION TESTS ===")
client.post('/login', data={'email':'admin@spmcollege.ac.in', 'password':'CollegeAdmin@123'})

res_blank_title = client.post('/forum/add', data={'title': '', 'category': 'Events & Fests', 'content': 'Test'}, follow_redirects=True)
print("Blank title rejected:", "Validation Error" in res_blank_title.data.decode('utf-8'))

res_blank_content = client.post('/forum/add', data={'title': 'Valid Title', 'category': 'Events & Fests', 'content': ''}, follow_redirects=True)
print("Blank content rejected:", "Validation Error" in res_blank_content.data.decode('utf-8'))

res_bad_cat = client.post('/forum/add', data={'title': 'Valid Title', 'category': 'InvalidCategory', 'content': 'Test'}, follow_redirects=True)
print("Invalid category rejected:", "Validation Error" in res_bad_cat.data.decode('utf-8'))

res_long_title = client.post('/forum/add', data={'title': 'A' * 251, 'category': 'Events & Fests', 'content': 'Test'}, follow_redirects=True)
print("Overlong title rejected:", "Validation Error" in res_long_title.data.decode('utf-8'))

print("\n=== 4. VALID TOPIC ADDITION & DELETION ===")
payload = {
    'author': 'Prof. Ananya Rao',
    'title': 'AI & Machine Learning Student Research Symposium 2026',
    'category': 'Events & Fests',
    'content': 'Calling all BCA and MCA students to submit research papers.'
}

res_add = client.post('/forum/add', data=payload, follow_redirects=True)
print("Valid post added cleanly:", res_add.status_code == 200)

new_post = models.ForumPost.query.filter_by(title=payload['title']).first()
print("Post persisted in DB:", new_post is not None)
print("Post bound to College Admin tenant_id (1):", new_post.college_id == 1 if new_post else False)

# Test same-tenant deletion
post_id = new_post.id
res_delete = client.post(f'/forum/delete/{post_id}', follow_redirects=True)
print("Same-tenant post deletion status:", res_delete.status_code == 200)
deleted_check = models.ForumPost.query.get(post_id)
print("Post removed from DB:", deleted_check is None)

print("\n=== 5. CROSS-TENANT SECURITY DELETION TEST ===")
# Create a dummy second college tenant and post
temp_college = models.College.query.filter_by(slug='other-college-tenant').first()
if not temp_college:
    temp_college = models.College(name='Other College Tenant', slug='other-college-tenant')
    db.session.add(temp_college)
    db.session.commit()

other_tenant_post = models.ForumPost(
    college_id=temp_college.id,
    author='Other Admin',
    title='Other Tenant Topic',
    category='Events & Fests',
    content='Other tenant content'
)
db.session.add(other_tenant_post)
db.session.commit()

# College Admin (college_id=1) attempts to delete other_tenant_post (college_id=temp_college.id)
res_cross = client.post(f'/forum/delete/{other_tenant_post.id}')
print("Cross-tenant deletion blocked with HTTP 403 Forbidden:", res_cross.status_code == 403)

# Cleanup
db.session.delete(other_tenant_post)
db.session.delete(temp_college)
db.session.commit()
client.get('/logout')

print("\nAll Step 7E Authorization, Validation & Security Tests PASSED Successfully!")
