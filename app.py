import os
import re
import secrets
import csv
import io
import uuid
from pathlib import Path
from datetime import datetime
from PIL import Image
import pypdf
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort, g, session, send_file, Response
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.orm import joinedload, selectinload
from extensions import db, migrate, login_manager, mail
import models
from seed import seed_default_college, get_default_college, get_database_module_matrix, DEFAULT_MODULE_MATRIX
from authz import platform_super_admin_required, college_admin_required, module_admin_required, check_tenant_ownership
from email_service import send_applicant_confirmation_email, send_admin_new_application_email, send_applicant_status_update_email
from pdf_service import generate_application_receipt_pdf, generate_provisional_admission_letter, generate_question_paper_pdf
from notification_service import (
    create_notification,
    notify_college_admins,
    get_unread_count_for_context,
    get_notifications_for_context,
    mark_notification_as_read,
    mark_all_notifications_as_read
)
from rate_limiter import rate_limit, reset_rate_limiter

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'seshadripuram_college_secret_key')

# Production Session & Cookie Hardening
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('HTTPS', 'false').lower() == 'true'

# Environment-Based Flask-Mail Configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'localhost')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 25))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'false').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', None)
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', None)
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'admissions@spmcollege.ac.in')
app.config['MAIL_SUPPRESS_SEND'] = os.environ.get('MAIL_SUPPRESS_SEND', 'true').lower() == 'true'

@app.errorhandler(403)
def forbidden_error(e):
    return render_template('403.html', title="403 Forbidden - Access Denied"), 403

@app.errorhandler(429)
def too_many_requests_error(e):
    retry_after = getattr(request, 'rate_limit_retry_after', 60)
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
        res = jsonify({
            'error': 'Too Many Requests',
            'message': f'Rate limit exceeded. Please try again after {retry_after} seconds.',
            'retry_after': retry_after
        })
        res.headers['Retry-After'] = str(retry_after)
        return res, 429
    
    flash(f"⚠️ Rate limit exceeded! Please wait {retry_after} seconds before trying again.", "warning")
    res = Response(
        render_template(
            '403.html',
            title="429 Too Many Requests - Rate Limit Exceeded"
        ),
        status=429
    )
    res.headers['Retry-After'] = str(retry_after)
    return res

# Database Configuration (SQLite local, environment variable override for PostgreSQL readiness)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///college.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)
mail.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return models.User.query.get(int(user_id))

# ==============================================================================
# SECURE CMS FILE STORAGE & VALIDATION HELPERS (Requirement 2, 3, 4, 5)
# ==============================================================================

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
ALLOWED_PDF_EXTENSIONS = {'pdf'}

def get_tenant_upload_dir(college_id, category):
    """
    Returns absolute Path object for tenant directory: static/uploads/colleges/<college_id>/<category>/
    Creates directories safely if missing.
    """
    base_dir = Path(app.root_path) / 'static' / 'uploads' / 'colleges' / str(college_id) / category
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir

def validate_and_save_pdf(file_storage, college_id):
    """
    Validates PDF file storage object:
    - Extension check (.pdf)
    - Magic header byte check (%PDF-)
    - pypdf structural check
    - UUID filename generation
    Resets file pointer via seek(0) after validation!
    """
    if not file_storage or not file_storage.filename:
        return False, "No file selected."

    filename = file_storage.filename.lower()
    if '.' not in filename or filename.rsplit('.', 1)[1] not in ALLOWED_PDF_EXTENSIONS:
        return False, "Invalid file type. Only PDF documents (.pdf) are allowed."

    # Inspect magic header bytes (%PDF-)
    file_storage.seek(0)
    header = file_storage.read(5)
    file_storage.seek(0)

    if header != b'%PDF-':
        return False, "Invalid PDF file header. Execution binary or corrupted file rejected."

    # Validate actual PDF structure using pypdf
    try:
        pdf_reader = pypdf.PdfReader(file_storage)
        if len(pdf_reader.pages) < 0:
            return False, "Empty or invalid PDF structure."
    except Exception as e:
        file_storage.seek(0)
        return False, f"PDF structural validation failed: {str(e)}"
    finally:
        file_storage.seek(0)

    # Save to tenant directory with UUID filename
    tenant_dir = get_tenant_upload_dir(college_id, 'question_papers')
    unique_filename = f"{uuid.uuid4().hex}.pdf"
    save_path = tenant_dir / unique_filename

    file_storage.save(save_path)
    file_storage.seek(0)
    return True, unique_filename

def validate_and_save_image(file_storage, college_id, category='gallery'):
    """
    Validates image file storage object:
    - Extension check (.png, .jpg, .jpeg, .webp)
    - Pillow Image.open() structural check to reject text/script files
    - UUID filename generation
    Resets file pointer via seek(0) after validation!
    """
    if not file_storage or not file_storage.filename:
        return False, "No image file selected."

    filename = file_storage.filename.lower()
    if '.' not in filename or filename.rsplit('.', 1)[1] not in ALLOWED_IMAGE_EXTENSIONS:
        return False, "Invalid image format. Allowed: PNG, JPG, JPEG, WEBP."

    ext = filename.rsplit('.', 1)[1]

    # Verify actual image content using Pillow
    file_storage.seek(0)
    try:
        img = Image.open(file_storage)
        img.verify()
    except Exception as e:
        file_storage.seek(0)
        return False, f"Image content validation failed: fake or corrupted image file."
    finally:
        file_storage.seek(0)

    # Save to tenant directory with UUID filename
    tenant_dir = get_tenant_upload_dir(college_id, category)
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    save_path = tenant_dir / unique_filename

    file_storage.save(save_path)
    file_storage.seek(0)
    return True, unique_filename

def safe_delete_tenant_file(college_id, category, filename):
    """
    Path Traversal Defense File Deletion (Requirement 5).
    Uses pathlib.Path.resolve() parent-containment check!
    """
    if not filename:
        return False

    tenant_root = get_tenant_upload_dir(college_id, category).resolve()
    try:
        target_path = (tenant_root / filename).resolve()
    except Exception:
        return False

    # Verify containment check: target_path must be inside tenant_root
    if tenant_root not in target_path.parents and target_path != tenant_root:
        app.logger.warning(f"Path traversal escape attempt detected for college {college_id}: {filename}")
        return False

    if target_path.exists() and target_path.is_file():
        try:
            target_path.unlink()
            return True
        except Exception as e:
            app.logger.error(f"Error unlinking file {target_path}: {e}")
            return False
    return True

# Ensure default tenant seed data exists on startup
with app.app_context():
    try:
        seed_default_college()
    except Exception as e:
        app.logger.warning(f"Seed startup warning: {e}")

# Global CSRF Token Management & Verification
@app.before_request
def ensure_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)

@app.before_request
def verify_csrf_protection():
    if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
        form_token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
        session_token = session.get('csrf_token')
        if not form_token or not session_token or not secrets.compare_digest(str(form_token), str(session_token)):
            abort(400, description="CSRF Token Missing or Invalid")

@app.after_request
def add_security_and_cache_headers(response):
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=86400'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# Academic Courses are now fully database-backed via models.Course and seed_default_courses()



# Campus Events and Academic Calendar items are now fully database-backed via models.CampusEvent and models.AcademicCalendarItem

# Centralized Gallery Category & Fallback Metadata Map
GALLERY_FALLBACK_MAP = {
    'tech': {
        'category_label': 'Tech & Hackathons',
        'icon': 'fa-solid fa-laptop-code',
        'gradient': 'from-blue-900 to-indigo-700'
    },
    'cultural': {
        'category_label': 'Cultural Extravaganza',
        'icon': 'fa-solid fa-guitar',
        'gradient': 'from-amber-600 to-rose-600'
    },
    'sports': {
        'category_label': 'Sports Meet',
        'icon': 'fa-solid fa-trophy',
        'gradient': 'from-emerald-700 to-teal-600'
    },
    'campus': {
        'category_label': 'Campus Life',
        'icon': 'fa-solid fa-building-columns',
        'gradient': 'from-slate-800 to-slate-900'
    }
}

def get_current_modules():
    """
    Helper function to query database for the active module matrix of the default college.
    Falls back gracefully to DEFAULT_MODULE_MATRIX if DB is unavailable.
    """
    try:
        return get_database_module_matrix()
    except Exception:
        return DEFAULT_MODULE_MATRIX

def get_current_college():
    if not hasattr(g, '_current_college'):
        try:
            g._current_college = get_default_college()
        except Exception:
            g._current_college = None
    return g._current_college

@app.after_request
def add_security_headers(response):
    """
    Applies production HTTP Security Headers, CSP & Selective Caching Policy (Step 24A & Step 25).
    """
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), camera=(), microphone=()'
    
    # Selective Cache-Control Policy (Step 25 Requirement 3)
    path = request.path if request else ''
    if path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=86400'
    elif path.startswith(('/admin', '/superadmin', '/students-corner', '/login', '/notifications', '/api')):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'

    # Carefully configured Content-Security-Policy supporting Tailwind CDN, FontAwesome, Google Fonts & Clearbit
    csp_directives = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; "
        "img-src 'self' data: https: blob:; "
        "connect-src 'self' https:; "
        "frame-src 'self' https://www.google.com https://maps.google.com https://*.google.com https://*.openstreetmap.org; "
        "frame-ancestors 'self';"
    )
    response.headers['Content-Security-Policy'] = csp_directives
    return response

@app.context_processor
def inject_college_context():
    college = get_current_college()
    settings = college.settings if (college and hasattr(college, 'settings')) else None
    if not hasattr(g, '_academic_calendar'):
        if college:
            g._academic_calendar = models.AcademicCalendarItem.query.filter_by(
                college_id=college.id
            ).order_by(models.AcademicCalendarItem.display_order).all()
        else:
            g._academic_calendar = []
    return dict(
        modules=get_current_modules(),
        college=college,
        settings=settings,
        academic_calendar=g._academic_calendar,
        csrf_token=session.get('csrf_token', '')
    )

@app.route('/')
def index():
    college = get_default_college()
    events = models.CampusEvent.query.filter_by(college_id=college.id).order_by(models.CampusEvent.display_order).all()
    academic_calendar = models.AcademicCalendarItem.query.filter_by(college_id=college.id).order_by(models.AcademicCalendarItem.display_order).all()
    return render_template('index.html', title="Seshadripuram College - Shaping Futures, Building Leaders", events=events, academic_calendar=academic_calendar)

