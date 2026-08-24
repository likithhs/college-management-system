import sys
import os
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college
from rate_limiter import reset_rate_limiter

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print(" STEP 26: RATE LIMITING & SECURITY DEFENSE AUDIT ")
print("==================================================")

college = seed_default_college()

def extract_csrf_token(res):
    html = res.data.decode('utf-8')
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    with client.session_transaction() as sess:
        return sess.get('csrf_token')

# Clean state before starting tests
reset_rate_limiter()

# [1/6] Login Brute-Force Protection Test (5 POSTs per minute)
print("\n[1/6] Auditing Login Brute-Force Defense (5 POSTs / minute)...")
res_login_g = client.get('/login')
tok_login = extract_csrf_token(res_login_g)

# Perform 5 failed login attempts
for i in range(1, 6):
    res_attempt = client.post('/login', data={
        'email': 'hacker@example.com',
        'password': f'wrong_pass_{i}',
        'csrf_token': tok_login
    })
    assert res_attempt.status_code != 429, f"Attempt {i} unexpectedly rate limited!"

# 6th attempt MUST return HTTP 429
res_blocked = client.post('/login', data={
    'email': 'hacker@example.com',
    'password': 'wrong_pass_6',
    'csrf_token': tok_login
})
assert res_blocked.status_code == 429, f"6th login attempt returned status {res_blocked.status_code} instead of 429!"
assert 'Retry-After' in res_blocked.headers
print("  -> PASSED (6th rapid failed login attempt strictly returned HTTP 429 with Retry-After header)")

reset_rate_limiter('login')

# [2/6] Application Submission Rate Limiting Test (5 POSTs per hour)
print("\n[2/6] Auditing Application Submission Rate Limiting (5 POSTs / hour)...")
tok_apply = extract_csrf_token(client.get('/apply'))

for i in range(1, 6):
    res_app_attempt = client.post('/apply', data={
        'full_name': f'Test Student {i}',
        'guardian_name': 'Guardian Test',
        'email': f'student{i}@example.com',
        'phone': '9876543210',
        'course': 'BCA',
        'percentage': '85.0',
        'csrf_token': tok_apply
    })
    assert res_app_attempt.status_code in [200, 302]

res_app_blocked = client.post('/apply', data={
    'full_name': 'OverLimit Student',
    'guardian_name': 'Guardian Test',
    'email': 'overlimit@example.com',
    'phone': '9876543210',
    'course': 'BCA',
    'percentage': '85.0',
    'csrf_token': tok_apply
})
assert res_app_blocked.status_code == 429
print("  -> PASSED (6th rapid application submission strictly returned HTTP 429)")

reset_rate_limiter('apply')

# [3/6] Forum Upvote & Reply Rate Limiting Test (10 POSTs per minute)
print("\n[3/6] Auditing Forum Interaction Throttling (10 POSTs / minute)...")
post1 = models.ForumPost.query.filter_by(college_id=college.id).first()
if not post1:
    post1 = models.ForumPost(
        college_id=college.id,
        title='Rate Limit Test Topic',
        author='Test Runner',
        category='General',
        content='Topic content'
    )
    db.session.add(post1)
    db.session.commit()

tok_forum = extract_csrf_token(client.get('/forum'))

for i in range(1, 11):
    res_like = client.post(f'/forum/like/{post1.id}', data={'csrf_token': tok_forum}, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert res_like.status_code != 429

res_like_blocked = client.post(f'/forum/like/{post1.id}', data={'csrf_token': tok_forum}, headers={'X-Requested-With': 'XMLHttpRequest'})
assert res_like_blocked.status_code == 429
print("  -> PASSED (11th rapid forum interaction strictly returned HTTP 429)")

reset_rate_limiter('forum_like')

# [4/6] PDF Download Endpoint Throttling Test (20 GETs per 5 minutes)
print("\n[4/6] Auditing PDF Download Throttling (20 GETs / 5 minutes)...")
app_verif = models.AdmissionApplication.query.filter_by(college_id=college.id, status='VERIFIED').first()
if not app_verif:
    app_verif = models.AdmissionApplication(
        college_id=college.id,
        application_number='SC2026-RLTEST',
        full_name='RateLimit Verified Student',
        guardian_name='Guardian RL',
        email='rlstudent@example.com',
        phone='9900112233',
        course='BCA',
        percentage=90.0,
        status='VERIFIED'
    )
    db.session.add(app_verif)
    db.session.commit()

# Establish applicant session
client.post('/students-corner', data={
    'tracking_id': app_verif.application_number,
    'email': 'rlstudent@example.com',
    'csrf_token': extract_csrf_token(client.get('/students-corner'))
})

for i in range(1, 21):
    res_pdf = client.get(f'/admission/provisional-letter/{app_verif.application_number}')
    assert res_pdf.status_code == 200

res_pdf_blocked = client.get(f'/admission/provisional-letter/{app_verif.application_number}')
assert res_pdf_blocked.status_code == 429
print("  -> PASSED (21st rapid PDF download strictly returned HTTP 429)")

reset_rate_limiter('pdf_download')

# [5/6] HTTP 429 Response Format Verification (JSON vs HTML)
print("\n[5/6] Auditing HTTP 429 Response Formats (JSON vs HTML)...")
# Trigger rate limit on login
for i in range(6):
    client.post('/login', data={'email': 'test@example.com', 'password': 'pass', 'csrf_token': tok_login})

# AJAX JSON request
res_json_429 = client.post('/login', data={'email': 'test@example.com', 'password': 'pass', 'csrf_token': tok_login}, headers={'Accept': 'application/json'})
assert res_json_429.status_code == 429
json_data = res_json_429.get_json()
assert json_data is not None
assert json_data['error'] == 'Too Many Requests'
assert 'retry_after' in json_data
print("  -> PASSED (AJAX/JSON rate limit breach returned valid JSON payload)")

# HTML Browser request
res_html_429 = client.post('/login', data={'email': 'test@example.com', 'password': 'pass', 'csrf_token': tok_login})
assert res_html_429.status_code == 429
assert 'text/html' in res_html_429.mimetype
assert 'Rate Limit Exceeded' in res_html_429.data.decode('utf-8') or 'Too Many Requests' in res_html_429.data.decode('utf-8')
print("  -> PASSED (Browser rate limit breach returned valid HTML error page)")

# [6/6] Cleanup & Limiter State Reset
print("\n[6/6] Cleaning Up Rate Limiter State...")
reset_rate_limiter()
print("  -> PASSED (Rate limiter state reset cleanly)")

print("\n==================================================")
print(" ALL 6 STEP 26 RATE LIMITING TESTS PASSED!       ")
print("==================================================")
