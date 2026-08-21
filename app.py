import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, migrate, login_manager
import models
from seed import seed_default_college, get_default_college, get_database_module_matrix, DEFAULT_MODULE_MATRIX
from authz import platform_super_admin_required, college_admin_required, module_admin_required, check_tenant_ownership

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'seshadripuram_college_secret_key')

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

# Academic Courses Database Dictionary
COURSES_DATA = {
    'bca': {
        'code': 'BCA',
        'name': 'Bachelor of Computer Applications',
        'level': 'Undergraduate (UG)',
        'duration': '3 Years (6 Semesters)',
        'affiliation': 'Bengaluru City University',
        'overview': 'The BCA program at Seshadripuram College is designed to build a strong foundation in computer science, software development, cloud computing, AI, and full-stack web engineering. Equipped with 100+ high-end computer labs.',
        'eligibility': '10+2 / Pre-University Examination passed in any stream with a minimum of 40% aggregate marks.',
        'outcomes': [
            'Proficiency in Java, Python, C++, Web Technologies, and Database Systems.',
            'Practical experience through industry projects and cloud labs.',
            '100% placement assistance with top tech recruiters like Infosys, Wipro, TCS, and Accenture.'
        ],
        'curriculum': [
            {'sem': 'Semester I', 'subjects': ['Programming in C', 'Computer Architecture', 'Discrete Mathematics', 'Digital Electronics']},
            {'sem': 'Semester II', 'subjects': ['Data Structures using C++', 'Operating Systems', 'Numerical Analysis', 'Python Programming']},
            {'sem': 'Semester III', 'subjects': ['Java Programming', 'Database Management Systems (DBMS)', 'Software Engineering', 'Computer Networks']},
            {'sem': 'Semester IV', 'subjects': ['Web Technologies (HTML/CSS/JS/Node)', 'Design & Analysis of Algorithms', 'Cloud Computing Basics', 'Python for Data Science']},
            {'sem': 'Semester V', 'subjects': ['Full Stack Web Development', 'Artificial Intelligence & ML', 'Cyber Security & Cryptography', 'Software Testing']},
            {'sem': 'Semester VI', 'subjects': ['Major Industry Project', 'Mobile App Development (Android/Flutter)', 'Advanced Java & Spring Boot', 'Ethics in IT']}
        ],
        'question_papers': [
            {'year': '2025', 'sem': 'Sem 5', 'subject': 'Full Stack Web Development', 'file': 'BCA_Sem5_FullStack_2025.pdf'},
            {'year': '2025', 'sem': 'Sem 5', 'subject': 'Artificial Intelligence', 'file': 'BCA_Sem5_AI_2025.pdf'},
            {'year': '2024', 'sem': 'Sem 4', 'subject': 'Database Management Systems', 'file': 'BCA_Sem4_DBMS_2024.pdf'},
            {'year': '2024', 'sem': 'Sem 3', 'subject': 'Java Programming', 'file': 'BCA_Sem3_Java_2024.pdf'},
            {'year': '2023', 'sem': 'Sem 2', 'subject': 'Data Structures', 'file': 'BCA_Sem2_DataStructures_2023.pdf'}
        ]
    },
    'mca': {
        'code': 'MCA',
        'name': 'Master of Computer Applications',
        'level': 'Postgraduate (PG)',
        'duration': '2 Years (4 Semesters)',
        'affiliation': 'Bengaluru City University',
        'overview': 'Advanced postgraduate program specializing in Cloud Microservices, Artificial Intelligence, Big Data Analytics, and Software Architecture.',
        'eligibility': 'BCA / B.Sc (CS/IT) / Graduate degree with Mathematics at PUC or Graduation level with min 50% aggregate.',
        'outcomes': [
            'Architectural mastery in Cloud Microservices & Distributed Systems.',
            'High-level positions like Software Development Engineer, Data Scientist, DevOps Engineer.'
        ],
        'curriculum': [
            {'sem': 'Semester I', 'subjects': ['Advanced Data Structures', 'Cloud Microservices Architecture', 'Enterprise Java', 'Applied Statistics']},
            {'sem': 'Semester II', 'subjects': ['Machine Learning & Deep Learning', 'Advanced Web Architectures', 'DevOps & CI/CD', 'Mobile Engineering']},
            {'sem': 'Semester III', 'subjects': ['Big Data Engineering', 'Cybersecurity Engineering', 'Full Stack Frameworks', 'Research Methodology']},
            {'sem': 'Semester IV', 'subjects': ['Postgraduate Thesis / Industry Internship', 'Publication & Project Defense']}
        ],
        'question_papers': [
            {'year': '2025', 'sem': 'Sem 3', 'subject': 'Cloud Microservices', 'file': 'MCA_Sem3_Cloud_2025.pdf'},
            {'year': '2025', 'sem': 'Sem 2', 'subject': 'Machine Learning', 'file': 'MCA_Sem2_ML_2025.pdf'},
            {'year': '2024', 'sem': 'Sem 1', 'subject': 'Advanced Data Structures', 'file': 'MCA_Sem1_ADS_2024.pdf'}
        ]
    },
    'bba': {
        'code': 'BBA',
        'name': 'Bachelor of Business Administration',
        'level': 'Undergraduate (UG)',
        'duration': '3 Years (6 Semesters)',
        'affiliation': 'Bengaluru City University',
        'overview': 'Empowering future business leaders with comprehensive skills in corporate management, marketing strategies, financial analytics, and entrepreneurship.',
        'eligibility': '10+2 / PUC passed in any discipline with minimum 40% aggregate.',
        'outcomes': [
            'Business leadership and strategic decision-making capabilities.',
            'Hands-on exposure to corporate internships, startup incubators, and business fests.'
        ],
        'curriculum': [
            {'sem': 'Semester I', 'subjects': ['Principles of Management', 'Financial Accounting', 'Business Economics', 'Corporate Communication']},
            {'sem': 'Semester II', 'subjects': ['Organizational Behavior', 'Cost Accounting', 'Business Law', 'Marketing Management']},
            {'sem': 'Semester III', 'subjects': ['Human Resource Management', 'Corporate Environment', 'Business Statistics', 'Financial Management']},
            {'sem': 'Semester IV', 'subjects': ['Entrepreneurship Development', 'Supply Chain Management', 'Services Management', 'Research Methods']},
            {'sem': 'Semester V', 'subjects': ['Elective I (Finance/Marketing/HR)', 'Elective II', 'Strategic Management', 'Income Tax']},
            {'sem': 'Semester VI', 'subjects': ['International Business', 'Corporate Governance', 'Project Report & Viva', 'Business Analytics']}
        ],
        'question_papers': [
            {'year': '2025', 'sem': 'Sem 5', 'subject': 'Financial Management', 'file': 'BBA_Sem5_Finance_2025.pdf'},
            {'year': '2024', 'sem': 'Sem 4', 'subject': 'Entrepreneurship', 'file': 'BBA_Sem4_Ent_2024.pdf'},
            {'year': '2024', 'sem': 'Sem 2', 'subject': 'Marketing Management', 'file': 'BBA_Sem2_Marketing_2024.pdf'}
        ]
    },
    'bcom': {
        'code': 'BCom',
        'name': 'Bachelor of Commerce',
        'level': 'Undergraduate (UG)',
        'duration': '3 Years (6 Semesters)',
        'affiliation': 'Bengaluru City University',
        'overview': 'Our flagship Commerce program focusing on Advanced Accounting, Taxation, Banking, Financial Auditing, and Corporate Finance.',
        'eligibility': '10+2 / PUC in Commerce or Science stream.',
        'outcomes': [
            'Deep expertise in Tally Prime, GST, Corporate Taxation, and Auditing.',
            'Seamless foundation for CA, CS, CMA, and MBA pursuits.'
        ],
        'curriculum': [
            {'sem': 'Semester I', 'subjects': ['Financial Accounting I', 'Business Dynamics', 'Indian Financial System', 'Market Behavior']},
            {'sem': 'Semester II', 'subjects': ['Advanced Accounting', 'Banking Law & Operations', 'Quantitative Analysis', 'Corporate Ethics']},
            {'sem': 'Semester III', 'subjects': ['Corporate Accounting I', 'Financial Markets', 'Direct Taxes', 'Business Regulations']},
            {'sem': 'Semester IV', 'subjects': ['Cost Accounting', 'E-Commerce', 'Indirect Taxes (GST)', 'Stock Market Operations']},
            {'sem': 'Semester V', 'subjects': ['Income Tax II', 'Auditing & Assurance', 'Management Accounting', 'Elective Paper 1']},
            {'sem': 'Semester VI', 'subjects': ['Business Taxation', 'International Financial Reporting', 'GST Practice', 'Project Work']}
        ],
        'question_papers': [
            {'year': '2025', 'sem': 'Sem 5', 'subject': 'Auditing & Assurance', 'file': 'BCom_Sem5_Auditing_2025.pdf'},
            {'year': '2024', 'sem': 'Sem 4', 'subject': 'Cost Accounting', 'file': 'BCom_Sem4_Cost_2024.pdf'}
        ]
    },
    'mba': {
        'code': 'MBA',
        'name': 'Master of Business Administration',
        'level': 'Postgraduate (PG)',
        'duration': '2 Years (4 Semesters)',
        'affiliation': 'Bengaluru City University',
        'overview': 'Executive business leadership & strategic management degree offering dual specializations in Finance, Marketing, HR, and Business Analytics.',
        'eligibility': 'Graduation in any stream with min 50% aggregate and valid PGCET/MAT/KMAT score.',
        'outcomes': ['Executive positions in Fortune 500 companies, startup leadership, and management consulting.'],
        'curriculum': [
            {'sem': 'Semester I', 'subjects': ['Management & Organizational Behavior', 'Managerial Economics', 'Accounting for Managers', 'Marketing Management']},
            {'sem': 'Semester II', 'subjects': ['Financial Management', 'Human Resource Management', 'Business Research Methods', 'Operations Management']},
            {'sem': 'Semester III', 'subjects': ['Specialization Electives (Dual)', 'Corporate Strategy', 'Summer Internship Project']},
            {'sem': 'Semester IV', 'subjects': ['International Business Dynamics', 'Strategic Leadership', 'Dissertation & Defense']}
        ],
        'question_papers': [
            {'year': '2025', 'sem': 'Sem 3', 'subject': 'Corporate Strategy', 'file': 'MBA_Sem3_Strategy_2025.pdf'},
            {'year': '2024', 'sem': 'Sem 2', 'subject': 'Financial Management', 'file': 'MBA_Sem2_FM_2024.pdf'}
        ]
    },
    'mcom': {
        'code': 'MCom',
        'name': 'Master of Commerce',
        'level': 'Postgraduate (PG)',
        'duration': '2 Years (4 Semesters)',
        'affiliation': 'Bengaluru City University',
        'overview': 'Advanced corporate finance, taxation, and quantitative methods degree designed for research scholars, financial analysts, and corporate consultants.',
        'eligibility': 'BCom / BBA degree with min 50% aggregate marks.',
        'outcomes': ['Expertise in Financial Risk Analysis, Corporate Valuation, and Academic Research.'],
        'curriculum': [
            {'sem': 'Semester I', 'subjects': ['Advanced Financial Management', 'Monetary System', 'Macroeconomics', 'Statistical Methods']},
            {'sem': 'Semester II', 'subjects': ['Corporate Tax Planning', 'Accounting Theory', 'Business Research', 'Financial Institutions']},
            {'sem': 'Semester III', 'subjects': ['Security Analysis & Portfolio Management', 'International Finance', 'Elective Papers']},
            {'sem': 'Semester IV', 'subjects': ['Derivatives Markets', 'Corporate Restructuring', 'Master Dissertation']}
        ],
        'question_papers': [
            {'year': '2025', 'sem': 'Sem 3', 'subject': 'Security Analysis', 'file': 'MCom_Sem3_SAPM_2025.pdf'}
        ]
    },
    'ba': {
        'code': 'BA',
        'name': 'Bachelor of Arts',
        'level': 'Undergraduate (UG)',
        'duration': '3 Years (6 Semesters)',
        'affiliation': 'Bengaluru City University',
        'overview': 'Fostering critical thinking, journalism, psychology, political science, and literature studies to develop empathetic society leaders.',
        'eligibility': '10+2 / PUC passed in any stream.',
        'outcomes': ['Careers in Media, Journalism, Public Administration, Civil Services, and Social Impact.'],
        'curriculum': [
            {'sem': 'Semester I', 'subjects': ['English Literature', 'Introduction to Psychology', 'Political Theory', 'Sociology Fundamentals']},
            {'sem': 'Semester II', 'subjects': ['Journalism & Mass Media', 'Developmental Psychology', 'Indian Constitution', 'Social Movements']}
        ],
        'question_papers': [
            {'year': '2025', 'sem': 'Sem 2', 'subject': 'Journalism & Mass Media', 'file': 'BA_Sem2_Journalism_2025.pdf'}
        ]
    },
    'bsc': {
        'code': 'BSc',
        'name': 'Bachelor of Science',
        'level': 'Undergraduate (UG)',
        'duration': '3 Years (6 Semesters)',
        'affiliation': 'Bengaluru City University',
        'overview': 'Postgraduate scientific research & data analytics degree focusing on Mathematics, Physics, Statistics, and Computer Science.',
        'eligibility': '10+2 / PUC in Science stream.',
        'outcomes': ['Scientific research careers, data analyst positions, and postgraduate specialization.'],
        'curriculum': [
            {'sem': 'Semester I', 'subjects': ['Calculus & Linear Algebra', 'Mechanics & Waves', 'Probability Theory', 'C Programming Lab']},
            {'sem': 'Semester II', 'subjects': ['Differential Equations', 'Electromagnetism', 'Statistical Inference', 'Data Structures Lab']}
        ],
        'question_papers': [
            {'year': '2025', 'sem': 'Sem 2', 'subject': 'Calculus & Linear Algebra', 'file': 'BSc_Sem2_Maths_2025.pdf'}
        ]
    },
    'msc': {
        'code': 'MSc',
        'name': 'Master of Science',
        'level': 'Postgraduate (PG)',
        'duration': '2 Years (4 Semesters)',
        'affiliation': 'Bengaluru City University',
        'overview': 'Advanced research program in Computer Science, Data Analytics, and Applied Mathematics with state-of-the-art laboratory infrastructure.',
        'eligibility': 'BSc in relevant discipline with min 50% aggregate.',
        'outcomes': ['High-impact research, PhD progression, R&D engineering roles in tech firms.'],
        'curriculum': [
            {'sem': 'Semester I', 'subjects': ['Advanced Algorithms', 'Quantum Computing Concepts', 'Mathematical Modeling']},
            {'sem': 'Semester II', 'subjects': ['Neural Networks', 'Distributed Database Systems', 'Scientific Python Lab']}
        ],
        'question_papers': [
            {'year': '2025', 'sem': 'Sem 1', 'subject': 'Advanced Algorithms', 'file': 'MSc_Sem1_Algo_2025.pdf'}
        ]
    }
}

