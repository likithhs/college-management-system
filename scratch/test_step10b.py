import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()

print("==================================================")
print("  STEP 10B: EVENTS & CALENDAR SCHEMA TEST SUITE   ")
print("==================================================")

college = seed_default_college()

# 1. CampusEvent Model Creation & Compatibility Property
print("\n[1/7] Testing CampusEvent model creation & date compatibility property...")
event1 = models.CampusEvent(
    college_id=college.id,
    title='Test Hackathon 2026',
    date_display='Sept 15, 2026',
    day='15',
    month='SEP',
    category='Technology',
    description='Test hackathon description',
    icon='fa-solid fa-code',
    display_order=1
)
db.session.add(event1)
db.session.commit()

assert event1.id is not None, "CampusEvent ID is None"
assert event1.date == 'Sept 15, 2026', f"Expected 'Sept 15, 2026', got '{event1.date}'"
print(f"  -> Created CampusEvent ID: {event1.id}")
print(f"  -> Compatibility property event.date: {event1.date}")
print("  -> PASSED (CampusEvent created with working date alias)")

# 2. AcademicCalendarItem Model Creation & Compatibility Properties
print("\n[2/7] Testing AcademicCalendarItem model creation & compatibility properties...")
cal_item1 = models.AcademicCalendarItem(
    college_id=college.id,
    date_display='Aug 1, 2026',
    event_name='Odd Semester Classes Begin',
    event_type='academic',
    display_order=1
)
db.session.add(cal_item1)
db.session.commit()

assert cal_item1.id is not None, "AcademicCalendarItem ID is None"
assert cal_item1.event == 'Odd Semester Classes Begin', "event alias failed"
assert cal_item1.date == 'Aug 1, 2026', "date alias failed"
assert cal_item1.type == 'academic', "type alias failed"
print(f"  -> Created AcademicCalendarItem ID: {cal_item1.id}")
print(f"  -> item.event alias: {cal_item1.event}")
print(f"  -> item.date alias: {cal_item1.date}")
print(f"  -> item.type alias: {cal_item1.type}")
print("  -> PASSED (AcademicCalendarItem created with working aliases)")

# 3. Multi-Tenant Isolation
print("\n[3/7] Testing multi-tenant isolation...")
other_college = models.College.query.filter_by(slug='step10b-other-tenant').first()
if not other_college:
    other_college = models.College(name='Step 10B Other Tenant', slug='step10b-other-tenant')
    db.session.add(other_college)
    db.session.commit()

other_event = models.CampusEvent(
    college_id=other_college.id,
    title='Other College Event',
    date_display='Nov 1, 2026',
    day='01',
    month='NOV',
    category='General',
    description='Other college event',
    display_order=1
)
db.session.add(other_event)
db.session.commit()

default_events = models.CampusEvent.query.filter_by(college_id=college.id).all()
other_events = models.CampusEvent.query.filter_by(college_id=other_college.id).all()
assert len(other_events) == 1 and other_events[0].title == 'Other College Event'
assert other_event not in default_events
print("  -> PASSED (CampusEvents strictly isolated by college_id)")

# 4. Display Order Sorting
print("\n[4/7] Testing display_order sorting...")
event2 = models.CampusEvent(
    college_id=college.id,
    title='Test Sports Meet',
    date_display='Oct 5, 2026',
    day='05',
    month='OCT',
    category='Sports',
    description='Sports meet',
    display_order=2
)
db.session.add(event2)
db.session.commit()

sorted_events = models.CampusEvent.query.filter_by(college_id=college.id).order_by(models.CampusEvent.display_order).all()
assert sorted_events[0].display_order <= sorted_events[1].display_order
print("  -> PASSED (Display order sorting verified)")

# 5. College Model Relationships
print("\n[5/7] Testing College relationships (college.campus_events, college.academic_calendar_items)...")
fetched_college = db.session.get(models.College, college.id)
assert len(fetched_college.campus_events) >= 2
assert len(fetched_college.academic_calendar_items) >= 1
print("  -> PASSED (College ORM relationships functional)")

# 6. Cascade Deletion
print("\n[6/7] Testing cascade deletion...")
other_col_id = other_college.id
other_ev_id = other_event.id
db.session.delete(other_college)
db.session.commit()

assert db.session.get(models.College, other_col_id) is None
assert db.session.get(models.CampusEvent, other_ev_id) is None
print("  -> PASSED (Deleting College cascades and deletes child events)")

# Cleanup test records
db.session.delete(event1)
db.session.delete(event2)
db.session.delete(cal_item1)
db.session.commit()

# 7. Existing Models Health Check
print("\n[7/7] Verifying health of existing models...")
assert models.Course.query.count() >= 9
assert models.GalleryItem.query.count() >= 6
assert models.ForumPost.query.count() >= 5
assert models.AdmissionApplication.query.count() >= 1
print("  -> PASSED (Courses, Gallery, Forum, Admissions operate cleanly)")

print("\n==================================================")
print(" ALL 7 STEP 10B SCHEMA TESTS PASSED 100%!        ")
print("==================================================")
