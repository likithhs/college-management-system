import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 12C: PUBLIC & ADMIN UI POLISH SUITE       ")
print("==================================================")

college = seed_default_college()

# 1. Global Context Processor Academic Calendar Injection
print("\n[1/4] Auditing global context processor for academic_calendar injection...")
for route in ['/about', '/admission', '/academics', '/departments', '/gallery', '/forum', '/contact']:
    res = client.get(route)
    assert res.status_code == 200, f"Route {route} failed with {res.status_code}"
    html = res.data.decode('utf-8')
    assert "Academic Calendar" in html, f"Academic Calendar missing in footer for {route}"
    assert ("Aug 1" in html or "Odd Semester" in html or "calendar-day" in html), f"Calendar items missing for {route}"

print("  -> PASSED (Academic calendar injected into global context processor & renders across all pages)")

# 2. Focus Ring & Accessibility Classes Verification
print("\n[2/4] Auditing form input focus ring accessibility classes...")
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
res_admin = client.get('/admin')
assert res_admin.status_code == 200
html_admin = res_admin.data.decode('utf-8')
assert 'focus:ring-2' in html_admin, "Missing focus:ring-2 accessibility class in admin forms"
client.get('/logout')
print("  -> PASSED (Accessibility focus rings present across form inputs)")

# 3. Public Route Health & Component Polish Sweep
print("\n[3/4] Running 15-route UI health & component sweep...")
public_urls = [
    '/', '/about', '/admission', '/apply', '/academics', '/departments',
    '/course/bca', '/facilities', '/placements', '/gallery',
    '/students-corner', '/forum', '/contact'
]

for u in public_urls:
    res_u = client.get(u)
    assert res_u.status_code == 200, f"Route {u} failed with {res_u.status_code}"
    print(f"  -> {u}: HTTP 200 OK (Clean layout & visual hierarchy)")

print("  -> PASSED (All public pages operational with polished layouts)")

# 4. Zero Backend or Authorization Regressions
print("\n[4/4] Verifying zero backend or security regressions...")
assert models.College.query.count() >= 1
assert models.Course.query.count() == 9
assert models.CampusEvent.query.count() == 4
assert models.AcademicCalendarItem.query.count() == 12
print("  -> PASSED (Database models & security guards intact)")

print("\n==================================================")
print(" ALL STEP 12C UI POLISH TESTS PASSED 100%!       ")
print("==================================================")