# Forum Mock Data
FORUM_POSTS = [
    {
        'id': 1,
        'author': 'Rahul Sharma (BCA 5th Sem)',
        'title': 'Best resources for preparing for Campus Placements in Cloud & Full Stack?',
        'category': 'Placements & Careers',
        'content': 'Hey everyone! As the 2026-27 placement drive is approaching, what topics are top companies like Infosys and TCS focusing on most for BCA students?',
        'replies': 8,
        'date': '2 hours ago',
        'likes': 14
    },
    {
        'id': 2,
        'author': 'Prof. Ananya Rao (Dept of CS)',
        'title': 'Hackathon 2026 Registration Announcement - TechVanguard',
        'category': 'Events & Fests',
        'content': 'Seshadripuram College is organizing the annual state-level hackathon "TechVanguard 2026" on Sept 15th. Cash prizes up to ₹1,00,000! Register at the CS Dept office.',
        'replies': 15,
        'date': 'Yesterday',
        'likes': 42
    },
    {
        'id': 3,
        'author': 'Priya Nair (MBA 3rd Sem)',
        'title': 'Discussion on Bangalore Startup Summit & College Incubator Grants',
        'category': 'Entrepreneurship',
        'content': 'Our college incubator cell is accepting pitch decks for student startups till August end. Seed grant up to ₹2 Lakhs available for selected teams.',
        'replies': 5,
        'date': '3 days ago',
        'likes': 29
    },
    {
        'id': 4,
        'author': 'Sneha Gupta (Alumni - BCA 2022)',
        'title': 'My Journey from Seshadripuram to Google - Tips for Juniors',
        'category': 'Alumni Network',
        'content': 'After graduating from BCA in 2022, I joined TCS and later cracked Google interview. Happy to mentor current students. DM me for guidance!',
        'replies': 22,
        'date': '1 week ago',
        'likes': 67
    },
    {
        'id': 5,
        'author': 'Vikram Reddy (Alumni - MBA 2020)',
        'title': 'Alumni Meetup Bangalore - August 2026',
        'category': 'Alumni Network',
        'content': 'Organizing an alumni get-together at Cubbon Park on Aug 25th. All batches welcome! RSVP in comments.',
        'replies': 11,
        'date': '4 days ago',
        'likes': 38
    }
]

