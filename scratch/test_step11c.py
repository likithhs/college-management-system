import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 11C: EVENTS & CALENDAR ADMIN MANAGEMENT    ")
print("==================================================")

college = seed_default_college()

# Reset news_events admin_access to True for clean test state
cfg_init = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='news_events').first()
if cfg_init:
    cfg_init.admin_access = True
    db.session.commit()

# 1. Unauthenticated Access Protection
print("\n[1/12] Testing unauthenticated admin access protection...")
res_unauth = client.post('/admin/event/add', data={'title': 'Unauth', 'date_display': 'Now', 'day': '01', 'month': 'JAN', 'category': 'Cat', 'description': 'Desc'})
assert res_unauth.status_code == 302 and 'login' in res_unauth.headers.get('Location', '')
print("  -> PASSED (Unauthenticated request redirected to /login)")

# Authenticate as College Admin
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})

# 2. Add New Campus Event
print("\n[2/12] Testing POST /admin/event/add...")
res_add_ev = client.post('/admin/event/add', data={
    'title': 'AI Symposium 2026',
    'date_display': 'Oct 28, 2026',
    'day': '28',
    'month': 'OCT',
    'category': 'Technology',
    'description': 'National symposium on generative AI and robotics.',
    'icon': 'fa-solid fa-robot'
}, follow_redirects=True)
assert res_add_ev.status_code == 200

created_ev = models.CampusEvent.query.filter_by(college_id=college.id, title='AI Symposium 2026').first()
assert created_ev is not None, "Event AI Symposium 2026 not found in database"
assert created_ev.date_display == 'Oct 28, 2026'
print("  -> PASSED (New campus event created successfully)")

# 3. Edit Campus Event
print("\n[3/12] Testing POST /admin/event/edit/<event_id>...")
res_edit_ev = client.post(f'/admin/event/edit/{created_ev.id}', data={
    'title': 'AI & Quantum Symposium 2026',
    'date_display': 'Oct 29, 2026',
    'day': '29',
    'month': 'OCT',
    'category': 'Technology',
    'description': 'Updated symposium description with Quantum Computing.',
    'icon': 'fa-solid fa-atom'
}, follow_redirects=True)
assert res_edit_ev.status_code == 200

edited_ev = db.session.get(models.CampusEvent, created_ev.id)
assert edited_ev.title == 'AI & Quantum Symposium 2026'
assert edited_ev.date_display == 'Oct 29, 2026'
print("  -> PASSED (Campus event edited successfully)")

# 4. Delete Campus Event
print("\n[4/12] Testing POST /admin/event/delete/<event_id>...")
ev_id = created_ev.id
res_del_ev = client.post(f'/admin/event/delete/{ev_id}', follow_redirects=True)
assert res_del_ev.status_code == 200
assert db.session.get(models.CampusEvent, ev_id) is None
print("  -> PASSED (Campus event deleted)")

# 5. Add Academic Calendar Item
print("\n[5/12] Testing POST /admin/calendar/add...")
res_add_cal = client.post('/admin/calendar/add', data={
    'event_name': 'Mid-Term Project Submission',
    'date_display': 'Nov 10, 2026',
    'event_type': 'academic'
}, follow_redirects=True)
assert res_add_cal.status_code == 200

created_cal = models.AcademicCalendarItem.query.filter_by(college_id=college.id, event_name='Mid-Term Project Submission').first()
assert created_cal is not None
assert created_cal.date_display == 'Nov 10, 2026'
print("  -> PASSED (Academic calendar item added successfully)")

# 6. Edit Academic Calendar Item
print("\n[6/12] Testing POST /admin/calendar/edit/<item_id>...")
res_edit_cal = client.post(f'/admin/calendar/edit/{created_cal.id}', data={
    'event_name': 'Final Project Submission Deadline',
    'date_display': 'Nov 15, 2026',
    'event_type': 'academic'
}, follow_redirects=True)
assert res_edit_cal.status_code == 200

edited_cal = db.session.get(models.AcademicCalendarItem, created_cal.id)
assert edited_cal.event_name == 'Final Project Submission Deadline'
assert edited_cal.date_display == 'Nov 15, 2026'
print("  -> PASSED (Academic calendar item edited successfully)")

# 7. Delete Academic Calendar Item
print("\n[7/12] Testing POST /admin/calendar/delete/<item_id>...")
cal_id = created_cal.id
res_del_cal = client.post(f'/admin/calendar/delete/{cal_id}', follow_redirects=True)
assert res_del_cal.status_code == 200
assert db.session.get(models.AcademicCalendarItem, cal_id) is None
print("  -> PASSED (Academic calendar item deleted)")

