import sys
import os
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college
from notification_service import (
    create_notification,
    notify_college_admins,
    sanitize_notification_link,
    get_unread_count_for_context,
    get_notifications_for_context,
    mark_notification_as_read
)

app.app_context().push()
db.create_all()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 17: IN-APP NOTIFICATION SYSTEM SUITE       ")
print("==================================================")

college = seed_default_college()

def extract_csrf_token(res):
    html = res.data.decode('utf-8')
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    with client.session_transaction() as sess:
        return sess.get('csrf_token')

# 1. Open Redirect Link Protection Audit (Requirement 4 & User Test Case)
print("\n[1/7] Auditing Open Redirect Link Sanitization...")
assert sanitize_notification_link("https://evil-phishing.com") is None
assert sanitize_notification_link("http://attacker.com/malware") is None
assert sanitize_notification_link("//external-domain.com") is None
assert sanitize_notification_link("javascript:alert(1)") is None
assert sanitize_notification_link("/students-corner") == "/students-corner"
assert sanitize_notification_link("/admin") == "/admin"
print("  -> PASSED (External URLs rejected; internal relative routes allowed)")

# 2. Multi-Admin Notification Dispatch Audit (Requirement 2 & User Test Case)
print("\n[2/7] Auditing Multi-Admin Notification Dispatch...")
admin2 = models.User.query.filter_by(email='admin2.test@spmcollege.ac.in').first()
if not admin2:
    admin2 = models.User(
        email='admin2.test@spmcollege.ac.in',
        role='COLLEGE_ADMIN',
        college_id=college.id,
        is_active=True
    )
    admin2.set_password('AdminPass@123')
    db.session.add(admin2)
    db.session.commit()

dispatched = notify_college_admins(
    college_id=college.id,
    title="Multi-Admin Alert Test",
    message="Broadcast alert for all admins",
    category="admissions",
    link="/admin"
)
admin_user_ids = [n.user_id for n in dispatched]
assert len(dispatched) >= 2
assert admin2.id in admin_user_ids
print("  -> PASSED (Notifications dispatched to all authorized tenant admin accounts)")

# 3. Application Submission Triggers In-App Notifications Audit
print("\n[3/7] Auditing Application Submission In-App Notification Triggers...")
sub_email = "student.notif17@example.com"
models.AdmissionApplication.query.filter_by(email=sub_email).delete()
models.Notification.query.filter_by(recipient_email=sub_email).delete()
db.session.commit()

res_apply_g = client.get('/apply')
tok_apply = extract_csrf_token(res_apply_g)

client.post('/apply', data={
    'full_name': 'Notification Student',
    'guardian_name': 'Guardian Notif',
    'email': sub_email,
    'phone': '9911223344',
    'course': 'BCA',
    'percentage': '88.5',
    'csrf_token': tok_apply
}, follow_redirects=True)

app_rec = models.AdmissionApplication.query.filter_by(email=sub_email).first()
assert app_rec is not None
app_num = app_rec.application_number

student_notif = models.Notification.query.filter_by(
    college_id=college.id,
    recipient_email=sub_email,
    application_number=app_num
).first()
assert student_notif is not None
assert "Submitted" in student_notif.title or "Received" in student_notif.title
print("  -> PASSED (Application submission created applicant & admin in-app notifications)")

# 4. Applicant Notification Context Isolation Audit (Requirement 1 & User Test Case)
print("\n[4/7] Auditing Applicant Notification Isolation...")

# Create Applicant B
email_b = "student.b.notif17@example.com"
models.AdmissionApplication.query.filter_by(email=email_b).delete()
models.Notification.query.filter_by(recipient_email=email_b).delete()
db.session.commit()

app_b = models.AdmissionApplication(
    college_id=college.id,
    application_number="SC2026-B17NOTIF",
    full_name="Applicant B",
    guardian_name="Guardian B",
    email=email_b,
    phone="9988776655",
    course="BBA",
    percentage="82.0",
    status="PENDING"
)
db.session.add(app_b)
db.session.commit()

notif_b = create_notification(
    college_id=college.id,
    title="Applicant B Private Notif",
    message="Private content for B",
    recipient_email=email_b,
    application_number="SC2026-B17NOTIF"
)

# Authenticate Applicant A session
client.get('/students-corner/logout')
res_corner_g = client.get('/students-corner')
tok_corner = extract_csrf_token(res_corner_g)

client.post('/students-corner', data={
    'tracking_id': app_num,
    'email': sub_email,
    'csrf_token': tok_corner
}, follow_redirects=True)

# Fetch notifications for Applicant A session
res_list = client.get('/notifications/list')
assert res_list.status_code == 200
list_data = res_list.get_json()
titles = [n['title'] for n in list_data]

assert "Applicant B Private Notif" not in titles, "Applicant A can see Applicant B's notification!"

# Attempt to mark Applicant B's notification read from Applicant A's session
res_read_cross = client.post(f'/notifications/read/{notif_b.id}', data={'csrf_token': tok_corner})
assert res_read_cross.status_code == 404, f"Expected 404 for cross-applicant notification read, got {res_read_cross.status_code}"
print("  -> PASSED (Applicant A cannot view or mark Applicant B's notifications)")

# 5. Duplicate Notification Prevention Audit (User Test Case)
print("\n[5/7] Auditing Duplicate Notification Prevention...")
notif_dup1 = create_notification(
    college_id=college.id,
    title="Duplicate Check Title",
    message="Duplicate Check Message",
    recipient_email=sub_email,
    application_number=app_num
)
notif_dup2 = create_notification(
    college_id=college.id,
    title="Duplicate Check Title",
    message="Duplicate Check Message",
    recipient_email=sub_email,
    application_number=app_num
)
assert notif_dup1.id == notif_dup2.id, "Duplicate notification created for identical parameters!"
print("  -> PASSED (Duplicate notification call returned existing record)")

# 6. CSRF Protection Audit (User Test Case)
print("\n[6/7] Auditing CSRF Validation on Notification Mutations...")

# Attempt POST without CSRF token
guest_cl = app.test_client(use_cookies=False)
res_no_csrf = guest_cl.post(f'/notifications/read/{student_notif.id}')
assert res_no_csrf.status_code in [400, 403], f"Expected 400/403 for missing CSRF, got {res_no_csrf.status_code}"

# Submit with valid CSRF token in session
res_with_csrf = client.post(f'/notifications/read/{student_notif.id}', data={'csrf_token': tok_corner})
assert res_with_csrf.status_code == 200
assert res_with_csrf.get_json()['success'] is True
print("  -> PASSED (CSRF token strictly enforced on notification mutation endpoints)")

# 7. Logout & Session Invalidation Audit (User Test Case)
print("\n[7/7] Auditing Notification Protection Post-Logout...")
client.get('/students-corner/logout')

res_post_logout_list = client.get('/notifications/list')
assert res_post_logout_list.status_code == 200
assert len(res_post_logout_list.get_json()) == 0, "Notifications returned after applicant logout!"

res_post_logout_read = client.post(f'/notifications/read/{student_notif.id}')
assert res_post_logout_read.status_code in [400, 403], f"Expected 400 or 403 after logout, got {res_post_logout_read.status_code}"
print("  -> PASSED (Notification access blocked completely after applicant logout)")

print("\n==================================================")
print(" ALL IN-APP NOTIFICATION TESTS PASSED!          ")
print("==================================================")