# Upcoming Events Data
UPCOMING_EVENTS = [
    {
        'title': 'TechVanguard Hackathon 2026',
        'date': 'Sept 15, 2026',
        'day': '15',
        'month': 'SEP',
        'category': 'Technology',
        'description': 'State-level hackathon with cash prizes up to \u20b91,00,000. Open to all departments.',
        'icon': 'fa-solid fa-code'
    },
    {
        'title': 'Annual Sports Meet',
        'date': 'Oct 5-7, 2026',
        'day': '05',
        'month': 'OCT',
        'category': 'Sports',
        'description': 'Inter-departmental athletics, cricket, volleyball, and badminton championships.',
        'icon': 'fa-solid fa-trophy'
    },
    {
        'title': 'Cultural Fest - Utsav 2026',
        'date': 'Nov 20-22, 2026',
        'day': '20',
        'month': 'NOV',
        'category': 'Cultural',
        'description': 'Three-day mega cultural festival featuring dance, music, drama, and fashion shows.',
        'icon': 'fa-solid fa-music'
    },
    {
        'title': 'Campus Placement Drive',
        'date': 'Dec 10, 2026',
        'day': '10',
        'month': 'DEC',
        'category': 'Placements',
        'description': 'Top recruiters including Infosys, TCS, Wipro, and Accenture on campus.',
        'icon': 'fa-solid fa-briefcase'
    }
]

