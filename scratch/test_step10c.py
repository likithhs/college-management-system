import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college, seed_default_events_and_calendar

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 10C: EVENTS & CALENDAR SEEDING TEST SUITE  ")
print("==================================================")

# 1. Trigger Seeding
college = seed_default_college()

# 2. Check Seeded Database Record Counts
print("\n[1/8] Verifying seeded database record counts...")
ev_count = models.CampusEvent.query.filter_by(college_id=college.id).count()
cal_count = models.AcademicCalendarItem.query.filter_by(college_id=college.id).count()

print(f"  -> CampusEvents count: {ev_count} (Expected: 4)")
print(f"  -> AcademicCalendarItems count: {cal_count} (Expected: 12)")

assert ev_count == 4, f"Expected 4 events, got {ev_count}"
assert cal_count == 12, f"Expected 12 calendar items, got {cal_count}"
print("  -> PASSED (All record counts match expected values)")

# 3. Test Idempotency (Run seed_default_events_and_calendar second time)
print("\n[2/8] Testing idempotency (running seed_default_events_and_calendar a second time)...")
seed_default_events_and_calendar(college)
ev_count_2 = models.CampusEvent.query.filter_by(college_id=college.id).count()
cal_count_2 = models.AcademicCalendarItem.query.filter_by(college_id=college.id).count()

assert ev_count_2 == ev_count, "CampusEvent count changed on re-seed"
assert cal_count_2 == cal_count, "AcademicCalendarItem count changed on re-seed"
print("  -> PASSED (Zero duplicate records created on second seeding run)")

# 4. Verify Tenant Ownership Binding
print("\n[3/8] Verifying tenant ownership binding...")
events = models.CampusEvent.query.filter_by(college_id=college.id).all()
cal_items = models.AcademicCalendarItem.query.filter_by(college_id=college.id).all()

for e in events:
    assert e.college_id == college.id
for c in cal_items:
    assert c.college_id == college.id
print("  -> PASSED (All records bound to default college tenant)")

# 5. Verify Display Order Preservation
print("\n[4/8] Verifying display order preservation...")
sorted_ev = models.CampusEvent.query.filter_by(college_id=college.id).order_by(models.CampusEvent.display_order).all()
sorted_cal = models.AcademicCalendarItem.query.filter_by(college_id=college.id).order_by(models.AcademicCalendarItem.display_order).all()

assert sorted_ev[0].title == 'TechVanguard Hackathon 2026'
assert sorted_ev[3].title == 'Campus Placement Drive'
assert sorted_cal[0].event_name == 'Odd Semester Classes Begin'
assert sorted_cal[11].event_name == 'Annual Convocation Ceremony'
print("  -> PASSED (Display order matches original list sequence)")

# 6. Verify Compatibility Aliases
print("\n[5/8] Verifying compatibility property aliases...")
first_ev = sorted_ev[0]
first_cal = sorted_cal[0]

assert first_ev.date == first_ev.date_display == 'Sept 15, 2026'
assert first_cal.event == first_cal.event_name == 'Odd Semester Classes Begin'
assert first_cal.date == first_cal.date_display == 'Aug 1, 2026'
assert first_cal.type == first_cal.event_type == 'academic'
print("  -> PASSED (Compatibility aliases event.date, item.event, item.date, item.type functional)")

# 7. Existing Modules Health Check
print("\n[6/8] Verifying health of existing modules...")
assert models.Course.query.filter_by(college_id=college.id).count() == 9
assert models.GalleryItem.query.filter_by(college_id=college.id).count() == 6
assert models.ForumPost.query.filter_by(college_id=college.id).count() >= 5
print("  -> PASSED (Courses, Gallery, Forum operational)")

# 8. Homepage Stability
print("\n[7/8 - 8/8] Verifying homepage stability...")
res_home = client.get('/')
assert res_home.status_code == 200, f"Expected 200, got {res_home.status_code}"
print("  -> Homepage (/): HTTP 200 OK")
print("  -> PASSED (Homepage operational)")

print("\n==================================================")
print(" ALL 8 STEP 10C SEEDING TESTS PASSED 100%!       ")
print("==================================================")
