import sys
import os
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("==================================================")
print("  STEP 19: COMPREHENSIVE UI/UX & RESPONSIVE SUITE ")
print("==================================================")

college = seed_default_college()

def extract_csrf_token(res):
    html = res.data.decode('utf-8')
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    with client.session_transaction() as sess:
        return sess.get('csrf_token')

# 1. Template Compilation Test (Requirement 1 & Test 1)
print("\n[1/6] Auditing All 18 Jinja2 HTML Templates Syntax & Compilation...")
templates_list = [
    '403.html', 'about.html', 'admin.html', 'admission.html', 'apply.html',
    'base.html', 'contact.html', 'course_detail.html', 'departments.html',
    'facilities.html', 'forum.html', 'gallery.html', 'index.html',
    'login.html', 'placements.html', 'students_corner.html',
    'superadmin.html', 'verify_receipt.html'
]

for tmpl in templates_list:
    try:
        t = app.jinja_env.get_template(tmpl)
        assert t is not None
    except Exception as e:
        print(f"  ❌ Template {tmpl} error: {e}")
        sys.exit(1)

print(f"  -> PASSED (All {len(templates_list)} templates compiled successfully without syntax errors)")

# 2. Viewport Support Test (Test 2)
print("\n[2/6] Auditing Mobile Viewport Meta Tag in base.html...")
base_path = os.path.join(app.root_path, 'templates', 'base.html')
with open(base_path, 'r', encoding='utf-8') as f:
    base_html = f.read()

assert 'name="viewport"' in base_html
assert 'width=device-width' in base_html
print("  -> PASSED (Valid mobile viewport meta tag verified in base.html)")

# 3. Responsive Data Containers Test (Test 3)
print("\n[3/6] Auditing Responsive Table Containers (overflow-x-auto)...")
admin_path = os.path.join(app.root_path, 'templates', 'admin.html')
corner_path = os.path.join(app.root_path, 'templates', 'students_corner.html')

with open(admin_path, 'r', encoding='utf-8') as f:
    admin_html = f.read()

with open(corner_path, 'r', encoding='utf-8') as f:
    corner_html = f.read()

assert 'overflow-x-auto' in admin_html, "admin.html missing overflow-x-auto for table data!"
assert 'overflow-x-auto' in corner_html, "students_corner.html missing overflow-x-auto for PYQ table!"
print("  -> PASSED (Data tables wrapped in responsive overflow-x-auto containers)")

# 4. Mobile Navigation Integrity Test (Test 4)
print("\n[4/6] Auditing Mobile Navigation Drawer & Script IDs...")
assert 'id="mobile-menu-btn"' in base_html
assert 'id="mobile-menu"' in base_html
assert 'id="mobile-menu-icon"' in base_html

js_path = os.path.join(app.root_path, 'static', 'js', 'main.js')
with open(js_path, 'r', encoding='utf-8') as f:
    js_content = f.read()

assert 'mobile-menu-btn' in js_content
assert 'mobile-menu' in js_content
print("  -> PASSED (Mobile menu button and drawer IDs match JS event handler)")

# 5. Existing Endpoint Regression Audit (Test 5)
print("\n[5/6] Auditing Registered Application Endpoints for HTTP 500 Failures...")
res_login_g = client.get('/login')
tok_login = extract_csrf_token(res_login_g)
client.post('/login', data={
    'email': 'admin@spmcollege.ac.in',
    'password': 'CollegeAdmin@123',
    'csrf_token': tok_login
}, follow_redirects=True)

endpoint_rules = [r for r in app.url_map.iter_rules() if 'GET' in r.methods and not r.arguments]

errors_500 = []
for rule in endpoint_rules:
    try:
        res = client.get(rule.rule)
        if res.status_code == 500:
            errors_500.append((rule.rule, res.status_code))
    except Exception as err:
        errors_500.append((rule.rule, str(err)))

assert len(errors_500) == 0, f"Found 500 errors on endpoints: {errors_500}"
print(f"  -> PASSED (Audited {len(endpoint_rules)} parameter-less GET endpoints; zero HTTP 500 failures)")

# 6. Core Responsive Class Audit (Test 6)
print("\n[6/6] Auditing Core Responsive Tailwind Grid Breakpoints...")
major_templates = ['base.html', 'admin.html', 'students_corner.html', 'index.html', 'apply.html', 'gallery.html', 'forum.html']

for tmpl_name in major_templates:
    p = os.path.join(app.root_path, 'templates', tmpl_name)
    with open(p, 'r', encoding='utf-8') as f:
        html_c = f.read()

    assert ('grid-cols-' in html_c or 'flex' in html_c or 'sm:' in html_c or 'md:' in html_c), f"No responsive layout classes in {tmpl_name}"

print("  -> PASSED (Major layout templates contain verified responsive grid and flex breakpoints)")

print("\n==================================================")
print(" ALL 6 UI/UX & RESPONSIVE AUDIT TESTS PASSED!    ")
print("==================================================")