# Academic Calendar Data
ACADEMIC_CALENDAR = [
    {'date': 'Aug 1, 2026', 'event': 'Odd Semester Classes Begin', 'type': 'academic'},
    {'date': 'Aug 15, 2026', 'event': 'Independence Day Celebration', 'type': 'holiday'},
    {'date': 'Sept 15, 2026', 'event': 'TechVanguard Hackathon', 'type': 'event'},
    {'date': 'Oct 2, 2026', 'event': 'Gandhi Jayanti Holiday', 'type': 'holiday'},
    {'date': 'Oct 15-25, 2026', 'event': 'Internal Assessment Tests (IAT-1)', 'type': 'exam'},
    {'date': 'Nov 1, 2026', 'event': 'Kannada Rajyotsava', 'type': 'holiday'},
    {'date': 'Nov 20-22, 2026', 'event': 'Cultural Fest - Utsav 2026', 'type': 'event'},
    {'date': 'Dec 1-10, 2026', 'event': 'Internal Assessment Tests (IAT-2)', 'type': 'exam'},
    {'date': 'Dec 15, 2026', 'event': 'Last Working Day (Odd Sem)', 'type': 'academic'},
    {'date': 'Jan 5-20, 2027', 'event': 'University End Semester Examinations', 'type': 'exam'},
    {'date': 'Feb 1, 2027', 'event': 'Even Semester Classes Begin', 'type': 'academic'},
    {'date': 'Mar 15, 2027', 'event': 'Annual Convocation Ceremony', 'type': 'event'}
]

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
    try:
        return get_default_college()
    except Exception:
        return None

