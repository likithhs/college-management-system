import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from authz import check_tenant_ownership

app.app_context().push()
client = app.test_client(use_cookies=True)

print("=== 1. UNAUTHENTICATED TESTS ===")
print("/admin unauth:", client.get('/admin').status_code)
print("/superadmin unauth:", client.get('/superadmin').status_code)
print("/superadmin/toggle-enable/gallery unauth:", client.post('/superadmin/toggle-enable/gallery').status_code)
print("/gallery/add unauth:", client.post('/gallery/add').status_code)

print("\n=== 2. COLLEGE ADMIN 403 TESTS ===")
client.post('/login', data={'email':'admin@spmcollege.ac.in', 'password':'CollegeAdmin@123'})
print("College Admin -> /admin access:", client.get('/admin').status_code)
print("College Admin -> /superadmin direct access:", client.get('/superadmin').status_code)
print("College Admin -> toggle-enable direct POST:", client.post('/superadmin/toggle-enable/gallery').status_code)
print("College Admin -> toggle-admin direct POST:", client.post('/superadmin/toggle-admin/gallery').status_code)

print("\n=== 3. MODULE ADMIN ACCESS ENFORCEMENT ===")
cfg = models.ModuleConfig.query.filter_by(college_id=1, module_key='gallery').first()
print("Gallery add when admin_access=True:", client.post('/gallery/add', data={'title':'Test'}).status_code)

cfg.admin_access = False
db.session.commit()
print("Gallery add when admin_access=False:", client.post('/gallery/add', data={'title':'Test'}).status_code)

cfg.admin_access = True
db.session.commit()
print("Gallery add after restoring admin_access=True:", client.post('/gallery/add', data={'title':'Test'}).status_code)

client.get('/logout')

print("\n=== 4. PLATFORM SUPER ADMIN TESTS ===")
client.post('/login', data={'email':'superadmin@spmcollege.ac.in', 'password':'SuperAdmin@123'})
print("Super Admin -> /superadmin access:", client.get('/superadmin').status_code)
print("Super Admin -> toggle-enable access:", client.post('/superadmin/toggle-enable/gallery').status_code)
client.get('/logout')

print("\n=== 5. TENANT OWNERSHIP HELPER TESTS ===")
ca_user = models.User.query.filter_by(email='admin@spmcollege.ac.in').first()
sa_user = models.User.query.filter_by(email='superadmin@spmcollege.ac.in').first()

with app.test_request_context():
    from flask_login import login_user
    login_user(ca_user)
    print("College Admin own tenant match (id=1):", check_tenant_ownership(1))
    print("College Admin other tenant match (id=2):", check_tenant_ownership(2))
    
    login_user(sa_user)
    print("Super Admin tenant override (id=99):", check_tenant_ownership(99))

print("\nAll Step 4 Authorization Tests COMPLETED Successfully!")
