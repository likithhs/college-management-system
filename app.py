import os
import secrets
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort, g, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.orm import joinedload, selectinload
from extensions import db, migrate, login_manager
import models
from seed import seed_default_college, get_default_college, get_database_module_matrix, DEFAULT_MODULE_MATRIX
from authz import platform_super_admin_required, college_admin_required, module_admin_required, check_tenant_ownership

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'seshadripuram_college_secret_key')

# Production Session & Cookie Hardening
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('HTTPS', 'false').lower() == 'true'

@app.errorhandler(403)
def forbidden_error(e):
    return render_template('403.html', title="403 Forbidden - Access Denied"), 403

# Database Configuration (SQLite local, environment variable override for PostgreSQL readiness)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///college.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return models.User.query.get(int(user_id))

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

        flash(f"🎉 Thank you {full_name}! Your application for {course} has been submitted successfully. Application ID: {new_app.application_number}.", "success")
        return redirect(url_for('apply'))

    return render_template('apply.html', title="Online Application Form 2026-27")

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
    ).filter_by(college_id=college.id, code=course_code.upper()).first_or_404()
    return render_template('course_detail.html', course=course, title=f"{course.code} - {course.name}")

@app.route('/facilities')
def facilities():
    modules = get_current_modules()
    if not modules['facilities']['enabled']:
        flash("⚠️ Facilities module is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))
    return render_template('facilities.html', title="Campus Infrastructure & Facilities - Seshadripuram College")

@app.route('/placements')
def placements():
    modules = get_current_modules()
    if not modules['placements']['enabled']:
        flash("⚠️ Placements module is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))
    return render_template('placements.html', title="Placements & Career Cell - Seshadripuram College")

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
    
    if not title:
        flash("⚠️ Validation Error: Image title is required.", "warning")
        return redirect(url_for('admin'))

    if category not in GALLERY_FALLBACK_MAP:
        flash("⚠️ Validation Error: Invalid gallery category selected.", "warning")
        return redirect(url_for('admin'))

    if image_url and not (image_url.startswith('http://') or image_url.startswith('https://')):
        flash("⚠️ Validation Error: Image URL must start with http:// or https://", "warning")
        return redirect(url_for('admin'))

    fallback = GALLERY_FALLBACK_MAP[category]
    
    new_item = models.GalleryItem(
        college_id=current_user.college_id,
        title=title,
        category=category,
        category_label=fallback['category_label'],
        description=description if description else 'New photo uploaded to college archives.',
        icon=fallback['icon'],
        gradient=fallback['gradient'],
        image_url=image_url
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
        
    db.session.delete(target)
    db.session.commit()
    
    flash(f"🗑️ Photo '{target.title}' removed from Campus Gallery.", "info")
    
    ref = request.referrer
    if ref and ('superadmin' in ref or 'admin' in ref or 'gallery' in ref):
        return redirect(ref)
    return redirect(url_for('gallery'))

@app.route('/students-corner')
def students_corner():
    modules = get_current_modules()
    if not modules['students_corner']['enabled']:
        flash("⚠️ Students Corner is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))
    return render_template('students_corner.html', title="Students Corner, Clubs & Examination - Seshadripuram College")

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
    posts = models.ForumPost.query.filter_by(
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

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        flash(f"✉️ Thank you {name}! Your message has been sent to Seshadripuram College Admin Office.", "success")
        return redirect(url_for('contact'))
    return render_template('contact.html', title="Contact Us - Seshadripuram College")

# AUTHENTICATION & LOGIN ROUTES
@app.route('/login', methods=['GET', 'POST'])
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

    if current_user.college_id:
        if modules.get('admission', {}).get('admin_access'):
            applications = models.AdmissionApplication.query.filter_by(
                college_id=current_user.college_id
            ).order_by(models.AdmissionApplication.created_at.desc()).all()
            
        if modules.get('gallery', {}).get('admin_access'):
            gallery_items = models.GalleryItem.query.filter_by(
                college_id=current_user.college_id
            ).order_by(models.GalleryItem.created_at.desc(), models.GalleryItem.id.desc()).all()

        if modules.get('forum', {}).get('admin_access'):
            forum_posts = models.ForumPost.query.filter_by(
                college_id=current_user.college_id
            ).order_by(models.ForumPost.created_at.desc(), models.ForumPost.id.desc()).all()

        if modules.get('academics', {}).get('admin_access'):
            courses = models.Course.query.filter_by(
                college_id=current_user.college_id
            ).order_by(models.Course.code).all()
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
        academic_calendar_items=academic_calendar_items
    )

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
    
    if new_status == current_status:
        flash(f"ℹ️ Application '{app_record.application_number}' is already in {current_status} status.", "info")
        return redirect(url_for('admin'))
        
    allowed_next = ALLOWED_ADMISSION_TRANSITIONS.get(current_status, set())
    
    if new_status not in allowed_next:
        flash(f"⚠️ Validation Error: Illegal status transition from {current_status} to {new_status}.", "warning")
        return redirect(url_for('admin'))
        
    app_record.status = new_status
    db.session.commit()
    
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
@module_admin_required('academics')
def admin_add_question_paper():
    course_id = request.form.get('course_id', type=int)
    year = request.form.get('year', '').strip()
    semester = request.form.get('semester', '').strip()
    subject = request.form.get('subject', '').strip()
    filename = request.form.get('filename', '').strip()

    if not course_id or not year or not semester or not subject or not filename:
        flash("⚠️ Validation Error: Course, Year, Semester, Subject, and Filename are required.", "warning")
        return redirect(url_for('admin'))

    course = models.Course.query.get_or_404(course_id)

    # Tenant ownership security check (verifies target course belongs to active admin's college)
    if not check_tenant_ownership(course.college_id):
        abort(403)

    clean_filename = secure_filename(filename)
    if not clean_filename or not clean_filename.lower().endswith('.pdf'):
        flash("⚠️ Validation Error: Question paper filename must be a valid .pdf file.", "warning")
        return redirect(url_for('admin'))

    try:
        new_paper = models.QuestionPaper(
            course_id=course_id,
            year=year,
            semester=semester,
            subject=subject,
            filename=clean_filename
        )
        db.session.add(new_paper)
        db.session.commit()
        flash(f"📄 Past Question Paper '{clean_filename}' added to course '{course.code}'.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding question paper: {str(e)}", "warning")

    return redirect(url_for('admin'))


@app.route('/admin/question-paper/delete/<int:paper_id>', methods=['POST'])
@module_admin_required('academics')
def admin_delete_question_paper(paper_id):
    paper = models.QuestionPaper.query.get_or_404(paper_id)

    # Tenant ownership security check via relationship (paper -> course -> college_id)
    if not check_tenant_ownership(paper.course.college_id):
        abort(403)

    try:
        filename = paper.filename
        db.session.delete(paper)
        db.session.commit()
        flash(f"🗑️ Question paper entry '{filename}' deleted.", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting question paper: {str(e)}", "warning")

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

# Download route simulation for past question papers
@app.route('/download-paper/<filename>')
def download_paper(filename):
    college = get_default_college()
    paper = models.QuestionPaper.query.join(models.Course).filter(
        models.Course.college_id == college.id,
        models.QuestionPaper.filename == filename
    ).first_or_404()
    
    return jsonify({
        'status': 'success',
        'message': f'Downloading exam question paper sample: {paper.filename}',
        'filename': paper.filename
    })

@app.route('/ca')
@college_admin_required
def admin_shortcut():
    return redirect(url_for('admin'))

@app.route('/sa')
@platform_super_admin_required
def superadmin_shortcut():
    return redirect(url_for('superadmin'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