@app.context_processor
def inject_college_context():
    college = get_current_college()
    settings = college.settings if (college and hasattr(college, 'settings')) else None
    return dict(
        modules=get_current_modules(),
        college=college,
        settings=settings
    )

@app.route('/')
def index():
    return render_template('index.html', title="Seshadripuram College - Shaping Futures, Building Leaders", events=UPCOMING_EVENTS, academic_calendar=ACADEMIC_CALENDAR)

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
            status='UNDER_REVIEW'
        )

        db.session.add(new_app)
        db.session.commit()

        flash(f"🎉 Thank you {full_name}! Your application for {course} has been submitted successfully. Application ID: {new_app.application_number}.", "success")
        return redirect(url_for('apply'))

    return render_template('apply.html', title="Online Application Form 2026-27")

@app.route('/departments')
def departments():
    modules = get_current_modules()
    if not modules['departments']['enabled']:
        flash("⚠️ Departments module is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))
    return render_template('departments.html', title="Academic Departments - Seshadripuram College")

@app.route('/course/<course_code>')
def course_detail(course_code):
    modules = get_current_modules()
    if not modules['academics']['enabled']:
        flash("⚠️ Course details are currently offline site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))
    code_lower = course_code.lower()
    course = COURSES_DATA.get(code_lower)
    if not course:
        course = COURSES_DATA['bca']
    return render_template('course_detail.html', course=course, title=f"{course['code']} - {course['name']}")

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

@app.route('/forum', methods=['GET', 'POST'])
def forum():
    modules = get_current_modules()
    if not modules['forum']['enabled']:
        flash("⚠️ Community Forum is currently disabled site-wide by Super Admin.", "warning")
        return redirect(url_for('index'))
    if request.method == 'POST':
        author = request.form.get('author')
        title = request.form.get('title')
        category = request.form.get('category')
        content = request.form.get('content')
        new_post = {
            'id': len(FORUM_POSTS) + 1,
            'author': author if author else 'College Administrator',
            'title': title,
            'category': category,
            'content': content,
            'replies': 0,
            'date': 'Just now',
            'likes': 1
        }
        FORUM_POSTS.insert(0, new_post)
        flash("🎉 Discussion topic has been published successfully to Campus Forum!", "success")
        ref = request.referrer
        if ref and ('superadmin' in ref or 'admin' in ref):
            return redirect(ref)
        return redirect(url_for('forum'))
    return render_template('forum.html', posts=FORUM_POSTS, title="Campus Community Forum - Seshadripuram College")

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
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
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
    
    if current_user.college_id:
        if modules.get('admission', {}).get('admin_access'):
            applications = models.AdmissionApplication.query.filter_by(
                college_id=current_user.college_id
            ).order_by(models.AdmissionApplication.created_at.desc()).all()
            
        if modules.get('gallery', {}).get('admin_access'):
            gallery_items = models.GalleryItem.query.filter_by(
                college_id=current_user.college_id
            ).order_by(models.GalleryItem.created_at.desc(), models.GalleryItem.id.desc()).all()

    return render_template(
        'admin.html',
        title="College Admin Portal",
        modules=modules,
        gallery_items=gallery_items,
        applications=applications
    )

@app.route('/admin/admission/status/<int:app_id>', methods=['POST'])
@module_admin_required('admission')
def update_application_status(app_id):
    new_status = request.form.get('status', '').strip().upper()
    if new_status not in ['UNDER_REVIEW', 'VERIFIED', 'REJECTED']:
        flash("⚠️ Invalid application status specified.", "warning")
        return redirect(url_for('admin'))
        
    app_record = models.AdmissionApplication.query.get_or_404(app_id)
    
    # Tenant ownership security check
    if not check_tenant_ownership(app_record.college_id):
        abort(403)
        
    app_record.status = new_status
    db.session.commit()
    flash(f"📋 Application '{app_record.application_number}' status updated to {new_status}.", "success")
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
    return jsonify({
        'status': 'success',
        'message': f'Downloading exam question paper sample: {filename}',
        'filename': filename
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
