import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = 'seshadripuram_college_secret_key'

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
    }
]

# Module Control Matrix Data (Controlled strictly by Super Admin)
MODULE_CONTROL_MATRIX = {
    'home': {'name': 'Home', 'enabled': True, 'admin_access': True},
    'about': {'name': 'About Us', 'enabled': True, 'admin_access': True},
    'academics': {'name': 'Academics & Syllabus', 'enabled': True, 'admin_access': True},
    'admission': {'name': 'Admission', 'enabled': True, 'admin_access': True},
    'departments': {'name': 'Departments', 'enabled': True, 'admin_access': True},
    'facilities': {'name': 'Facilities', 'enabled': True, 'admin_access': True},
    'students_corner': {'name': 'Students Corner', 'enabled': True, 'admin_access': True},
    'gallery': {'name': 'Gallery', 'enabled': True, 'admin_access': True},
    'placements': {'name': 'Placements', 'enabled': True, 'admin_access': True},
    'forum': {'name': 'Community Forum', 'enabled': True, 'admin_access': True},
    'news_events': {'name': 'News & Events', 'enabled': True, 'admin_access': True}
}

@app.context_processor
def inject_modules():
    return dict(modules=MODULE_CONTROL_MATRIX)

@app.route('/')
def index():
    return render_template('index.html', title="Seshadripuram College - Shaping Futures, Building Leaders")

@app.route('/about')
def about():
    if not MODULE_CONTROL_MATRIX['about']['enabled']:
        flash("About Us module is currently disabled by Super Admin.", "warning")
        return redirect(url_for('index'))
    return render_template('about.html', title="About Us - Seshadripuram College")

@app.route('/admission')
def admission():
    if not MODULE_CONTROL_MATRIX['admission']['enabled']:
        flash("Admission module is currently disabled by Super Admin.", "warning")
        return redirect(url_for('index'))
    return render_template('admission.html', title="Admissions 2026-27 - Seshadripuram College")

@app.route('/apply', methods=['GET', 'POST'])
def apply():
    if not MODULE_CONTROL_MATRIX['admission']['enabled']:
        flash("Online Applications are currently closed by Super Admin.", "warning")
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('full_name')
        course = request.form.get('course')
        phone = request.form.get('phone')
        email = request.form.get('email')
        flash(f"Thank you {name}! Your application for {course} has been submitted successfully. Application ID: SC2026-{os.urandom(2).hex().upper()}.", "success")
        return redirect(url_for('apply'))
    return render_template('apply.html', title="Online Application Form 2026-27")

@app.route('/departments')
def departments():
    if not MODULE_CONTROL_MATRIX['departments']['enabled']:
        flash("Departments module is currently disabled by Super Admin.", "warning")
        return redirect(url_for('index'))
    return render_template('departments.html', title="Academic Departments - Seshadripuram College")

@app.route('/course/<course_code>')
def course_detail(course_code):
    if not MODULE_CONTROL_MATRIX['academics']['enabled']:
        flash("Course details are currently offline by Super Admin.", "warning")
        return redirect(url_for('index'))
    code_lower = course_code.lower()
    course = COURSES_DATA.get(code_lower)
    if not course:
        course = COURSES_DATA['bca']
    return render_template('course_detail.html', course=course, title=f"{course['code']} - {course['name']}")

@app.route('/facilities')
def facilities():
    if not MODULE_CONTROL_MATRIX['facilities']['enabled']:
        flash("Facilities module is currently disabled by Super Admin.", "warning")
        return redirect(url_for('index'))
    return render_template('facilities.html', title="Campus Infrastructure & Facilities - Seshadripuram College")

@app.route('/placements')
def placements():
    if not MODULE_CONTROL_MATRIX['placements']['enabled']:
        flash("Placements module is currently disabled by Super Admin.", "warning")
        return redirect(url_for('index'))
    return render_template('placements.html', title="Placements & Career Cell - Seshadripuram College")

