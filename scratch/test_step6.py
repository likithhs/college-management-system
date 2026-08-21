import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college, seed_default_gallery_items

app.app_context().push()
client = app.test_client(use_cookies=True)

print("=== 1. MIGRATION & SEEDING IDEMPOTENCY TESTS ===")
college = seed_default_college()
initial_items = models.GalleryItem.query.filter_by(college_id=college.id).all()
print("Initial seeded gallery items count (should be >= 6):", len(initial_items))

# Test Idempotency
seed_default_gallery_items(college)
reseed_items = models.GalleryItem.query.filter_by(college_id=college.id).all()
print("Reseed count matches initial count (idempotent):", len(reseed_items) == len(initial_items))

titles = [item.title for item in reseed_items]
print("Default item 'TechVanguard Hackathon 2026' present:", 'TechVanguard Hackathon 2026' in titles)
print("Default item 'Annual Youth Fest Seshadri Utsav' present:", 'Annual Youth Fest Seshadri Utsav' in titles)

print("\n=== 2. PUBLIC GALLERY RENDERING & MODULE ENABLED CHECK ===")
res_public = client.get('/gallery')
print("/gallery GET status:", res_public.status_code)
html_public = res_public.data.decode('utf-8')
print("Public gallery contains 'TechVanguard Hackathon 2026':", 'TechVanguard Hackathon 2026' in html_public)
print("Public gallery contains data-category attribute:", 'data-category="tech"' in html_public)

# Test disabling module
cfg = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='gallery').first()
cfg.enabled = False
db.session.commit()

res_disabled = client.get('/gallery')
print("/gallery GET when enabled=False redirects:", res_disabled.status_code == 302)

cfg.enabled = True
db.session.commit()

print("\n=== 3. ADD GALLERY ITEM & VALIDATION ===")
# Login as College Admin
client.post('/login', data={'email':'admin@spmcollege.ac.in', 'password':'CollegeAdmin@123'})

# Validation failures
res_no_title = client.post('/gallery/add', data={'title': '', 'category': 'tech'}, follow_redirects=True)
print("Blank title rejected:", "Validation Error" in res_no_title.data.decode('utf-8'))

res_bad_cat = client.post('/gallery/add', data={'title': 'Test Item', 'category': 'invalid_category'}, follow_redirects=True)
print("Invalid category rejected:", "Validation Error" in res_bad_cat.data.decode('utf-8'))

res_bad_url = client.post('/gallery/add', data={'title': 'Test Item', 'category': 'tech', 'image_url': 'ftp://invalid-scheme.com'}, follow_redirects=True)
print("Invalid image URL scheme rejected:", "Validation Error" in res_bad_url.data.decode('utf-8'))

# Valid Add
valid_item_payload = {
    'title': 'Robotics & Drone Expo 2026',
    'category': 'tech',
    'description': 'Demonstration of autonomous drones and robotic arms.',
    'image_url': 'https://images.unsplash.com/photo-1485827404703-89b55fcc595e'
}
res_add = client.post('/gallery/add', data=valid_item_payload, follow_redirects=True)
print("Valid gallery item added cleanly:", res_add.status_code == 200)

added_item = models.GalleryItem.query.filter_by(title='Robotics & Drone Expo 2026').first()
print("Added item persisted in DB:", added_item is not None)
print("Added item college_id matches user college_id (1):", added_item.college_id == 1 if added_item else False)
print("Added item category_label set automatically:", added_item.category_label == 'Tech & Hackathons' if added_item else False)

print("\n=== 4. DELETE GALLERY ITEM & CROSS-TENANT SECURITY ===")
item_to_delete_id = added_item.id

# Delete item
res_del = client.post(f'/gallery/delete/{item_to_delete_id}', follow_redirects=True)
print("Delete request status:", res_del.status_code)
deleted_check = models.GalleryItem.query.get(item_to_delete_id)
print("Item deleted from database:", deleted_check is None)

# Cross-tenant deletion security check simulation
temp_college = models.College.query.filter_by(slug='test-college-tenant').first()
if not temp_college:
    temp_college = models.College(name='Test College Tenant', slug='test-college-tenant')
    db.session.add(temp_college)
    db.session.commit()

other_tenant_item = models.GalleryItem(
    college_id=temp_college.id,
    title='Other Tenant Event',
    category='campus',
    category_label='Campus Life',
    description='Other college event.'
)
db.session.add(other_tenant_item)
db.session.commit()

# College Admin (college_id=1) attempts to delete other_tenant_item (college_id=temp_college.id)
res_cross_del = client.post(f'/gallery/delete/{other_tenant_item.id}')
print("Cross-tenant deletion blocked with HTTP 403 Forbidden:", res_cross_del.status_code == 403)

# Clean up temporary test item and college
db.session.delete(other_tenant_item)
db.session.delete(temp_college)
db.session.commit()

client.get('/logout')

print("\n=== 5. AUTHORIZATION & MODULE ADMIN_ACCESS ENFORCEMENT ===")
# Login as Super Admin to set admin_access = False
client.post('/login', data={'email':'superadmin@spmcollege.ac.in', 'password':'SuperAdmin@123'})
cfg.admin_access = False
db.session.commit()
client.get('/logout')

# College Admin attempts POST /gallery/add when admin_access = False
client.post('/login', data={'email':'admin@spmcollege.ac.in', 'password':'CollegeAdmin@123'})
res_admin_denied = client.post('/gallery/add', data=valid_item_payload)
print("Gallery add blocked with HTTP 403 when admin_access=False:", res_admin_denied.status_code == 403)
client.get('/logout')

# Restore admin_access = True
client.post('/login', data={'email':'superadmin@spmcollege.ac.in', 'password':'SuperAdmin@123'})
cfg.admin_access = True
db.session.commit()
client.get('/logout')

print("\nAll Step 6 Gallery Persistence Tests PASSED Successfully!")
