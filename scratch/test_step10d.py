import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 10D: DATABASE EVENTS & CALENDAR TEST SUITE ")
print("==================================================")

college = seed_default_college()

# 1 & 2. Homepage Loads Events and Calendar from Database
print("\n[1/13 & 2/13] Testing GET / homepage database events & calendar rendering...")
res_home = client.get('/')
assert res_home.status_code == 200, f"Expected 200, got {res_home.status_code}"
html_home = res_home.data.decode('utf-8')

assert "TechVanguard Hackathon 2026" in html_home, "Hackathon title missing from rendered homepage"
assert "Odd Semester Classes Begin" in html_home, "Classes begin calendar item missing from homepage"
print("  -> PASSED (Homepage successfully rendered database events & calendar items)")

# 3 & 4. Display Order Preservation
print("\n[3/13 & 4/13] Verifying display_order preservation...")
events_db = models.CampusEvent.query.filter_by(college_id=college.id).order_by(models.CampusEvent.display_order).all()
cal_db = models.AcademicCalendarItem.query.filter_by(college_id=college.id).order_by(models.AcademicCalendarItem.display_order).all()

assert events_db[0].title == 'TechVanguard Hackathon 2026'
assert events_db[3].title == 'Campus Placement Drive'
assert cal_db[0].event_name == 'Odd Semester Classes Begin'
assert cal_db[11].event_name == 'Annual Convocation Ceremony'
print("  -> PASSED (display_order sorting preserved)")

# 5 & 6. Template Compatibility Properties
print("\n[5/13 & 6/13] Verifying template compatibility properties...")
ev = events_db[0]
cal = cal_db[0]

assert ev.date == 'Sept 15, 2026'
assert cal.event == 'Odd Semester Classes Begin'
assert cal.date == 'Aug 1, 2026'
assert cal.type == 'academic'
print("  -> PASSED (Compatibility properties event.date, item.event, item.date, item.type verified)")

# 7 & 8. Cross-Tenant Data Isolation
print("\n[7/13 & 8/13] Testing cross-tenant isolation...")
other_college = models.College.query.filter_by(slug='step10d-other-tenant').first()
if not other_college:
    other_college = models.College(name='Step 10D Other Tenant', slug='step10d-other-tenant')
    db.session.add(other_college)
    db.session.commit()

other_ev = models.CampusEvent(
    college_id=other_college.id,
    title='SECRET OTHER EVENT',
    date_display='Dec 31, 2026',
    day='31',
    month='DEC',
    category='Secret',
    description='Secret event description',
    display_order=1
)
other_cal = models.AcademicCalendarItem(
    college_id=other_college.id,
    date_display='Dec 31, 2026',
    event_name='SECRET OTHER CALENDAR EVENT',
    event_type='secret',
    display_order=1
)
db.session.add_all([other_ev, other_cal])
db.session.commit()

res_home_iso = client.get('/')
html_iso = res_home_iso.data.decode('utf-8')
assert "SECRET OTHER EVENT" not in html_iso, "Cross tenant event leaked onto homepage"
assert "SECRET OTHER CALENDAR EVENT" not in html_iso, "Cross tenant calendar item leaked onto homepage"

# Cleanup
db.session.delete(other_ev)
db.session.delete(other_cal)
db.session.delete(other_college)
db.session.commit()
print("  -> PASSED (Cross-tenant events & calendar items completely isolated)")

# 9 & 10. Audit in app.py for UPCOMING_EVENTS and ACADEMIC_CALENDAR
print("\n[9/13 & 10/13] Auditing in-memory list definitions in app.py...")
with open(os.path.join(os.path.dirname(__file__), '..', 'app.py'), 'r', encoding='utf-8') as f:
    app_code = f.read()

assert 'UPCOMING_EVENTS =' not in app_code, "UPCOMING_EVENTS still defined in app.py"
assert 'ACADEMIC_CALENDAR =' not in app_code, "ACADEMIC_CALENDAR still defined in app.py"
print("  -> PASSED (Zero UPCOMING_EVENTS and ACADEMIC_CALENDAR list references in app.py)")

# 11 & 12. Dependent Routes Health Check
print("\n[11/13 & 12/13] Testing public routes health...")
assert client.get('/').status_code == 200
assert client.get('/students-corner').status_code == 200
assert client.get('/about').status_code == 200
assert client.get('/academics').status_code == 200
assert client.get('/departments').status_code == 200
assert client.get('/course/bca').status_code == 200
print("  -> PASSED (Public routes return HTTP 200 OK)")

# 13. System-Wide Module Regression Health Check
print("\n[13/13] Verifying Courses, Admissions, Gallery, and Forum health...")
assert models.Course.query.count() >= 9
assert models.GalleryItem.query.count() >= 6
assert models.ForumPost.query.count() >= 5
assert models.AdmissionApplication.query.count() >= 1
assert client.get('/gallery').status_code == 200
assert client.get('/forum').status_code == 200
assert client.get('/admission').status_code == 200
assert client.get('/apply').status_code == 200
print("  -> PASSED (All migrated database modules operational with 0 regressions)")

print("\n==================================================")
print(" ALL 13 STEP 10D DATABASE ROUTE TESTS PASSED 100%!")
print("==================================================")