@app.route('/about')
def about():
    modules = get_current_modules()
    if not modules['about']['enabled']:
        flash("⚠️ About Us module is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))
    return render_template('about.html', title="About Us - Seshadripuram College")

@app.route('/admission')
def admission():
    modules = get_current_modules()
    if not modules['admission']['enabled']:
        flash("⚠️ Admission module is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))
    return render_template('admission.html', title="Admissions 2026-27 - Seshadripuram College")

ALLOWED_COURSES = [
    'BCA - Bachelor of Computer Applications',
    'BBA - Bachelor of Business Administration',
    'BCom - Bachelor of Commerce',
    'BA - Bachelor of Arts',
    'BSc - Bachelor of Science',
    'MCA - Master of Computer Applications',
    'MBA - Master of Business Administration',
    'MCom - Master of Commerce',
    'MSc - Master of Science'
]

def generate_application_number():
    """
    Generates a unique, persistent application number (e.g. SC2026-A1B2C3)
    guaranteed to be unique across all records in the database.
    """
    while True:
        candidate = f"SC2026-{os.urandom(3).hex().upper()}"
        if not models.AdmissionApplication.query.filter_by(application_number=candidate).first():
            return candidate

@app.route('/apply', methods=['GET', 'POST'])
@rate_limit(limit=5, period=3600, scope='apply')
def apply():
    modules = get_current_modules()
    if not modules['admission']['enabled']:
        flash("⚠️ Online Applications are currently closed site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        guardian_name = request.form.get('guardian_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        course = request.form.get('course', '').strip()
        raw_percentage = request.form.get('percentage', '').strip()

        # Server-side Validation
        errors = []
        if not full_name:
            errors.append("Full student name is required.")
        if not guardian_name:
            errors.append("Father / Guardian name is required.")
        if not email or '@' not in email or '.' not in email:
            errors.append("A valid email address is required.")
        if not phone or len(phone) < 8:
            errors.append("A valid phone number is required.")
        
        # Course validation
        matching_course = next((c for c in ALLOWED_COURSES if course.lower() in c.lower()), None)
        if not matching_course and course not in ALLOWED_COURSES:
            errors.append("Please select a valid academic program from the list.")
        else:
            course = matching_course if matching_course else course

        # Percentage validation
        try:
            percentage = float(raw_percentage)
            if percentage < 35.0 or percentage > 100.0:
                errors.append("Marks percentage must be between 35% and 100%.")
        except (ValueError, TypeError):
            errors.append("Please enter a valid numeric percentage.")

        if errors:
            for err in errors:
                flash(f"⚠️ Validation Error: {err}", "warning")
            return redirect(url_for('apply'))

        # Active College Resolution
        college = get_default_college()
        if not college:
            flash("⚠️ Unable to resolve institutional tenant context.", "warning")
            return redirect(url_for('apply'))

        # Duplicate Submission Protection (Same college, email, and course)
        existing_app = models.AdmissionApplication.query.filter_by(
            college_id=college.id,
            email=email,
            course=course
        ).first()

        if existing_app:
            flash(f"⚠️ Application Notice: An application for {course} associated with email '{email}' has already been submitted under Application ID {existing_app.application_number}.", "warning")
            return redirect(url_for('apply'))

        # Generate persistent application number and save
        app_number = generate_application_number()
        new_app = models.AdmissionApplication(
            college_id=college.id,
            application_number=app_number,
            full_name=full_name,
            guardian_name=guardian_name,
            email=email,
            phone=phone,
            course=course,
            percentage=percentage,
            status='PENDING'
        )

        db.session.add(new_app)
        db.session.commit()

        # Generate secure receipt access token for this session
        receipt_token = secrets.token_urlsafe(16)
        if 'receipt_tokens' not in session:
            session['receipt_tokens'] = {}
        session['receipt_tokens'][new_app.application_number] = receipt_token
        session.modified = True

        # Trigger In-App Notifications (Requirement 2 & 3: Multi-admin alert + applicant notification)
        try:
            notify_college_admins(
                college_id=college.id,
                title=f"New Application Received: {new_app.application_number}",
                message=f"New online application {new_app.application_number} submitted by {new_app.full_name} for {new_app.course}.",
                category='admissions',
                link='/admin'
            )
            create_notification(
                college_id=college.id,
                title=f"Application {new_app.application_number} Received",
                message=f"Dear {new_app.full_name}, your application for {new_app.course} has been submitted successfully.",
                category='admissions',
                recipient_email=new_app.email,
                application_number=new_app.application_number,
                link='/students-corner'
            )
        except Exception as notif_err:
            app.logger.error(f"In-app notification dispatch error on submission: {notif_err}")

        # Trigger email notifications (isolated so SMTP errors never break submission)
        try:
            send_applicant_confirmation_email(new_app, college)
            send_admin_new_application_email(new_app, college)
        except Exception as mail_err:
            app.logger.error(f"Application submission email notification error: {mail_err}")

        receipt_url = url_for('download_application_receipt', app_number=new_app.application_number, token=receipt_token)
        flash(f"🎉 Thank you {full_name}! Your application for {course} has been submitted successfully. Application ID: {new_app.application_number}. <a href='{receipt_url}' target='_blank' class='underline font-bold ml-1 text-amber-300 hover:text-amber-200'>📄 Download Official PDF Receipt</a>", "success")
        return redirect(url_for('apply'))

    return render_template('apply.html', title="Online Application Form 2026-27")

@app.route('/admission/receipt/<app_number>')
@rate_limit(limit=20, period=300, scope='pdf_download', only_post=False)
def download_application_receipt(app_number):
    app_record = models.AdmissionApplication.query.filter_by(application_number=app_number).first_or_404()
    
    # Secure Receipt Access Control Check (Requirement 1):
    # Allowed IF:
    # 1. Logged in Admin or Super Admin user (COLLEGE_ADMIN or PLATFORM_SUPER_ADMIN)
    # 2. Query token matches session token generated during application submission
    # 3. Logged in user with matching email
    user_role = getattr(current_user, 'role', '').upper() if current_user.is_authenticated else ''
    user_is_admin = current_user.is_authenticated and (user_role in ['COLLEGE_ADMIN', 'PLATFORM_SUPER_ADMIN', 'ADMIN', 'SUPERADMIN'])
    token = request.args.get('token', '').strip()
    session_tokens = session.get('receipt_tokens', {})
    session_token = session_tokens.get(app_number) if isinstance(session_tokens, dict) else None
    token_valid = (token and session_token and secrets.compare_digest(token, session_token))
    student_matches = current_user.is_authenticated and hasattr(current_user, 'email') and current_user.email == app_record.email

    applicant_access = session.get('applicant_access', {})
    applicant_session_valid = (
        isinstance(applicant_access, dict) and
        applicant_access.get('app_number') == app_number and
        applicant_access.get('college_id') == app_record.college_id
    )

    if not (user_is_admin or token_valid or student_matches or applicant_session_valid):
        flash("🔒 Security Alert: Unauthorized attempt to download student application receipt. Please log in as an authorized admin or use your valid receipt token.", "warning")
        return abort(403)

    # Tenant ownership check if admin
    if user_is_admin and not check_tenant_ownership(app_record.college_id):
        return abort(403)

    college = get_default_college()
    pdf_buffer = generate_application_receipt_pdf(app_record, college)
    
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        download_name=f'Receipt_{app_number}.pdf',
        as_attachment=False
    )

@app.route('/verify-receipt/<app_number>')
def verify_application_receipt(app_number):
    app_record = models.AdmissionApplication.query.filter_by(application_number=app_number).first()
    college = get_default_college()
    college_setting = college.settings if college else None
    return render_template(
        'verify_receipt.html',
        app_record=app_record,
        app_number=app_number,
        college=college,
        college_setting=college_setting,
        title=f"Receipt Verification - {app_number}"
    )

@app.route('/academics')
def academics():
    modules = get_current_modules()
    if not modules['academics']['enabled']:
        flash("⚠️ Academics & Syllabus module is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))
    college = get_default_college()
    courses = models.Course.query.filter_by(college_id=college.id).order_by(models.Course.id).all()
    return render_template('departments.html', courses=courses, title="Academics & Syllabus - Seshadripuram College")

@app.route('/departments')
def departments():
    modules = get_current_modules()
    if not modules['departments']['enabled']:
        flash("⚠️ Departments module is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))
    college = get_default_college()
    courses = models.Course.query.filter_by(college_id=college.id).order_by(models.Course.id).all()
    return render_template('departments.html', courses=courses, title="Academic Departments - Seshadripuram College")

@app.route('/course/<course_code>')
def course_detail(course_code):
    modules = get_current_modules()
    if not modules['academics']['enabled']:
        flash("⚠️ Course details are currently offline site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))
    college = get_default_college()
    course = models.Course.query.options(
        joinedload(models.Course.outcome_records),
        selectinload(models.Course.semesters).selectinload(models.CurriculumSemester.subjects),
        selectinload(models.Course.question_papers)
    ).filter(
        models.Course.college_id == college.id,
        db.func.lower(models.Course.code) == course_code.strip().lower()
    ).first_or_404()

    is_pg = ('PG' in (course.level or '')) or ('Postgraduate' in (course.level or '')) or ('Master' in (course.name or ''))
    sem_list = ['1st Sem', '2nd Sem', '3rd Sem', '4th Sem'] if is_pg else ['1st Sem', '2nd Sem', '3rd Sem', '4th Sem', '5th Sem', '6th Sem']

    # Pre-group question papers into their respective semester bins
    sem_papers = {s: [] for s in sem_list}
    for paper in (course.question_papers or []):
        p_match = re.search(r'\d+', paper.semester or '')
        p_num = p_match.group(0) if p_match else ''
        assigned = False
        for s in sem_list:
            s_match = re.search(r'\d+', s)
            s_num = s_match.group(0) if s_match else ''
            if s_num and s_num == p_num:
                sem_papers[s].append(paper)
                assigned = True
                break
        if not assigned and sem_list:
            sem_papers[sem_list[0]].append(paper)

    return render_template(
        'course_detail.html',
        course=course,
        sem_list=sem_list,
        sem_papers=sem_papers,
        is_pg=is_pg,
        title=f"{course.code} - {course.name}"
    )

@app.route('/facilities')
def facilities():
    modules = get_current_modules()
    if not modules['facilities']['enabled']:
        flash("⚠️ Facilities module is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))
    return render_template('facilities.html', title="Campus Infrastructure & Facilities - Seshadripuram College")

@app.route('/faculty')
def faculty_directory():
    modules = get_current_modules()
    if not modules['academics']['enabled']:
        flash("⚠️ Faculty Directory module is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))

    college = get_default_college()
    dept = request.args.get('dept', '').strip().upper()

    query = models.FacultyMember.query.filter_by(college_id=college.id, is_active=True)
    if dept:
        query = query.filter_by(department_code=dept)

    faculty_members = query.order_by(models.FacultyMember.display_order.asc(), models.FacultyMember.id.asc()).all()

    dept_rows = db.session.query(models.FacultyMember.department_code).filter_by(college_id=college.id, is_active=True).distinct().all()
    dept_codes = [d[0] for d in dept_rows] if dept_rows else ['BCA', 'BBA', 'BCOM', 'MCA', 'HUMANITIES']

    return render_template(
        'faculty.html',
        title="Faculty & Staff Directory - Seshadripuram College",
        faculty_members=faculty_members,
        dept_codes=dept_codes,
        selected_dept=dept
    )

@app.route('/placements')
def placements():
    modules = get_current_modules()
    if not modules['placements']['enabled']:
        flash("⚠️ Placements module is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))

    college = get_default_college()
    status_filter = request.args.get('status', '').strip().upper()

    query = models.PlacementDrive.query.filter_by(college_id=college.id, is_active=True)
    if status_filter and status_filter in ['UPCOMING', 'ONGOING', 'COMPLETED', 'CANCELLED']:
        query = query.filter_by(status=status_filter)

    drives = query.order_by(models.PlacementDrive.id.desc()).all()
    return render_template(
        'placements.html',
        title="Placements & Career Cell - Seshadripuram College",
        placement_drives=drives,
        selected_status=status_filter
    )

@app.route('/gallery')
def gallery():
    modules = get_current_modules()
    if not modules['gallery']['enabled']:
        flash("⚠️ Gallery module is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))
    
    college = get_default_college()
    gallery_items = models.GalleryItem.query.filter_by(
        college_id=college.id
    ).order_by(models.GalleryItem.created_at.desc(), models.GalleryItem.id.desc()).all()
    
    return render_template('gallery.html', title="Campus Photo & Video Gallery - Seshadripuram College", gallery_items=gallery_items)

# Gallery Add Photo
@app.route('/gallery/add', methods=['POST'])
@module_admin_required('gallery')
def gallery_add():
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'campus').strip().lower()
    description = request.form.get('description', '').strip()
    image_url = request.form.get('image_url', '').strip()
    image_file = request.files.get('image_file')

    if not title:
        flash("⚠️ Validation Error: Image title is required.", "warning")
        return redirect(url_for('admin'))

    if category not in GALLERY_FALLBACK_MAP:
        category = 'campus'

    # Support real image file upload with Pillow validation (Requirement 4)
    saved_image_name = image_url
    if image_file and image_file.filename:
        success, filename_or_err = validate_and_save_image(image_file, current_user.college_id)
        if not success:
            flash(f"⚠️ Image Upload Error: {filename_or_err}", "warning")
            return redirect(url_for('admin'))
        saved_image_name = filename_or_err

    fallback = GALLERY_FALLBACK_MAP.get(category, GALLERY_FALLBACK_MAP['campus'])
    
    new_item = models.GalleryItem(
        college_id=current_user.college_id,
        title=title,
        category=category,
        category_label=fallback['category_label'],
        description=description if description else 'New photo uploaded to college archives.',
        icon=fallback['icon'],
        gradient=fallback['gradient'],
        image_url=saved_image_name
    )
    db.session.add(new_item)
    db.session.commit()
    
    flash(f"🖼️ Photo '{new_item.title}' added to Campus Gallery successfully!", "success")
    
    ref = request.referrer
    if ref and ('superadmin' in ref or 'admin' in ref or 'gallery' in ref):
        return redirect(ref)
    return redirect(url_for('gallery'))

# Gallery Delete Photo
@app.route('/gallery/delete/<int:item_id>', methods=['POST'])
@module_admin_required('gallery')
def gallery_delete(item_id):
    target = models.GalleryItem.query.get_or_404(item_id)
    
    # Tenant ownership verification
    if not check_tenant_ownership(target.college_id):
        abort(403)

    # Path-safe deletion (Requirement 5)
    if target.image_url:
        safe_delete_tenant_file(target.college_id, 'gallery', target.image_url)
        
    db.session.delete(target)
    db.session.commit()
    
    flash(f"🗑️ Photo '{target.title}' removed from Campus Gallery.", "info")
    
    ref = request.referrer
    if ref and ('superadmin' in ref or 'admin' in ref or 'gallery' in ref):
        return redirect(ref)
    return redirect(url_for('gallery'))

@app.route('/students-corner', methods=['GET', 'POST'])
@rate_limit(limit=10, period=60, scope='students_corner')
def students_corner():
    modules = get_current_modules()
    if not modules['students_corner']['enabled']:
        flash("⚠️ Students Corner is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))

    college = get_default_college()
    lookup_error = None

    # Handle POST tracking lookup
    if request.method == 'POST':
        if 'applicant_access' in session:
            session.pop('applicant_access', None)

        tracking_id = request.form.get('tracking_id', '').strip().upper()
        email = request.form.get('email', '').strip().lower()

        if not tracking_id or not email:
            lookup_error = "Please enter both your Tracking ID and registered Email Address."
        else:
            # Strict tenant-scoped query with normalized email comparison (Requirement 1)
            app_match = models.AdmissionApplication.query.filter(
                models.AdmissionApplication.college_id == college.id,
                models.AdmissionApplication.application_number == tracking_id,
                db.func.lower(models.AdmissionApplication.email) == email
            ).first()

            if app_match:
                # Store minimal secure session context (Requirement 2)
                session['applicant_access'] = {
                    'app_id': app_match.id,
                    'app_number': app_match.application_number,
                    'application_number': app_match.application_number,
                    'college_id': app_match.college_id,
                    'email': app_match.email,
                    'full_name': app_match.full_name
                }
                session.modified = True
                flash(f"✅ Welcome back! Application '{app_match.application_number}' verified.", "success")
                return redirect(url_for('students_corner'))
            else:
                lookup_error = f"No application matching Tracking ID '{tracking_id}' and Email '{email}' was found for this institution."

    # Resolve active student application from session if authorized
    active_app = None
    doc_requests = []
    applicant_sess = session.get('applicant_access')
    if isinstance(applicant_sess, dict):
        app_id = applicant_sess.get('app_id')
        app_num = applicant_sess.get('application_number')
        tenant_id = applicant_sess.get('college_id')
        if tenant_id == college.id and app_id and app_num:
            active_app = models.AdmissionApplication.query.filter_by(
                id=app_id,
                college_id=college.id,
                application_number=app_num
            ).first()

            if active_app:
                doc_requests = models.StudentDocumentRequest.query.filter_by(
                    college_id=college.id,
                    application_number=active_app.application_number
                ).order_by(models.StudentDocumentRequest.created_at.desc()).all()

    # Query Question Papers (PYQ) strictly scoped to active tenant via Course relationship (Requirement 3)
    search_q = request.args.get('q', '').strip()
    qp_query = models.QuestionPaper.query.options(joinedload(models.QuestionPaper.course)).join(models.Course).filter(models.Course.college_id == college.id)
    if search_q:
        qp_query = qp_query.filter(
            (models.QuestionPaper.subject.ilike(f"%{search_q}%")) |
            (models.QuestionPaper.year.ilike(f"%{search_q}%")) |
            (models.QuestionPaper.semester.ilike(f"%{search_q}%"))
        )
    question_papers = qp_query.order_by(models.QuestionPaper.created_at.desc()).all()

    # Query Academic Calendar items & announcements
    calendar_items = models.AcademicCalendarItem.query.filter_by(college_id=college.id).order_by(models.AcademicCalendarItem.display_order.asc()).all()
    announcements = models.ForumPost.query.filter_by(college_id=college.id).order_by(models.ForumPost.created_at.desc()).limit(3).all()

    return render_template(
        'students_corner.html',
        title="Student Portal & Applicant Dashboard - Seshadripuram College",
        active_app=active_app,
        doc_requests=doc_requests,
        lookup_error=lookup_error,
        question_papers=question_papers,
        calendar_items=calendar_items,
        announcements=announcements,
        search_q=search_q
    )

@app.route('/students-corner/logout')
def student_dashboard_logout():
    # Only clear applicant dashboard session key (Requirement 2)
    if 'applicant_access' in session:
        session.pop('applicant_access', None)
        session.modified = True
        flash("ℹ️ You have logged out of your Applicant Dashboard session.", "info")
    return redirect(url_for('students_corner'))

FORUM_CATEGORIES = [
    'Placements & Careers',
    'Events & Fests',
    'Entrepreneurship',
    'Alumni Network',
    'Academics & Question Papers'
]

@app.route('/forum', methods=['GET'])
def forum():
    modules = get_current_modules()
    if not modules['forum']['enabled']:
        flash("⚠️ Community Forum is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))
        
    college = get_default_college()
    posts = models.ForumPost.query.options(
        selectinload(models.ForumPost.reply_records)
    ).filter_by(
        college_id=college.id
    ).order_by(
        models.ForumPost.created_at.desc(),
        models.ForumPost.id.desc()
    ).all()

    return render_template('forum.html', posts=posts, title="Campus Community Forum - Seshadripuram College")

@app.route('/forum/add', methods=['POST'])
@module_admin_required('forum')
def add_forum_post():
    author = request.form.get('author', '').strip()
    category = request.form.get('category', '').strip()
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    
    if not title:
        flash("⚠️ Validation Error: Forum title is required.", "warning")
        return redirect(request.referrer or url_for('admin'))
        
    if len(title) > 250:
        flash("⚠️ Validation Error: Forum title is too long.", "warning")
        return redirect(request.referrer or url_for('admin'))

    if not category or category not in FORUM_CATEGORIES:
        flash("⚠️ Validation Error: Invalid forum category selected.", "warning")
        return redirect(request.referrer or url_for('admin'))

    if not content:
        flash("⚠️ Validation Error: Forum content is required.", "warning")
        return redirect(request.referrer or url_for('admin'))

    if len(author) > 150:
        flash("⚠️ Validation Error: Author name is too long.", "warning")
        return redirect(request.referrer or url_for('admin'))

    new_post = models.ForumPost(
        college_id=current_user.college_id,
        author=author if author else 'College Administrator',
        title=title,
        category=category,
        content=content,
        replies=0,
        likes=0
    )
    db.session.add(new_post)
    db.session.commit()
    
    flash(f"💬 Discussion topic '{new_post.title}' published successfully!", "success")
    
    ref = request.referrer
    if ref and ('superadmin' in ref or 'admin' in ref or 'forum' in ref):
        return redirect(ref)
    return redirect(url_for('forum'))

@app.route('/forum/delete/<int:post_id>', methods=['POST'])
@module_admin_required('forum')
def delete_forum_post(post_id):
    target = models.ForumPost.query.get_or_404(post_id)
    
    # Tenant ownership security check
    if not check_tenant_ownership(target.college_id):
        abort(403)
        
    db.session.delete(target)
    db.session.commit()
    
    flash(f"🗑️ Forum post deleted successfully.", "info")
    
    ref = request.referrer
    if ref and ('superadmin' in ref or 'admin' in ref or 'forum' in ref):
        return redirect(ref)
    return redirect(url_for('forum'))

@app.route('/forum/reply/<int:post_id>', methods=['POST'])
@rate_limit(limit=10, period=60, scope='forum_reply')
def add_forum_reply(post_id):
    modules = get_current_modules()
    if not modules['forum']['enabled']:
        flash("⚠️ Forum replies are currently disabled.", "warning")
        return redirect(url_for('forum'))

    college = get_default_college()
    # Strict tenant-scoped post lookup (Security Rule)
    post = models.ForumPost.query.filter_by(id=post_id, college_id=college.id).first_or_404()

    author = request.form.get('author', '').strip()
    content = request.form.get('content', '').strip()

    if not content:
        flash("⚠️ Validation Error: Reply content cannot be empty.", "warning")
        return redirect(url_for('forum'))

    is_admin = current_user.is_authenticated and hasattr(current_user, 'role') and current_user.role in ['COLLEGE_ADMIN', 'PLATFORM_SUPER_ADMIN']
    
    reply_author = author if author else ('College Administration Staff' if is_admin else 'Student Member')

    reply = models.ForumReply(
        post_id=post.id,
        author=reply_author,
        user_id=current_user.id if current_user.is_authenticated else None,
        is_admin_reply=is_admin,
        content=content
    )
    db.session.add(reply)
    
    # Increment replies counter on post
    post.replies = (post.replies or 0) + 1
    db.session.commit()

    # Trigger notification if visitor replied to admin post or vice versa
    if not is_admin:
        notify_college_admins(
            college_id=college.id,
            title="New Forum Reply Posted 💬",
            message=f"New community reply on topic '{post.title}': \"{content[:60]}...\"",
            category="forum",
            link="/forum"
        )

    flash("💬 Your reply has been posted successfully!", "success")
    return redirect(url_for('forum'))

@app.route('/forum/like/<int:post_id>', methods=['POST'])
@rate_limit(limit=10, period=60, scope='forum_like')
def like_forum_post(post_id):
    modules = get_current_modules()
    if not modules['forum']['enabled']:
        return jsonify({'error': 'Forum disabled'}), 403

    college = get_default_college()
    # Strict tenant-scoped post lookup (Security Rule)
    post = models.ForumPost.query.filter_by(id=post_id, college_id=college.id).first_or_404()

    liked_posts = session.get('liked_posts', [])
    if post_id in liked_posts:
        return jsonify({
            'status': 'already_liked',
            'likes_count': post.likes_count or post.likes or 0,
            'message': 'You have already upvoted this topic.'
        })

    # Increment likes count safely
    post.likes_count = (post.likes_count or 0) + 1
    post.likes = post.likes_count
    db.session.commit()

    liked_posts.append(post_id)
    session['liked_posts'] = liked_posts

    return jsonify({
        'status': 'success',
        'likes_count': post.likes_count,
        'message': 'Topic upvoted!'
    })

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        flash(f"✉️ Thank you {name}! Your message has been sent to Seshadripuram College Admin Office.", "success")
        return redirect(url_for('contact'))
    return render_template('contact.html', title="Contact Us - Seshadripuram College")

# AUTHENTICATION & LOGIN ROUTES
@app.route('/login', methods=['GET', 'POST'])
@rate_limit(limit=5, period=60, scope='login')
def login():
    if current_user.is_authenticated:
        if current_user.is_super_admin:
            return redirect(url_for('superadmin'))
        return redirect(url_for('admin'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = True if request.form.get('remember') else False

        user = models.User.query.filter_by(email=email).first()
        if user and user.is_active and user.check_password(password):
            login_user(user, remember=remember)
            flash(f"🔓 Welcome back, {user.email}!", "success")
            next_page = request.args.get('next') or request.form.get('next')
            if next_page and next_page.startswith('/') and not next_page.startswith('//') and '\\' not in next_page and 'http:' not in next_page and 'https:' not in next_page:
                return redirect(next_page)
            if user.is_super_admin:
                return redirect(url_for('superadmin'))
            return redirect(url_for('admin'))

        flash("Invalid credentials.", "warning")

    return render_template('login.html', title="Administrator & Portal Login")

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    if current_user.is_authenticated:
        logout_user()
        flash("🔒 You have been logged out successfully.", "info")
    return redirect(url_for('login'))

def sanitize_csv_val(val):
    """Sanitizes CSV fields against CSV Injection (=, +, -, @, tab, CR prefix)."""
    if val is None:
        return ""
    val_str = str(val)
    if val_str and val_str[0] in ['=', '+', '-', '@', '\t', '\r']:
        return f"'{val_str}"
    return val_str

@app.route('/admin')
@college_admin_required
def admin():
    modules = get_current_modules()
    applications = []
    gallery_items = []
    forum_posts = []
    courses = []
    question_papers = []
    campus_events = []
    academic_calendar_items = []

    # Real-Time Analytics Metrics (Requirement 2)
    stats = {
        'total': 0,
        'verified': 0,
        'seat_locked': 0,
        'pending_review': 0,
        'rejected': 0
    }
    course_counts = {}

    # Query & Filter Parameters (Requirement 5)
    q = request.args.get('q', '').strip()
    course_filter = request.args.get('course_filter', '').strip()
    status_filter = request.args.get('status_filter', '').strip().upper()
    
    # Safe Pagination handling (Requirement 5)
    raw_page = request.args.get('page', '1')
    try:
        page = int(raw_page)
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    per_page = 10
    total_pages = 1
    total_filtered = 0

    if current_user.college_id:
        if modules.get('admission', {}).get('admin_access'):
            base_app_query = models.AdmissionApplication.query.filter_by(
                college_id=current_user.college_id
            )
            
            # Real-Time Tenant Metrics (Includes 5th Rejected card)
            stats['total'] = base_app_query.count()
            stats['verified'] = base_app_query.filter_by(status='VERIFIED').count()
            stats['seat_locked'] = base_app_query.filter_by(status='SEAT_LOCKED').count()
            stats['pending_review'] = base_app_query.filter(
                models.AdmissionApplication.status.in_(['PENDING', 'UNDER_REVIEW'])
            ).count()
            stats['rejected'] = base_app_query.filter_by(status='REJECTED').count()

            # Course Distribution Breakdown
            all_courses = models.Course.query.filter_by(college_id=current_user.college_id).all()
            for c_item in all_courses:
                course_counts[c_item.name] = base_app_query.filter_by(course=c_item.name).count()

            # Filtered List Query
            list_query = base_app_query
            if q:
                list_query = list_query.filter(
                    (models.AdmissionApplication.full_name.ilike(f"%{q}%")) |
                    (models.AdmissionApplication.application_number.ilike(f"%{q}%")) |
                    (models.AdmissionApplication.email.ilike(f"%{q}%")) |
                    (models.AdmissionApplication.phone.ilike(f"%{q}%"))
                )
            if course_filter:
                list_query = list_query.filter(models.AdmissionApplication.course == course_filter)
            if status_filter in ADMISSION_STATUSES:
                list_query = list_query.filter(models.AdmissionApplication.status == status_filter)

            total_filtered = list_query.count()
            total_pages = max(1, (total_filtered + per_page - 1) // per_page)
            if page > total_pages:
                page = total_pages

            applications = list_query.order_by(
                models.AdmissionApplication.created_at.desc()
            ).offset((page - 1) * per_page).limit(per_page).all()
            
        if modules.get('gallery', {}).get('admin_access'):
            gallery_items = models.GalleryItem.query.filter_by(
                college_id=current_user.college_id
            ).order_by(models.GalleryItem.created_at.desc(), models.GalleryItem.id.desc()).all()

        if modules.get('forum', {}).get('admin_access'):
            forum_posts = models.ForumPost.query.filter_by(
                college_id=current_user.college_id
            ).order_by(models.ForumPost.created_at.desc(), models.ForumPost.id.desc()).all()

        if modules.get('academics', {}).get('admin_access') or modules.get('question_papers', {}).get('admin_access'):
            courses = models.Course.query.filter_by(
                college_id=current_user.college_id
            ).order_by(models.Course.code).all()

        if modules.get('question_papers', {}).get('admin_access'):
            question_papers = models.QuestionPaper.query.options(
                joinedload(models.QuestionPaper.course)
            ).join(models.Course).filter(
                models.Course.college_id == current_user.college_id
            ).order_by(models.QuestionPaper.created_at.desc(), models.QuestionPaper.id.desc()).all()

        if modules.get('news_events', {}).get('admin_access'):
            campus_events = models.CampusEvent.query.filter_by(
                college_id=current_user.college_id
            ).order_by(models.CampusEvent.display_order).all()
            academic_calendar_items = models.AcademicCalendarItem.query.filter_by(
                college_id=current_user.college_id
            ).order_by(models.AcademicCalendarItem.display_order).all()

        doc_requests = models.StudentDocumentRequest.query.filter_by(
            college_id=current_user.college_id
        ).order_by(models.StudentDocumentRequest.created_at.desc()).all()

        event_registrations = models.EventRegistration.query.filter_by(
            college_id=current_user.college_id
        ).order_by(models.EventRegistration.created_at.desc()).all()

    return render_template(
        'admin.html',
        title="College Admin Portal",
        modules=modules,
        gallery_items=gallery_items,
        applications=applications,
        forum_posts=forum_posts,
        courses=courses,
        question_papers=question_papers,
        campus_events=campus_events,
        academic_calendar_items=academic_calendar_items,
        doc_requests=doc_requests,
        event_registrations=event_registrations,
        stats=stats,
        course_counts=course_counts,
        q=q,
        course_filter=course_filter,
        status_filter=status_filter,
        page=page,
        total_pages=total_pages,
        total_filtered=total_filtered
    )

@app.route('/admin/applications/export')
@module_admin_required('admission')
def export_admission_applications():
    if not current_user.college_id:
        return abort(403)

    q = request.args.get('q', '').strip()
    course_filter = request.args.get('course_filter', '').strip()
    status_filter = request.args.get('status_filter', '').strip().upper()

    query = models.AdmissionApplication.query.filter_by(college_id=current_user.college_id)
    if q:
        query = query.filter(
            (models.AdmissionApplication.full_name.ilike(f"%{q}%")) |
            (models.AdmissionApplication.application_number.ilike(f"%{q}%")) |
            (models.AdmissionApplication.email.ilike(f"%{q}%")) |
            (models.AdmissionApplication.phone.ilike(f"%{q}%"))
        )
    if course_filter:
        query = query.filter(models.AdmissionApplication.course == course_filter)
    if status_filter in ADMISSION_STATUSES:
        query = query.filter(models.AdmissionApplication.status == status_filter)

    exported_records = query.order_by(models.AdmissionApplication.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Tracking ID', 'Full Name', 'Guardian Name', 'Email', 'Phone', 'Course', 'Percentage', 'Status', 'Submission Date'])

    for app_item in exported_records:
        writer.writerow([
            sanitize_csv_val(app_item.application_number),
            sanitize_csv_val(app_item.full_name),
            sanitize_csv_val(app_item.guardian_name),
            sanitize_csv_val(app_item.email),
            sanitize_csv_val(app_item.phone),
            sanitize_csv_val(app_item.course),
            sanitize_csv_val(app_item.percentage),
            sanitize_csv_val(app_item.status),
            sanitize_csv_val(app_item.created_at.strftime('%Y-%m-%d %H:%M:%S') if app_item.created_at else '')
        ])

    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=Admissions_Export_{timestamp}.csv'
        }
    )

@app.route('/admin/admission/detail/<int:app_id>')
@module_admin_required('admission')
def get_applicant_detail(app_id):
    # Strict tenant scoping: Returns HTTP 404 if application belongs to another college (Requirement 3 & GET read-only Requirement 4)
    app_record = models.AdmissionApplication.query.filter_by(
        id=app_id,
        college_id=current_user.college_id
    ).first_or_404()

    return jsonify({
        'id': app_record.id,
        'application_number': app_record.application_number,
        'full_name': app_record.full_name,
        'guardian_name': app_record.guardian_name,
        'email': app_record.email,
        'phone': app_record.phone,
        'course': app_record.course,
        'percentage': app_record.percentage,
        'status': app_record.status,
        'created_at': app_record.created_at.strftime('%B %d, %Y, %I:%M %p') if app_record.created_at else ''
    })

def get_current_notification_context():
    """
    Resolves notification recipient context from authenticated User OR secure applicant session.
    Never accepts raw client query inputs for recipient scoping (Requirement 1 & 5).
    """
    college = get_default_college()
    if current_user.is_authenticated:
        return {
            'college_id': current_user.college_id or college.id,
            'user_id': current_user.id,
            'email': None,
            'app_num': None
        }
    applicant_sess = session.get('applicant_access')
    if isinstance(applicant_sess, dict):
        tenant_id = applicant_sess.get('college_id')
        email = applicant_sess.get('email')
        app_num = applicant_sess.get('app_number') or applicant_sess.get('application_number')
        if tenant_id == college.id and email and app_num:
            return {
                'college_id': college.id,
                'user_id': None,
                'email': email,
                'app_num': app_num
            }
    return None

@app.route('/notifications/unread-count')
def notifications_unread_count():
    ctx = get_current_notification_context()
    if not ctx:
        return jsonify({'unread_count': 0})
    count = get_unread_count_for_context(
        college_id=ctx['college_id'],
        user_id=ctx['user_id'],
        email=ctx['email'],
        app_num=ctx['app_num']
    )
    return jsonify({'unread_count': count})

@app.route('/notifications/list')
def notifications_list():
    ctx = get_current_notification_context()
    if not ctx:
        return jsonify([])
    items = get_notifications_for_context(
        college_id=ctx['college_id'],
        user_id=ctx['user_id'],
        email=ctx['email'],
        app_num=ctx['app_num'],
        limit=10
    )
    result = []
    for item in items:
        result.append({
            'id': item.id,
            'title': item.title,
            'message': item.message,
            'category': item.category,
            'link': item.link,
            'is_read': item.is_read,
            'created_at': item.created_at.strftime('%b %d, %H:%M') if item.created_at else ''
        })
    return jsonify(result)

@app.route('/notifications/read/<int:notif_id>', methods=['POST'])
def notifications_mark_read(notif_id):
    ctx = get_current_notification_context()
    if not ctx:
        return jsonify({'success': False, 'error': 'Unauthorized context'}), 403

    success = mark_notification_as_read(
        notif_id=notif_id,
        college_id=ctx['college_id'],
        user_id=ctx['user_id'],
        email=ctx['email'],
        app_num=ctx['app_num']
    )
    if success:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Notification not found or access denied'}), 404

@app.route('/notifications/read-all', methods=['POST'])
def notifications_mark_all_read():
    ctx = get_current_notification_context()
    if not ctx:
        return jsonify({'success': False, 'error': 'Unauthorized context'}), 403

    count = mark_all_notifications_as_read(
        college_id=ctx['college_id'],
        user_id=ctx['user_id'],
        email=ctx['email'],
        app_num=ctx['app_num']
    )
    return jsonify({'success': True, 'count': count})

ADMISSION_STATUSES = {
    'PENDING',
    'UNDER_REVIEW',
    'VERIFIED',
    'SEAT_LOCKED',
    'REJECTED'
}

ALLOWED_ADMISSION_TRANSITIONS = {
    'PENDING': {'UNDER_REVIEW', 'REJECTED'},
    'UNDER_REVIEW': {'PENDING', 'VERIFIED', 'REJECTED'},
    'VERIFIED': {'SEAT_LOCKED', 'UNDER_REVIEW', 'REJECTED'},
    'SEAT_LOCKED': {'VERIFIED'},
    'REJECTED': {'UNDER_REVIEW'}
}

@app.route('/admin/admission/status/<int:app_id>', methods=['POST'])
@module_admin_required('admission')
def update_application_status(app_id):
    new_status = request.form.get('status', '').strip().upper()
    
    if new_status not in ADMISSION_STATUSES:
        flash("⚠️ Validation Error: Invalid admission status specified.", "warning")
        return redirect(url_for('admin'))
        
    app_record = models.AdmissionApplication.query.get_or_404(app_id)
    
    # Tenant ownership security check
    if not check_tenant_ownership(app_record.college_id):
        abort(403)

    current_status = app_record.status.upper()
    old_status = current_status
    
    if new_status == current_status:
        flash(f"ℹ️ Application '{app_record.application_number}' is already in {current_status} status.", "info")
        return redirect(url_for('admin'))
        
    allowed_next = ALLOWED_ADMISSION_TRANSITIONS.get(current_status, set())
    
    if new_status not in allowed_next:
        flash(f"⚠️ Validation Error: Illegal status transition from {current_status} to {new_status}.", "warning")
        return redirect(url_for('admin'))
        
    app_record.status = new_status
    if new_status == 'SEAT_LOCKED':
        provision_student_from_application(app_record)
    db.session.commit()

    # Trigger In-App Notification for applicant (Requirement 1 & 3: Applicant scoped notification)
    try:
        create_notification(
            college_id=app_record.college_id,
            title=f"Application Status Updated: {app_record.application_number}",
            message=f"Your application status for {app_record.course} has been updated to {new_status}.",
            category='admissions',
            recipient_email=app_record.email,
            application_number=app_record.application_number,
            link='/students-corner'
        )
    except Exception as notif_err:
        app.logger.error(f"In-app notification dispatch error on status update: {notif_err}")

    # Trigger status update email notification to student (isolated so SMTP errors never roll back status)
    try:
        college = get_default_college()
        send_applicant_status_update_email(app_record, old_status, new_status, college)
    except Exception as mail_err:
        app.logger.error(f"Status update email notification error: {mail_err}")
    
    flash(f"📋 Application '{app_record.application_number}' status updated to {new_status}.", "success")
    return redirect(url_for('admin'))

# ==============================================================================
# STEP 11B: COURSE & CURRICULUM MANAGEMENT ADMIN ROUTES
# ==============================================================================

@app.route('/admin/course/add', methods=['POST'])
@module_admin_required('academics')
def admin_add_course():
    code = request.form.get('code', '').strip().upper()
    name = request.form.get('name', '').strip()
    level = request.form.get('level', '').strip()
    duration = request.form.get('duration', '').strip()
    affiliation = request.form.get('affiliation', '').strip()
    overview = request.form.get('overview', '').strip()
    eligibility = request.form.get('eligibility', '').strip()

    if not code or not name or not level or not duration or not overview:
        flash("⚠️ Validation Error: Course Code, Name, Level, Duration, and Overview are required.", "warning")
        return redirect(url_for('admin'))

    # Duplicate course code check within tenant
    existing = models.Course.query.filter_by(college_id=current_user.college_id, code=code).first()
    if existing:
        flash(f"⚠️ Validation Error: Course with code '{code}' already exists for this college.", "warning")
        return redirect(url_for('admin'))

    try:
        new_course = models.Course(
            college_id=current_user.college_id,
            code=code,
            name=name,
            level=level,
            duration=duration,
            affiliation=affiliation or 'Bengaluru City University',
            overview=overview,
            eligibility=eligibility or '10+2 / Pre-University Examination passed in any stream.'
        )
        db.session.add(new_course)
        db.session.commit()
        flash(f"🎓 Course '{code} - {name}' created successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding course: {str(e)}", "warning")

    return redirect(url_for('admin'))


@app.route('/admin/course/delete/<int:course_id>', methods=['POST'])
@module_admin_required('academics')
def admin_delete_course(course_id):
    course = models.Course.query.get_or_404(course_id)
    if not check_tenant_ownership(course.college_id):
        abort(403)

    try:
        course_code = course.code
        db.session.delete(course)
        db.session.commit()
        flash(f"🗑️ Course '{course_code}' and all related outcomes, semesters, and subjects deleted.", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting course: {str(e)}", "warning")

    return redirect(url_for('admin'))


@app.route('/admin/course/outcome/add/<int:course_id>', methods=['POST'])
@module_admin_required('academics')
def admin_add_course_outcome(course_id):
    course = models.Course.query.get_or_404(course_id)
    if not check_tenant_ownership(course.college_id):
        abort(403)

    content = request.form.get('content', '').strip()
    if not content:
        flash("⚠️ Validation Error: Outcome content cannot be empty.", "warning")
        return redirect(url_for('admin'))

    try:
        max_order = db.session.query(db.func.max(models.CourseOutcome.display_order)).filter_by(course_id=course_id).scalar() or 0
        new_outcome = models.CourseOutcome(
            course_id=course_id,
            content=content,
            display_order=max_order + 1
        )
        db.session.add(new_outcome)
        db.session.commit()
        flash(f"✅ Learning outcome added to course '{course.code}'.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding outcome: {str(e)}", "warning")

    return redirect(url_for('admin'))


@app.route('/admin/course/outcome/delete/<int:outcome_id>', methods=['POST'])
@module_admin_required('academics')
def admin_delete_course_outcome(outcome_id):
    outcome = models.CourseOutcome.query.get_or_404(outcome_id)
    if not check_tenant_ownership(outcome.course.college_id):
        abort(403)

    try:
        db.session.delete(outcome)
        db.session.commit()
        flash("🗑️ Learning outcome removed.", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting outcome: {str(e)}", "warning")

    return redirect(url_for('admin'))


@app.route('/admin/course/semester/add/<int:course_id>', methods=['POST'])
@module_admin_required('academics')
def admin_add_course_semester(course_id):
    course = models.Course.query.get_or_404(course_id)
    if not check_tenant_ownership(course.college_id):
        abort(403)

    semester_name = request.form.get('semester_name', '').strip()
    if not semester_name:
        flash("⚠️ Validation Error: Semester name is required (e.g. 'Semester I').", "warning")
        return redirect(url_for('admin'))

    try:
        max_order = db.session.query(db.func.max(models.CurriculumSemester.display_order)).filter_by(course_id=course_id).scalar() or 0
        new_sem = models.CurriculumSemester(
            course_id=course_id,
            semester_name=semester_name,
            display_order=max_order + 1
        )
        db.session.add(new_sem)
        db.session.commit()
        flash(f"✅ Semester '{semester_name}' added to course '{course.code}'.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding semester: {str(e)}", "warning")

    return redirect(url_for('admin'))


@app.route('/admin/course/subject/add/<int:semester_id>', methods=['POST'])
@module_admin_required('academics')
def admin_add_course_subject(semester_id):
    sem = models.CurriculumSemester.query.get_or_404(semester_id)
    if not check_tenant_ownership(sem.course.college_id):
        abort(403)

    subject_name = request.form.get('subject_name', '').strip()
    if not subject_name:
        flash("⚠️ Validation Error: Subject name is required.", "warning")
        return redirect(url_for('admin'))

    try:
        max_order = db.session.query(db.func.max(models.CurriculumSubject.display_order)).filter_by(semester_id=semester_id).scalar() or 0
        new_subject = models.CurriculumSubject(
            semester_id=semester_id,
            subject_name=subject_name,
            display_order=max_order + 1
        )
        db.session.add(new_subject)
        db.session.commit()
        flash(f"📚 Subject '{subject_name}' added to '{sem.semester_name}'.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding subject: {str(e)}", "warning")

    return redirect(url_for('admin'))

# ==============================================================================
# STEP 11C: CAMPUS EVENTS & ACADEMIC CALENDAR MANAGEMENT ADMIN ROUTES
# ==============================================================================

@app.route('/admin/event/add', methods=['POST'])
@module_admin_required('news_events')
def admin_add_event():
    title = request.form.get('title', '').strip()
    date_display = request.form.get('date_display', '').strip()
    day = request.form.get('day', '').strip()
    month = request.form.get('month', '').strip().upper()
    category = request.form.get('category', '').strip()
    description = request.form.get('description', '').strip()
    icon = request.form.get('icon', '').strip() or 'fa-solid fa-calendar'

    if not title or not date_display or not day or not month or not category or not description:
        flash("⚠️ Validation Error: Event Title, Date, Day, Month, Category, and Description are required.", "warning")
        return redirect(url_for('admin'))

    try:
        max_order = db.session.query(db.func.max(models.CampusEvent.display_order)).filter_by(college_id=current_user.college_id).scalar() or 0
        new_event = models.CampusEvent(
            college_id=current_user.college_id,
            title=title,
            date_display=date_display,
            day=day,
            month=month,
            category=category,
            description=description,
            icon=icon,
            display_order=max_order + 1
        )
        db.session.add(new_event)
        db.session.commit()
        flash(f"🎉 Event '{title}' added successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding event: {str(e)}", "warning")

    return redirect(url_for('admin'))


@app.route('/admin/event/edit/<int:event_id>', methods=['POST'])
@module_admin_required('news_events')
def admin_edit_event(event_id):
    event_item = models.CampusEvent.query.get_or_404(event_id)
    if not check_tenant_ownership(event_item.college_id):
        abort(403)

    title = request.form.get('title', '').strip()
    date_display = request.form.get('date_display', '').strip()
    day = request.form.get('day', '').strip()
    month = request.form.get('month', '').strip().upper()
    category = request.form.get('category', '').strip()
    description = request.form.get('description', '').strip()
    icon = request.form.get('icon', '').strip()

    if not title or not date_display or not day or not month or not category or not description:
        flash("⚠️ Validation Error: Event fields cannot be empty.", "warning")
        return redirect(url_for('admin'))

    try:
        event_item.title = title
        event_item.date_display = date_display
        event_item.day = day
        event_item.month = month
        event_item.category = category
        event_item.description = description
        if icon:
            event_item.icon = icon
        db.session.commit()
        flash(f"✏️ Event '{title}' updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating event: {str(e)}", "warning")

    return redirect(url_for('admin'))


@app.route('/admin/event/delete/<int:event_id>', methods=['POST'])
@module_admin_required('news_events')
def admin_delete_event(event_id):
    event_item = models.CampusEvent.query.get_or_404(event_id)
    if not check_tenant_ownership(event_item.college_id):
        abort(403)

    try:
        title = event_item.title
        db.session.delete(event_item)
        db.session.commit()
        flash(f"🗑️ Campus event '{title}' deleted.", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting event: {str(e)}", "warning")

    return redirect(url_for('admin'))


@app.route('/admin/calendar/add', methods=['POST'])
@module_admin_required('news_events')
def admin_add_calendar_item():
    event_name = request.form.get('event_name', '').strip()
    date_display = request.form.get('date_display', '').strip()
    event_type = request.form.get('event_type', '').strip().lower()

    if not event_name or not date_display or not event_type:
        flash("⚠️ Validation Error: Event Name, Date, and Type are required.", "warning")
        return redirect(url_for('admin'))

    try:
        max_order = db.session.query(db.func.max(models.AcademicCalendarItem.display_order)).filter_by(college_id=current_user.college_id).scalar() or 0
        new_item = models.AcademicCalendarItem(
            college_id=current_user.college_id,
            event_name=event_name,
            date_display=date_display,
            event_type=event_type,
            display_order=max_order + 1
        )
        db.session.add(new_item)
        db.session.commit()
        flash(f"📅 Academic calendar item '{event_name}' added successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding calendar item: {str(e)}", "warning")

    return redirect(url_for('admin'))


@app.route('/admin/calendar/edit/<int:item_id>', methods=['POST'])
@module_admin_required('news_events')
def admin_edit_calendar_item(item_id):
    cal_item = models.AcademicCalendarItem.query.get_or_404(item_id)
    if not check_tenant_ownership(cal_item.college_id):
        abort(403)

    event_name = request.form.get('event_name', '').strip()
    date_display = request.form.get('date_display', '').strip()
    event_type = request.form.get('event_type', '').strip().lower()

    if not event_name or not date_display or not event_type:
        flash("⚠️ Validation Error: Calendar item fields cannot be empty.", "warning")
        return redirect(url_for('admin'))

    try:
        cal_item.event_name = event_name
        cal_item.date_display = date_display
        cal_item.event_type = event_type
        db.session.commit()
        flash(f"✏️ Calendar item '{event_name}' updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating calendar item: {str(e)}", "warning")

    return redirect(url_for('admin'))


@app.route('/admin/calendar/delete/<int:item_id>', methods=['POST'])
@module_admin_required('news_events')
def admin_delete_calendar_item(item_id):
    cal_item = models.AcademicCalendarItem.query.get_or_404(item_id)
    if not check_tenant_ownership(cal_item.college_id):
        abort(403)

    try:
        event_name = cal_item.event_name
        db.session.delete(cal_item)
        db.session.commit()
        flash(f"🗑️ Calendar item '{event_name}' deleted.", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting calendar item: {str(e)}", "warning")

    return redirect(url_for('admin'))

# ==============================================================================
# STEP 11D: QUESTION PAPER MANAGEMENT ADMIN ROUTES
# ==============================================================================

@app.route('/admin/question-paper/add', methods=['POST'])
@app.route('/admin/question-paper/upload', methods=['POST'])
@module_admin_required('question_papers')
def admin_upload_question_paper():
    course_id = request.form.get('course_id', type=int)
    year = request.form.get('year', '').strip()
    semester = request.form.get('semester', '').strip()
    subject = request.form.get('subject', '').strip()
    file_storage = request.files.get('file')

    if not course_id or not year or not semester or not subject:
        flash("⚠️ Validation Error: Course, Year, Semester, and Subject are all required.", "warning")
        return redirect(url_for('admin'))

    # Validate selected course belongs to current tenant
    course = models.Course.query.filter_by(id=course_id, college_id=current_user.college_id).first()
    if not course:
        flash("⚠️ Validation Error: Selected course does not belong to your institution.", "warning")
        return redirect(url_for('admin'))

    # Semester validation: 4 semesters for Master's (PG), 6 semesters for Bachelor's (UG)
    is_pg = 'PG' in course.level or 'Postgraduate' in course.level or 'Master' in course.name
    valid_sems = ['1st Sem', '2nd Sem', '3rd Sem', '4th Sem'] if is_pg else ['1st Sem', '2nd Sem', '3rd Sem', '4th Sem', '5th Sem', '6th Sem']
    
    if semester not in valid_sems:
        max_sem_text = "4 semesters (1st Sem to 4th Sem)" if is_pg else "6 semesters (1st Sem to 6th Sem)"
        prog_type = "Master's (PG)" if is_pg else "Bachelor's (UG)"
        flash(f"⚠️ Validation Error: '{course.code}' is a {prog_type} program and only supports {max_sem_text}.", "warning")
        return redirect(url_for('admin'))

    # Strict PDF-only validation
    if not file_storage or not file_storage.filename:
        flash("⚠️ Validation Error: An authentic PDF file (.pdf) is strictly required.", "warning")
        return redirect(url_for('admin'))

    success, filename_or_err = validate_and_save_pdf(file_storage, current_user.college_id)
    if not success:
        flash(f"⚠️ PDF Upload Error: {filename_or_err}. Only valid PDF documents are allowed.", "warning")
        return redirect(url_for('admin'))

    qp = models.QuestionPaper(
        course_id=course.id,
        year=year,
        semester=semester,
        subject=subject,
        filename=filename_or_err
    )
    db.session.add(qp)
    db.session.commit()

    flash(f"📄 Question Paper '{subject}' ({semester}) uploaded successfully in PDF format!", "success")
    return redirect(url_for('admin'))

@app.route('/admin/question-paper/delete/<int:paper_id>', methods=['POST'])
@module_admin_required('question_papers')
def admin_delete_question_paper(paper_id):
    qp = models.QuestionPaper.query.join(models.Course).filter(
        models.QuestionPaper.id == paper_id,
        models.Course.college_id == current_user.college_id
    ).first_or_404()

    # Path-safe deletion
    safe_delete_tenant_file(current_user.college_id, 'question_papers', qp.filename)

    db.session.delete(qp)
    db.session.commit()
    flash(f"🗑️ Question paper '{qp.subject}' deleted successfully.", "info")
    return redirect(url_for('admin'))

# SUPER ADMIN MODULE CONTROL MATRIX PORTAL (Controlled strictly by Super Admin)
@app.route('/superadmin')
@platform_super_admin_required
def superadmin():
    college = get_default_college()
    gallery_items = models.GalleryItem.query.filter_by(
        college_id=college.id
    ).order_by(models.GalleryItem.created_at.desc(), models.GalleryItem.id.desc()).all()
    return render_template('superadmin.html', title="Super Admin - Module Control Matrix", modules=get_current_modules(), gallery_items=gallery_items)

@app.route('/superadmin/toggle-enable/<module_key>', methods=['POST'])
@platform_super_admin_required
def toggle_enable(module_key):
    try:
        college = get_default_college()
        cfg = models.ModuleConfig.query.filter_by(college_id=college.id, module_key=module_key).first()
        if cfg:
            cfg.enabled = not cfg.enabled
            db.session.commit()
            status_str = "ENABLED ✅" if cfg.enabled else "DISABLED ⚡"
            msg_type = "success" if cfg.enabled else "warning"
            flash(f"Notification: Module '{cfg.name}' site-wide view is now {status_str}!", msg_type)
        else:
            flash(f"Module key '{module_key}' not found in database.", "warning")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating module status: {str(e)}", "warning")
    return redirect(url_for('superadmin'))

@app.route('/superadmin/toggle-admin/<module_key>', methods=['POST'])
@platform_super_admin_required
def toggle_admin(module_key):
    try:
        college = get_default_college()
        cfg = models.ModuleConfig.query.filter_by(college_id=college.id, module_key=module_key).first()
        if cfg:
            cfg.admin_access = not cfg.admin_access
            db.session.commit()
            status_str = "GRANTED 🔑" if cfg.admin_access else "REVOKED 🔒"
            msg_type = "success" if cfg.admin_access else "info"
            flash(f"Notification: College Admin access for '{cfg.name}' has been {status_str}!", msg_type)
        else:
            flash(f"Module key '{module_key}' not found in database.", "warning")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating admin access: {str(e)}", "warning")
    return redirect(url_for('superadmin'))


# ==============================================================================
# SECURE CMS INSTITUTION SETTINGS ROUTES (Requirement 6)
# ==============================================================================

@app.route('/admin/settings/update', methods=['POST'])
@college_admin_required
def admin_update_settings():
    if not current_user.college_id:
        return abort(403)

    college_setting = models.CollegeSetting.query.filter_by(college_id=current_user.college_id).first()
    if not college_setting:
        college_setting = models.CollegeSetting(college_id=current_user.college_id)
        db.session.add(college_setting)

    college_name = request.form.get('college_name', '').strip()
    tagline = request.form.get('tagline', '').strip()
    email_info = request.form.get('email_info', '').strip().lower()
    phone_primary = request.form.get('phone_primary', '').strip()
    address = request.form.get('address', '').strip()
    accreditation = request.form.get('accreditation', '').strip()
    hero_title = request.form.get('hero_title', '').strip()
    hero_subtitle = request.form.get('hero_subtitle', '').strip()

    # Validation rules (Requirement 6)
    if not college_name or len(college_name) > 150:
        flash("⚠️ Validation Error: College Name is required and must be under 150 characters.", "warning")
        return redirect(url_for('admin'))

    if email_info and ('@' not in email_info or '.' not in email_info or len(email_info) > 120):
        flash("⚠️ Validation Error: Please provide a valid email address.", "warning")
        return redirect(url_for('admin'))

    if len(tagline) > 250 or len(hero_title) > 150 or len(hero_subtitle) > 300 or len(address) > 300:
        flash("⚠️ Validation Error: Text length exceeds maximum permitted limit.", "warning")
        return redirect(url_for('admin'))

    college_setting.college_name = college_name
    college_setting.tagline = tagline
    college_setting.email_info = email_info
    college_setting.phone_primary = phone_primary
    college_setting.address = address
    college_setting.accreditation = accreditation
    college_setting.hero_title = hero_title
    college_setting.hero_subtitle = hero_subtitle

    db.session.commit()
    flash("🏫 Institution settings and branding updated successfully!", "success")
    return redirect(url_for('admin'))

# ==============================================================================
# SECURE CMS ANNOUNCEMENT ROUTES (Requirement 7)
# ==============================================================================

@app.route('/admin/announcement/add', methods=['POST'])
@module_admin_required('news_events')
def admin_add_announcement():
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'Announcements').strip()
    content = request.form.get('content', '').strip()

    if not title or not content:
        flash("⚠️ Validation Error: Title and Content are required.", "warning")
        return redirect(url_for('admin'))

    new_post = models.ForumPost(
        college_id=current_user.college_id,
        author=getattr(current_user, 'email', 'College Administration Desk'),
        title=title,
        category=category,
        content=content
    )
    db.session.add(new_post)
    db.session.commit()

    flash(f"📰 Announcement '{title}' published successfully!", "success")
    return redirect(url_for('admin'))

@app.route('/admin/announcement/delete/<int:post_id>', methods=['POST'])
@module_admin_required('news_events')
def admin_delete_announcement(post_id):
    post = models.ForumPost.query.filter_by(id=post_id, college_id=current_user.college_id).first_or_404()
    title = post.title
    db.session.delete(post)
    db.session.commit()
    flash(f"🗑️ Announcement '{title}' deleted.", "info")
    return redirect(url_for('admin'))

# Download route for past question papers (PDF format strictly enforced)
@app.route('/download-paper/<filename>')
def download_paper(filename):
    modules = get_current_modules()
    if not modules.get('question_papers', {}).get('enabled', True):
        flash("⚠️ Examination Question Paper Repository is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))

    college = get_default_college()
    paper = models.QuestionPaper.query.join(models.Course).filter(
        models.Course.college_id == college.id,
        models.QuestionPaper.filename == filename
    ).first_or_404()

    clean_download_name = f"{paper.course.code}_{paper.semester.replace(' ', '_')}_{paper.subject.replace(' ', '_')}_{paper.year}.pdf"
    tenant_file = get_tenant_upload_dir(college.id, 'question_papers') / os.path.basename(paper.filename)
    if tenant_file.exists() and tenant_file.is_file():
        return send_file(tenant_file, mimetype='application/pdf', download_name=clean_download_name, as_attachment=True)

    # Generate authentic university examination PDF on the fly
    pdf_buffer = generate_question_paper_pdf(paper, college)
    return send_file(pdf_buffer, mimetype='application/pdf', download_name=clean_download_name, as_attachment=True)

# ==============================================================================
# SECURE CMS FACULTY & STAFF DIRECTORY ROUTES (Step 3A)
# ==============================================================================

@app.route('/admin/faculty/add', methods=['POST'])
@module_admin_required('academics')
def admin_add_faculty_member():
    name = request.form.get('name', '').strip()
    designation = request.form.get('designation', '').strip()
    department_code = request.form.get('department_code', 'BCA').strip().upper()
    qualification = request.form.get('qualification', '').strip()
    specialization = request.form.get('specialization', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    photo_file = request.files.get('photo_file')

    if not name or not designation or not department_code or not qualification or not email:
        flash("⚠️ Validation Error: Name, Designation, Department, Qualification, and Email are required.", "warning")
        return redirect(url_for('admin'))

    if '@' not in email or '.' not in email:
        flash("⚠️ Validation Error: Please enter a valid email address.", "warning")
        return redirect(url_for('admin'))

    saved_photo_name = None
    if photo_file and photo_file.filename:
        success, filename_or_err = validate_and_save_image(photo_file, current_user.college_id, 'faculty')
        if not success:
            flash(f"⚠️ Faculty Photo Error: {filename_or_err}", "warning")
            return redirect(url_for('admin'))
        saved_photo_name = filename_or_err

    max_order = db.session.query(db.func.max(models.FacultyMember.display_order)).filter_by(college_id=current_user.college_id).scalar() or 0
    faculty = models.FacultyMember(
        college_id=current_user.college_id,
        name=name,
        designation=designation,
        department_code=department_code,
        qualification=qualification,
        specialization=specialization,
        email=email,
        phone=phone,
        photo_url=saved_photo_name,
        display_order=max_order + 1,
        is_active=True
    )
    db.session.add(faculty)
    db.session.commit()

    flash(f"👨‍🏫 Faculty Profile '{name}' added successfully!", "success")
    return redirect(url_for('admin'))


@app.route('/admin/faculty/delete/<int:faculty_id>', methods=['POST'])
@module_admin_required('academics')
def admin_delete_faculty_member(faculty_id):
    faculty = models.FacultyMember.query.filter_by(id=faculty_id, college_id=current_user.college_id).first_or_404()
    
    if faculty.photo_url:
        safe_delete_tenant_file(current_user.college_id, 'faculty', faculty.photo_url)

    db.session.delete(faculty)
    db.session.commit()
    flash("🗑️ Faculty member deleted.", "info")
    return redirect(url_for('admin'))


# ==============================================================================
# SECURE CMS PLACEMENT DRIVES ROUTES (Step 3B)
# ==============================================================================

@app.route('/admin/placement-drive/add', methods=['POST'])
@module_admin_required('placements')
def admin_add_placement_drive():
    company_name = request.form.get('company_name', '').strip()
    role_offered = request.form.get('role_offered', '').strip()
    package_lpa = request.form.get('package_lpa', '').strip()
    eligibility_criteria = request.form.get('eligibility_criteria', '').strip()
    drive_date = request.form.get('drive_date', '').strip()
    application_deadline = request.form.get('application_deadline', '').strip()
    status = request.form.get('status', 'UPCOMING').strip().upper()
    contact_email = request.form.get('contact_email', '').strip().lower()
    logo_file = request.files.get('logo_file')

    if not company_name or not role_offered or not package_lpa or not eligibility_criteria or not drive_date:
        flash("⚠️ Validation Error: Company Name, Role, Package, Eligibility, and Drive Date are required.", "warning")
        return redirect(url_for('admin'))

    if status not in ['UPCOMING', 'ONGOING', 'COMPLETED', 'CANCELLED']:
        status = 'UPCOMING'

    saved_logo_name = None
    if logo_file and logo_file.filename:
        success, filename_or_err = validate_and_save_image(logo_file, current_user.college_id, 'placements')
        if not success:
            flash(f"⚠️ Recruiter Logo Error: {filename_or_err}", "warning")
            return redirect(url_for('admin'))
        saved_logo_name = filename_or_err

    drive = models.PlacementDrive(
        college_id=current_user.college_id,
        company_name=company_name,
        company_logo=saved_logo_name,
        role_offered=role_offered,
        package_lpa=package_lpa,
        eligibility_criteria=eligibility_criteria,
        drive_date=drive_date,
        application_deadline=application_deadline,
        status=status,
        contact_email=contact_email,
        is_active=True
    )
    db.session.add(drive)
    db.session.commit()

    flash(f"💼 Placement Drive for '{company_name}' created successfully!", "success")
    return redirect(url_for('admin'))


@app.route('/admin/placement-drive/delete/<int:drive_id>', methods=['POST'])
@module_admin_required('placements')
def admin_delete_placement_drive(drive_id):
    drive = models.PlacementDrive.query.filter_by(id=drive_id, college_id=current_user.college_id).first_or_404()
    
    if drive.company_logo:
        safe_delete_tenant_file(current_user.college_id, 'placements', drive.company_logo)

    db.session.delete(drive)
    db.session.commit()
    flash("🗑️ Placement drive entry deleted.", "info")
    return redirect(url_for('admin'))


@app.route('/ca')
@college_admin_required
def admin_shortcut():
    return redirect(url_for('admin'))

@app.route('/sa')
@platform_super_admin_required
def superadmin_shortcut():
    return redirect(url_for('superadmin'))

# ==============================================================================
# ADVANCED STUDENT SERVICES & DIGITAL CAMPUS ROUTES (Step 5)
# ==============================================================================

@app.route('/admission/provisional-letter/<app_number>')
@rate_limit(limit=20, period=300, scope='pdf_download', only_post=False)
def download_provisional_letter(app_number):
    app_record = models.AdmissionApplication.query.filter_by(application_number=app_number).first_or_404()

    # Status Restriction: Only VERIFIED or SEAT_LOCKED allowed
    if app_record.status not in ['VERIFIED', 'SEAT_LOCKED']:
        abort(403)

    # Access Control Security Check:
    # 1. Matching authenticated applicant session OR
    # 2. Authenticated authorized admin belonging to the same college
    is_authorized = False
    if current_user.is_authenticated and check_tenant_ownership(app_record.college_id):
        is_authorized = True
    elif 'applicant_access' in session:
        app_access = session['applicant_access']
        if (app_access.get('college_id') == app_record.college_id and
            app_access.get('application_number') == app_number and
            app_access.get('email', '').strip().lower() == app_record.email.strip().lower()):
            is_authorized = True

    if not is_authorized:
        abort(403)

    college = models.College.query.get_or_404(app_record.college_id)
    pdf_buffer = generate_provisional_admission_letter(app_record, college)
    filename = f"Provisional_Admission_Letter_{app_number}.pdf"
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )


@app.route('/students-corner/document-request', methods=['POST'])
@rate_limit(limit=10, period=3600, scope='document_request')
def submit_student_document_request():
    if 'applicant_access' not in session:
        flash("⚠️ Authentication required: Please log in to your Student Portal.", "warning")
        return redirect(url_for('students_corner'))

    app_access = session['applicant_access']
    document_type = request.form.get('document_type', '').strip()
    reason = request.form.get('reason', '').strip()

    if not document_type or not reason:
        flash("⚠️ Validation Error: Document type and reason are required.", "warning")
        return redirect(url_for('students_corner'))

    doc_req = models.StudentDocumentRequest(
        college_id=app_access['college_id'],
        application_number=app_access['application_number'],
        student_name=app_access['full_name'],
        email=app_access['email'],
        document_type=document_type,
        reason=reason,
        status='PENDING'
    )
    db.session.add(doc_req)
    db.session.commit()

    notify_college_admins(
        college_id=app_access['college_id'],
        title="New Document Request Submitted 📜",
        message=f"Student {app_access['full_name']} requested '{document_type}' for App #{app_access['application_number']}.",
        category="document_request",
        link="/admin"
    )

    flash(f"📜 Request for '{document_type}' submitted successfully! Track status in your Student Desk.", "success")
    return redirect(url_for('students_corner'))


@app.route('/admin/document-request/status/<int:req_id>', methods=['POST'])
@module_admin_required('admission')
def admin_update_document_request_status(req_id):
    req_item = models.StudentDocumentRequest.query.filter_by(id=req_id, college_id=current_user.college_id).first_or_404()
    
    new_status = request.form.get('status', '').strip().upper()
    admin_remarks = request.form.get('admin_remarks', '').strip()

    if new_status not in ['PENDING', 'PROCESSING', 'ISSUED', 'REJECTED']:
        flash("⚠️ Invalid document request status.", "warning")
        return redirect(url_for('admin'))

    req_item.status = new_status
    if admin_remarks:
        req_item.admin_remarks = admin_remarks
    db.session.commit()

    # Notify applicant if context matches
    create_notification(
        college_id=req_item.college_id,
        title=f"Document Request Update ({new_status}) 📜",
        message=f"Your request for '{req_item.document_type}' status is now '{new_status}'. Remarks: {admin_remarks or 'None'}",
        category="document_request",
        application_number=req_item.application_number,
        recipient_email=req_item.email,
        link="/students-corner"
    )

    flash(f"📜 Document request #{req_id} updated to '{new_status}'.", "success")
    return redirect(url_for('admin'))


@app.route('/events/register/<int:event_id>', methods=['POST'])
@rate_limit(limit=10, period=3600, scope='event_register')
def register_campus_event(event_id):
    college = get_default_college()
    event = models.CampusEvent.query.filter_by(id=event_id, college_id=college.id).first_or_404()

    name = request.form.get('participant_name', '').strip()
    email = request.form.get('participant_email', '').strip().lower()
    phone = request.form.get('participant_phone', '').strip()

    if not name or not email:
        flash("⚠️ Validation Error: Participant name and email are required.", "warning")
        return redirect(url_for('index'))

    # Duplicate Prevention
    existing = models.EventRegistration.query.filter_by(event_id=event.id, participant_email=email).first()
    if existing:
        flash(f"ℹ️ You are already registered for '{event.title}'. Pass Code: {existing.registration_code}", "info")
        return redirect(url_for('index'))

    reg_code = f"EVT-{uuid.uuid4().hex[:8].upper()}"

    registration = models.EventRegistration(
        college_id=college.id,
        event_id=event.id,
        participant_name=name,
        participant_email=email,
        participant_phone=phone,
        registration_code=reg_code,
        status='CONFIRMED'
    )
    db.session.add(registration)
    db.session.commit()

    flash(f"🎉 Successfully registered for '{event.title}'! Your Registration Pass Code is {reg_code}.", "success")
    return redirect(url_for('index'))


@app.route('/verify-event-registration/<registration_code>')
def verify_event_registration(registration_code):
    reg = models.EventRegistration.query.filter_by(registration_code=registration_code).first_or_404()
    event = models.CampusEvent.query.get_or_404(reg.event_id)
    college = models.College.query.get_or_404(reg.college_id)

    masked_email = reg.participant_email[:2] + "****@" + reg.participant_email.split('@')[-1] if '@' in reg.participant_email else reg.participant_email

    return render_template(
        'verify_receipt.html',
        receipt_type='Event Registration Pass',
        is_valid=True,
        record_id=reg.registration_code,
        college_name=college.name,
        details={
            'Event Title': event.title,
            'Event Date': event.date_display,
            'Participant Name': reg.participant_name,
            'Participant Email': masked_email,
            'Status': reg.status,
            'Registration Date': reg.created_at.strftime('%b %d, %Y %H:%M')
        }
    )

def provision_student_from_application(app_record, raw_password=None):
    """
    Safely provisions a Student account from an AdmissionApplication record.
    Prevents duplicate provisioning if a Student account already exists for this application.
    """
    if not app_record or not app_record.college_id:
        return None, None

    existing_by_app = models.Student.query.filter_by(
        college_id=app_record.college_id,
        admission_application_id=app_record.id
    ).first()
    if existing_by_app:
        return existing_by_app, None

    existing_by_email = models.Student.query.filter_by(
        college_id=app_record.college_id,
        email=app_record.email.strip().lower()
    ).first()
    if existing_by_email:
        return existing_by_email, None

    course_code = app_record.course.upper() if app_record.course else 'GEN'
    reg_number = f"REG2026-{course_code}-{app_record.id:04d}"
    generated_pass = raw_password or secrets.token_urlsafe(10)

    student = models.Student(
        college_id=app_record.college_id,
        register_number=reg_number,
        admission_application_id=app_record.id,
        full_name=app_record.full_name,
        email=app_record.email.strip().lower(),
        phone=app_record.phone,
        course_code=course_code,
        semester='Semester 1',
        section='A',
        status='ACTIVE'
    )
    student.set_password(generated_pass)
    db.session.add(student)
    db.session.commit()

    try:
        create_notification(
            college_id=app_record.college_id,
            title="Student Portal Account Provisioned 🎓",
            message=f"Welcome {app_record.full_name}! Your Official Student Account ({reg_number}) has been created.",
            category="admissions",
            recipient_email=app_record.email,
            application_number=app_record.application_number,
            link="/student/login"
        )
    except Exception as e:
        app.logger.error(f"Error dispatching student account creation notification: {e}")

    return student, generated_pass


# ==============================================================================
# POST-ADMISSION STUDENT AUTHENTICATION & PORTAL ROUTES (Phase 6 Step 1)
# ==============================================================================

@app.route('/student/login', methods=['GET', 'POST'])
@rate_limit(limit=5, period=60, scope='student_login')
def student_login():
    if session.get('student_access'):
        return redirect(url_for('student_dashboard'))

    college = get_default_college()

    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        password = request.form.get('password', '').strip()

        if not login_id or not password:
            flash("⚠️ Validation Error: Register Number/Email and Password are required.", "warning")
            return redirect(url_for('student_login'))

        student = models.Student.query.filter(
            (models.Student.college_id == college.id) &
            ((models.Student.email == login_id.lower()) | (models.Student.register_number == login_id.upper()))
        ).first()

        if not student or not student.check_password(password):
            flash("🔒 Authentication Failed: Invalid Register Number/Email or Password.", "warning")
            return redirect(url_for('student_login'))

        if student.status == 'SUSPENDED':
            flash("⚠️ Account Suspended: Please contact Registrar Office.", "warning")
            return abort(403)

        session['student_access'] = {
            'student_id': student.id,
            'college_id': student.college_id,
            'register_number': student.register_number,
            'email': student.email,
            'full_name': student.full_name
        }
        session.modified = True

        flash(f"🎓 Welcome back, {student.full_name}! (Reg No: {student.register_number})", "success")
        return redirect(url_for('student_dashboard'))

    return render_template('login.html', is_student_login=True, title="Student Portal Login - Seshadripuram College")


@app.route('/student/logout')
def student_logout():
    session.pop('student_access', None)
    session.modified = True
    flash("👋 Logged out of Student Portal successfully.", "info")
    return redirect(url_for('student_login'))


@app.route('/student/dashboard')
def student_dashboard():
    student_sess = session.get('student_access')
    if not student_sess or not isinstance(student_sess, dict):
        flash("🔒 Authentication required: Please log in to your Student Portal.", "warning")
        return redirect(url_for('student_login'))

    student_id = student_sess.get('student_id')
    student = db.session.get(models.Student, student_id)
    if not student:
        session.pop('student_access', None)
        return redirect(url_for('student_login'))

    if student.status == 'SUSPENDED':
        session.pop('student_access', None)
        flash("⚠️ Account Suspended: Please contact Registrar Office.", "warning")
        return abort(403)

    college = get_default_college()
    course = models.Course.query.filter_by(college_id=college.id, code=student.course_code).first()

    subjects = []
    if course:
        sem_record = models.CurriculumSemester.query.filter_by(course_id=course.id, semester_name=student.semester).first()
        if sem_record:
            subjects = models.CurriculumSubject.query.options(
                joinedload(models.CurriculumSubject.faculty),
                selectinload(models.CurriculumSubject.materials)
            ).filter_by(semester_id=sem_record.id).order_by(models.CurriculumSubject.display_order).all()

    question_papers = []
    if course:
        question_papers = models.QuestionPaper.query.filter_by(course_id=course.id).order_by(models.QuestionPaper.id.desc()).all()

    exam_schedules = []
    if course:
        exam_schedules = models.ExamTimetableItem.query.filter_by(
            college_id=college.id,
            course_id=course.id,
            semester_name=student.semester
        ).order_by(models.ExamTimetableItem.exam_date).all()

    doc_requests = models.StudentDocumentRequest.query.filter_by(
        college_id=college.id,
        email=student.email
    ).order_by(models.StudentDocumentRequest.created_at.desc()).all()

    event_passes = models.EventRegistration.query.filter_by(
        college_id=college.id,
        participant_email=student.email
    ).order_by(models.EventRegistration.created_at.desc()).all()

    return render_template(
        'student_dashboard.html',
        student=student,
        course=course,
        subjects=subjects,
        question_papers=question_papers,
        exam_schedules=exam_schedules,
        doc_requests=doc_requests,
        event_passes=event_passes
    )


@app.route('/student/profile/update', methods=['POST'])
def student_profile_update():
    student_sess = session.get('student_access')
    if not student_sess or not isinstance(student_sess, dict):
        return abort(403)

    student = db.session.get(models.Student, student_sess.get('student_id'))
    if not student or student.status == 'SUSPENDED':
        return abort(403)

    phone = request.form.get('phone', '').strip()
    if phone:
        student.phone = phone
        db.session.commit()
        flash("✅ Contact details updated successfully!", "success")
    
    return redirect(url_for('student_dashboard'))


# ==============================================================================
# ACADEMIC MANAGEMENT & CURRICULUM ROUTES (Phase 6 Step 2)
# ==============================================================================

@app.route('/admin/subject/add', methods=['POST'])
@module_admin_required('academics')
def admin_add_subject():
    sem_id = request.form.get('semester_id')
    sub_code = request.form.get('subject_code', '').strip().upper()
    sub_name = request.form.get('subject_name', '').strip()
    credits = int(request.form.get('credits', 4))
    syllabus_summary = request.form.get('syllabus_summary', '').strip()
    faculty_id = request.form.get('faculty_id')

    if not sem_id or not sub_name:
        flash("⚠️ Validation Error: Semester ID and Subject Name are required.", "warning")
        return redirect(url_for('admin'))

    sem_record = models.CurriculumSemester.query.get_or_404(sem_id)
    course = models.Course.query.get_or_404(sem_record.course_id)
    if not check_tenant_ownership(course.college_id):
        return abort(403)

    subject = models.CurriculumSubject(
        semester_id=sem_record.id,
        subject_code=sub_code if sub_code else None,
        subject_name=sub_name,
        credits=credits,
        syllabus_summary=syllabus_summary if syllabus_summary else None,
        faculty_id=int(faculty_id) if (faculty_id and faculty_id.isdigit()) else None
    )
    db.session.add(subject)
    db.session.commit()

    flash(f"📚 Subject '{sub_name}' added to {course.code} {sem_record.semester_name}.", "success")
    return redirect(url_for('admin'))


@app.route('/admin/subject/delete/<int:sub_id>', methods=['POST'])
@module_admin_required('academics')
def admin_delete_subject(sub_id):
    sub = models.CurriculumSubject.query.get_or_404(sub_id)
    sem_record = models.CurriculumSemester.query.get_or_404(sub.semester_id)
    course = models.Course.query.get_or_404(sem_record.course_id)
    if not check_tenant_ownership(course.college_id):
        return abort(403)

    db.session.delete(sub)
    db.session.commit()
    flash(f"🗑️ Subject '{sub.subject_name}' deleted.", "info")
    return redirect(url_for('admin'))


@app.route('/admin/study-material/upload', methods=['POST'])
@module_admin_required('academics')
def admin_upload_study_material():
    sub_id = request.form.get('subject_id')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    material_type = request.form.get('material_type', 'NOTES').strip().upper()
    file = request.files.get('file')

    if not sub_id or not title or not file:
        flash("⚠️ Validation Error: Subject ID, Title, and File are required.", "warning")
        return redirect(url_for('admin'))

    sub = models.CurriculumSubject.query.get_or_404(sub_id)
    sem_record = models.CurriculumSemester.query.get_or_404(sub.semester_id)
    course = models.Course.query.get_or_404(sem_record.course_id)
    if not check_tenant_ownership(course.college_id):
        return abort(403)

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'png', 'jpg', 'txt']:
        flash("⚠️ Security Error: Unsupported file format.", "warning")
        return redirect(url_for('admin'))

    upload_dir = get_tenant_upload_dir(course.college_id, 'study_materials')
    safe_filename = f"{uuid.uuid4().hex[:12]}_{secure_filename(file.filename)}"
    file_path = upload_dir / safe_filename
    file.save(str(file_path))

    material = models.SubjectMaterial(
        subject_id=sub.id,
        title=title,
        description=description,
        material_type=material_type,
        file_url=safe_filename
    )
    db.session.add(material)
    db.session.commit()

    flash(f"📄 Study material '{title}' uploaded for {sub.subject_name}.", "success")
    return redirect(url_for('admin'))


@app.route('/admin/study-material/delete/<int:mat_id>', methods=['POST'])
@module_admin_required('academics')
def admin_delete_study_material(mat_id):
    mat = models.SubjectMaterial.query.get_or_404(mat_id)
    sub = models.CurriculumSubject.query.get_or_404(mat.subject_id)
    sem_record = models.CurriculumSemester.query.get_or_404(sub.semester_id)
    course = models.Course.query.get_or_404(sem_record.course_id)
    if not check_tenant_ownership(course.college_id):
        return abort(403)

    upload_dir = get_tenant_upload_dir(course.college_id, 'study_materials')
    file_path = upload_dir / mat.file_url
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            app.logger.error(f"Error unlinking study material: {e}")

    db.session.delete(mat)
    db.session.commit()
    flash(f"🗑️ Study material '{mat.title}' deleted.", "info")
    return redirect(url_for('admin'))


@app.route('/admin/exam-timetable/add', methods=['POST'])
@module_admin_required('academics')
def admin_add_exam_timetable():
    course_id = request.form.get('course_id')
    sem_name = request.form.get('semester_name', '').strip()
    sub_name = request.form.get('subject_name', '').strip()
    exam_date = request.form.get('exam_date', '').strip()
    exam_time = request.form.get('exam_time', '').strip()
    hall_number = request.form.get('hall_number', '').strip()

    if not course_id or not sem_name or not sub_name or not exam_date:
        flash("⚠️ Validation Error: Course, Semester, Subject, and Exam Date are required.", "warning")
        return redirect(url_for('admin'))

    course = models.Course.query.get_or_404(course_id)
    if not check_tenant_ownership(course.college_id):
        return abort(403)

    item = models.ExamTimetableItem(
        college_id=course.college_id,
        course_id=course.id,
        semester_name=sem_name,
        subject_name=sub_name,
        exam_date=exam_date,
        exam_time=exam_time,
        hall_number=hall_number
    )
    db.session.add(item)
    db.session.commit()

    flash(f"📅 Exam schedule added for '{sub_name}' ({exam_date}).", "success")
    return redirect(url_for('admin'))


@app.route('/admin/exam-timetable/delete/<int:item_id>', methods=['POST'])
@module_admin_required('academics')
def admin_delete_exam_timetable(item_id):
    item = models.ExamTimetableItem.query.get_or_404(item_id)
    if not check_tenant_ownership(item.college_id):
        return abort(403)

    db.session.delete(item)
    db.session.commit()
    flash("🗑️ Exam timetable schedule item deleted.", "info")
    return redirect(url_for('admin'))


with app.app_context():
    db.create_all()
    try:
        db.session.execute(db.text("ALTER TABLE forum_posts ADD COLUMN likes_count INTEGER DEFAULT 0"))
        db.session.commit()
    except Exception:
        db.session.rollback()

    for col_def in [
        "ALTER TABLE curriculum_subjects ADD COLUMN subject_code VARCHAR(30)",
        "ALTER TABLE curriculum_subjects ADD COLUMN credits INTEGER DEFAULT 4",
        "ALTER TABLE curriculum_subjects ADD COLUMN syllabus_summary TEXT",
        "ALTER TABLE curriculum_subjects ADD COLUMN syllabus_pdf_url VARCHAR(255)",
        "ALTER TABLE curriculum_subjects ADD COLUMN faculty_id INTEGER REFERENCES faculty_members(id)"
    ]:
        try:
            db.session.execute(db.text(col_def))
            db.session.commit()
        except Exception:
            db.session.rollback()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