@app.route('/gallery')
def gallery():
    if not MODULE_CONTROL_MATRIX['gallery']['enabled']:
        flash("Gallery module is currently disabled by Super Admin.", "warning")
        return redirect(url_for('index'))
    return render_template('gallery.html', title="Campus Photo & Video Gallery - Seshadripuram College")

@app.route('/students-corner')
def students_corner():
    if not MODULE_CONTROL_MATRIX['students_corner']['enabled']:
        flash("Students Corner is currently disabled by Super Admin.", "warning")
        return redirect(url_for('index'))
    return render_template('students_corner.html', title="Students Corner, Clubs & Examination - Seshadripuram College")

@app.route('/forum', methods=['GET', 'POST'])
def forum():
    if not MODULE_CONTROL_MATRIX['forum']['enabled']:
        flash("Community Forum is currently disabled by Super Admin.", "warning")
        return redirect(url_for('index'))
    if request.method == 'POST':
        author = request.form.get('author')
        title = request.form.get('title')
        category = request.form.get('category')
        content = request.form.get('content')
        new_post = {
            'id': len(FORUM_POSTS) + 1,
            'author': author if author else 'Anonymous Student',
            'title': title,
            'category': category,
            'content': content,
            'replies': 0,
            'date': 'Just now',
            'likes': 1
        }
        FORUM_POSTS.insert(0, new_post)
        flash("Your discussion topic has been published successfully!", "success")
        return redirect(url_for('forum'))
    return render_template('forum.html', posts=FORUM_POSTS, title="Campus Community Forum - Seshadripuram College")

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        flash(f"Thank you {name}! Your message has been sent to Seshadripuram College Admin Office. We will get back to you shortly.", "success")
        return redirect(url_for('contact'))
    return render_template('contact.html', title="Contact Us - Seshadripuram College")

@app.route('/login')
def login():
    return render_template('login.html', title="Student & Faculty Portal Login")

@app.route('/admin')
def admin():
    return render_template('admin.html', title="College Admin Portal", modules=MODULE_CONTROL_MATRIX)

# SUPER ADMIN MODULE CONTROL MATRIX PORTAL (Controlled strictly by Super Admin)
@app.route('/superadmin')
def superadmin():
    return render_template('superadmin.html', title="Super Admin - Module Control Matrix", modules=MODULE_CONTROL_MATRIX)

@app.route('/superadmin/toggle-enable/<module_key>', methods=['POST'])
def toggle_enable(module_key):
    if module_key in MODULE_CONTROL_MATRIX:
        MODULE_CONTROL_MATRIX[module_key]['enabled'] = not MODULE_CONTROL_MATRIX[module_key]['enabled']
        status_str = "ENABLED" if MODULE_CONTROL_MATRIX[module_key]['enabled'] else "DISABLED"
        flash(f"Module '{MODULE_CONTROL_MATRIX[module_key]['name']}' public view is now {status_str}.", "success")
    return redirect(url_for('superadmin'))

@app.route('/superadmin/toggle-admin/<module_key>', methods=['POST'])
def toggle_admin(module_key):
    if module_key in MODULE_CONTROL_MATRIX:
        MODULE_CONTROL_MATRIX[module_key]['admin_access'] = not MODULE_CONTROL_MATRIX[module_key]['admin_access']
        status_str = "GRANTED" if MODULE_CONTROL_MATRIX[module_key]['admin_access'] else "REVOKED"
        flash(f"College Admin access for '{MODULE_CONTROL_MATRIX[module_key]['name']}' has been {status_str}.", "success")
    return redirect(url_for('superadmin'))

# Download route simulation for past question papers
@app.route('/download-paper/<filename>')
def download_paper(filename):
    return jsonify({
        'status': 'success',
        'message': f'Downloading exam question paper sample: {filename}',
        'filename': filename
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)