# 8. Cross-Tenant Attack Protection (returns HTTP 403)
print("\n[8/12] Testing cross-tenant attack protection...")
other_college = models.College.query.filter_by(slug='step11c-other-tenant').first()
if not other_college:
    other_college = models.College(name='Step 11C Other Tenant', slug='step11c-other-tenant')
    db.session.add(other_college)
    db.session.commit()

other_ev = models.CampusEvent(college_id=other_college.id, title='SECRET OTHER EV', date_display='Date', day='01', month='JAN', category='Secret', description='Secret')
other_cal = models.AcademicCalendarItem(college_id=other_college.id, date_display='Date', event_name='SECRET OTHER CAL', event_type='academic')
db.session.add_all([other_ev, other_cal])
db.session.commit()

res_cross_ev = client.post(f'/admin/event/delete/{other_ev.id}')
assert res_cross_ev.status_code == 403

res_cross_cal = client.post(f'/admin/calendar/delete/{other_cal.id}')
assert res_cross_cal.status_code == 403

db.session.delete(other_ev)
db.session.delete(other_cal)
db.session.delete(other_college)
db.session.commit()
print("  -> PASSED (Cross-tenant modification attempts blocked with HTTP 403)")

# 9. Module Admin Access Control (Revoked Access)
print("\n[9/12] Testing module admin access restriction when Super Admin revokes 'news_events'...")
client.get('/logout')

try:
    # Super Admin revokes news_events admin access
    client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
    cfg_news = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='news_events').first()
    cfg_news.admin_access = False
    db.session.commit()
    client.get('/logout')

    # College Admin attempts action
    client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})
    res_rev_ev = client.post('/admin/event/add', data={'title': 'REVOKED EV', 'date_display': 'Date', 'day': '01', 'month': 'JAN', 'category': 'Rev', 'description': 'Rev'})
    assert res_rev_ev.status_code == 403
    assert models.CampusEvent.query.filter_by(college_id=college.id, title='REVOKED EV').first() is None

    res_rev_cal = client.post('/admin/calendar/add', data={'event_name': 'REVOKED CAL', 'date_display': 'Date', 'event_type': 'academic'})
    assert res_rev_cal.status_code == 403
    assert models.AcademicCalendarItem.query.filter_by(college_id=college.id, event_name='REVOKED CAL').first() is None
    print("  -> PASSED (Module access restriction enforced with HTTP 403 when Super Admin revokes permission)")
finally:
    # Always restore news_events admin access
    client.get('/logout')
    client.post('/login', data={'email': 'superadmin@spmcollege.ac.in', 'password': 'SuperAdmin@123'})
    cfg_news = models.ModuleConfig.query.filter_by(college_id=college.id, module_key='news_events').first()
    if cfg_news:
        cfg_news.admin_access = True
        db.session.commit()
    client.get('/logout')

# 10. Dynamic Homepage Integration Verification
print("\n[10/12] Testing dynamic homepage rendering of admin-created events...")
client.post('/login', data={'email': 'admin@spmcollege.ac.in', 'password': 'CollegeAdmin@123'})

client.post('/admin/event/add', data={
    'title': 'DYNAMIC HOMEPAGE EVENT TEST',
    'date_display': 'Dec 25, 2026',
    'day': '25',
    'month': 'DEC',
    'category': 'Test',
    'description': 'Dynamic rendering test',
    'icon': 'fa-solid fa-star'
})

dyn_ev = models.CampusEvent.query.filter_by(college_id=college.id, title='DYNAMIC HOMEPAGE EVENT TEST').first()
assert dyn_ev is not None

res_home_dyn = client.get('/')
assert "DYNAMIC HOMEPAGE EVENT TEST" in res_home_dyn.data.decode('utf-8')

# Cleanup dynamic test event
client.post(f'/admin/event/delete/{dyn_ev.id}')
print("  -> PASSED (Admin-created events immediately render on public homepage)")

# 11. Admin Dashboard View
print("\n[11/12] Testing Admin Portal UI rendering...")
res_admin = client.get('/admin')
assert res_admin.status_code == 200
assert "Campus Events &amp; Academic Calendar Management" in res_admin.data.decode('utf-8') or "Campus Events & Academic Calendar Management" in res_admin.data.decode('utf-8')
client.get('/logout')
print("  -> PASSED (Campus Events & Calendar section rendered on admin dashboard)")

# 12. Public Routes Health Verification
print("\n[12/12] Verifying public academic & homepage routes health...")
assert client.get('/').status_code == 200
assert client.get('/academics').status_code == 200
assert client.get('/departments').status_code == 200
print("  -> PASSED (Public routes operational)")

print("\n==================================================")
print(" ALL 12 STEP 11C ADMIN MANAGEMENT TESTS PASSED 100%!")
print("==================================================")
