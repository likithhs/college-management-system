import os
from extensions import db
from models import College, CollegeSetting, ModuleConfig, User, GalleryItem, ForumPost, Course, CourseOutcome, CurriculumSemester, CurriculumSubject, QuestionPaper, CampusEvent, AcademicCalendarItem

DEFAULT_MODULE_MATRIX = {
    'home': {'name': 'Home', 'enabled': True, 'admin_access': True},
    'about': {'name': 'About Us', 'enabled': True, 'admin_access': True},
    'academics': {'name': 'Academics & Syllabus', 'enabled': True, 'admin_access': True},
    'question_papers': {'name': 'Exam Question Paper Repository', 'enabled': True, 'admin_access': False},
    'admission': {'name': 'Admission', 'enabled': True, 'admin_access': True},
    'departments': {'name': 'Departments', 'enabled': True, 'admin_access': True},
    'facilities': {'name': 'Facilities', 'enabled': True, 'admin_access': True},
    'students_corner': {'name': 'Students Corner', 'enabled': True, 'admin_access': True},
    'gallery': {'name': 'Gallery', 'enabled': True, 'admin_access': True},
    'placements': {'name': 'Placements', 'enabled': True, 'admin_access': True},
    'forum': {'name': 'Community Forum', 'enabled': True, 'admin_access': True},
    'news_events': {'name': 'News & Events', 'enabled': True, 'admin_access': True},
    'floating_sidebar': {'name': 'Floating Right-Corner Quick Buttons', 'enabled': True, 'admin_access': True}
}

DEFAULT_SEED_GALLERY_ITEMS = [
    {
        'title': 'TechVanguard Hackathon 2026',
        'category': 'tech',
        'category_label': 'Tech & Hackathons',
        'description': '24-hour coding marathon with over 500+ participants.',
        'icon': 'fa-solid fa-laptop-code',
        'gradient': 'from-blue-900 to-indigo-700',
        'image_url': ''
    },
    {
        'title': 'Annual Youth Fest Seshadri Utsav',
        'category': 'cultural',
        'category_label': 'Cultural Extravaganza',
        'description': 'Dance, music performance, and fashion show showcase.',
        'icon': 'fa-solid fa-guitar',
        'gradient': 'from-amber-600 to-rose-600',
        'image_url': ''
    },
    {
        'title': 'Inter-Collegiate Athletics Championship',
        'category': 'sports',
        'category_label': 'Sports Meet',
        'description': 'Seshadripuram sports teams winning gold medals.',
        'icon': 'fa-solid fa-trophy',
        'gradient': 'from-emerald-700 to-teal-600',
        'image_url': ''
    },
    {
        'title': '100+ Terminal Cloud Computing Lab',
        'category': 'campus',
        'category_label': 'Campus Infrastructure',
        'description': 'Students working in high-end software development environment.',
        'icon': 'fa-solid fa-building-columns',
        'gradient': 'from-slate-800 to-slate-900',
        'image_url': ''
    },
    {
        'title': 'Annual Convocation Day',
        'category': 'cultural',
        'category_label': 'Graduation',
        'description': 'Awarding university rank holders and graduating batches.',
        'icon': 'fa-solid fa-graduation-cap',
        'gradient': 'from-purple-800 to-indigo-900',
        'image_url': ''
    },
    {
        'title': 'Generative AI & Cloud Summit',
        'category': 'tech',
        'category_label': 'AI Workshop',
        'description': 'Industry tech experts speaking to computer science scholars.',
        'icon': 'fa-solid fa-robot',
        'gradient': 'from-blue-700 to-cyan-600',
        'image_url': ''
    }
]

DEFAULT_SEED_FORUM_POSTS = [
    {
        'author': 'Rahul Sharma (BCA 5th Sem)',
        'title': 'Best resources for preparing for Campus Placements in Cloud & Full Stack?',
        'category': 'Placements & Careers',
        'content': 'Hey everyone! As the 2026-27 placement drive is approaching, what topics are top companies like Infosys and TCS focusing on most for BCA students?',
        'replies': 8,
        'likes': 14
    },
    {
        'author': 'Prof. Ananya Rao (Dept of CS)',
        'title': 'Hackathon 2026 Registration Announcement - TechVanguard',
        'category': 'Events & Fests',
        'content': 'Seshadripuram College is organizing the annual state-level hackathon "TechVanguard 2026" on Sept 15th. Cash prizes up to ₹1,00,000! Register at the CS Dept office.',
        'replies': 15,
        'likes': 42
    },
    {
        'author': 'Priya Nair (MBA 3rd Sem)',
        'title': 'Discussion on Bangalore Startup Summit & College Incubator Grants',
        'category': 'Entrepreneurship',
        'content': 'Our college incubator cell is accepting pitch decks for student startups till August end. Seed grant up to ₹2 Lakhs available for selected teams.',
        'replies': 5,
        'likes': 29
    },
    {
        'author': 'Sneha Gupta (Alumni - BCA 2022)',
        'title': 'My Journey from Seshadripuram to Google - Tips for Juniors',
        'category': 'Alumni Network',
        'content': 'After graduating from BCA in 2022, I joined TCS and later cracked Google interview. Happy to mentor current students. DM me for guidance!',
        'replies': 22,
        'likes': 67
    },
    {
        'author': 'Vikram Reddy (Alumni - MBA 2020)',
        'title': 'Alumni Meetup Bangalore - August 2026',
        'category': 'Alumni Network',
        'content': 'Organizing an alumni get-together at Cubbon Park on Aug 25th. All batches welcome! RSVP in comments.',
        'replies': 11,
        'likes': 38
    }
]

def seed_default_users(college):
    """
    Idempotent seeding function for Platform Super Admin and College Admin accounts.
    """
    # 1. Seed Platform Super Admin
    super_admin_email = os.environ.get('SUPERADMIN_EMAIL', 'superadmin@spmcollege.ac.in')
    super_admin_pass = os.environ.get('SUPERADMIN_PASSWORD', 'SuperAdmin@123')
    
    super_admin = User.query.filter_by(email=super_admin_email).first()
    if not super_admin:
        super_admin = User(
            email=super_admin_email,
            role='PLATFORM_SUPER_ADMIN',
            college_id=None,
            is_active=True
        )
        super_admin.set_password(super_admin_pass)
        db.session.add(super_admin)

    # 2. Seed College Admin for Default Tenant
    college_admin_email = os.environ.get('COLLEGEADMIN_EMAIL', 'admin@spmcollege.ac.in')
    college_admin_pass = os.environ.get('COLLEGEADMIN_PASSWORD', 'CollegeAdmin@123')

    college_admin = User.query.filter_by(email=college_admin_email).first()
    if not college_admin:
        college_admin = User(
            email=college_admin_email,
            role='COLLEGE_ADMIN',
            college_id=college.id,
            is_active=True
        )
        college_admin.set_password(college_admin_pass)
        db.session.add(college_admin)

    db.session.commit()

def seed_default_gallery_items(college):
    """
    Idempotent seeding function for default gallery items.
    """
    for item_data in DEFAULT_SEED_GALLERY_ITEMS:
        existing = GalleryItem.query.filter_by(college_id=college.id, title=item_data['title']).first()
        if not existing:
            item = GalleryItem(
                college_id=college.id,
                title=item_data['title'],
                category=item_data['category'],
                category_label=item_data['category_label'],
                description=item_data['description'],
                icon=item_data['icon'],
                gradient=item_data['gradient'],
                image_url=item_data['image_url']
            )
            db.session.add(item)
    db.session.commit()

def seed_default_forum_posts(college):
    """
    Idempotent seeding function for default community forum posts.
    """
    for post_data in DEFAULT_SEED_FORUM_POSTS:
        existing = ForumPost.query.filter_by(
            college_id=college.id,
            title=post_data['title']
        ).first()
        if not existing:
            post = ForumPost(
                college_id=college.id,
                author=post_data['author'],
                title=post_data['title'],
                category=post_data['category'],
                content=post_data['content'],
                replies=post_data.get('replies', 0),
                likes=post_data.get('likes', 0)
            )
            db.session.add(post)
    db.session.commit()

DEFAULT_SEED_COURSES = {
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
            {'year': '2025', 'sem': '1st Sem', 'subject': 'Programming in C & Digital Logic', 'file': 'BCA_Sem1_ProgC_2025.pdf'},
            {'year': '2025', 'sem': '2nd Sem', 'subject': 'Data Structures using C++', 'file': 'BCA_Sem2_DataStructures_2025.pdf'},
            {'year': '2025', 'sem': '3rd Sem', 'subject': 'Java Programming & OOPS', 'file': 'BCA_Sem3_Java_2025.pdf'},
            {'year': '2025', 'sem': '4th Sem', 'subject': 'Database Management Systems (DBMS)', 'file': 'BCA_Sem4_DBMS_2025.pdf'},
            {'year': '2025', 'sem': '5th Sem', 'subject': 'Full Stack Web Development', 'file': 'BCA_Sem5_FullStack_2025.pdf'},
            {'year': '2025', 'sem': '6th Sem', 'subject': 'Advanced Java & Cloud Computing', 'file': 'BCA_Sem6_Cloud_2025.pdf'}
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
            {'year': '2025', 'sem': '1st Sem', 'subject': 'Advanced Data Structures & Algorithms', 'file': 'MCA_Sem1_ADS_2025.pdf'},
            {'year': '2025', 'sem': '2nd Sem', 'subject': 'Machine Learning & Deep Learning', 'file': 'MCA_Sem2_ML_2025.pdf'},
            {'year': '2025', 'sem': '3rd Sem', 'subject': 'Cloud Microservices Architecture', 'file': 'MCA_Sem3_Cloud_2025.pdf'},
            {'year': '2025', 'sem': '4th Sem', 'subject': 'Big Data Engineering & Security', 'file': 'MCA_Sem4_BigData_2025.pdf'}
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
            {'year': '2025', 'sem': '1st Sem', 'subject': 'Principles of Management', 'file': 'BBA_Sem1_PrinciplesMgmt_2025.pdf'},
            {'year': '2025', 'sem': '2nd Sem', 'subject': 'Marketing Management', 'file': 'BBA_Sem2_Marketing_2025.pdf'},
            {'year': '2025', 'sem': '3rd Sem', 'subject': 'Human Resource Management', 'file': 'BBA_Sem3_HRM_2025.pdf'},
            {'year': '2025', 'sem': '4th Sem', 'subject': 'Entrepreneurship Development', 'file': 'BBA_Sem4_Ent_2025.pdf'},
            {'year': '2025', 'sem': '5th Sem', 'subject': 'Financial Management', 'file': 'BBA_Sem5_Finance_2025.pdf'},
            {'year': '2025', 'sem': '6th Sem', 'subject': 'International Business & Analytics', 'file': 'BBA_Sem6_IB_2025.pdf'}
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
            {'year': '2025', 'sem': '1st Sem', 'subject': 'Financial Accounting I', 'file': 'BCom_Sem1_FA1_2025.pdf'},
            {'year': '2025', 'sem': '2nd Sem', 'subject': 'Advanced Accounting', 'file': 'BCom_Sem2_AdvAcc_2025.pdf'},
            {'year': '2025', 'sem': '3rd Sem', 'subject': 'Direct Taxation', 'file': 'BCom_Sem3_Tax_2025.pdf'},
            {'year': '2025', 'sem': '4th Sem', 'subject': 'Cost Accounting', 'file': 'BCom_Sem4_Cost_2025.pdf'},
            {'year': '2025', 'sem': '5th Sem', 'subject': 'Auditing & Assurance', 'file': 'BCom_Sem5_Auditing_2025.pdf'},
            {'year': '2025', 'sem': '6th Sem', 'subject': 'Business Taxation & GST', 'file': 'BCom_Sem6_GST_2025.pdf'}
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
            {'year': '2025', 'sem': '1st Sem', 'subject': 'Managerial Economics & Accounts', 'file': 'MBA_Sem1_Econ_2025.pdf'},
            {'year': '2025', 'sem': '2nd Sem', 'subject': 'Financial Management', 'file': 'MBA_Sem2_FM_2025.pdf'},
            {'year': '2025', 'sem': '3rd Sem', 'subject': 'Corporate Strategy & Governance', 'file': 'MBA_Sem3_Strategy_2025.pdf'},
            {'year': '2025', 'sem': '4th Sem', 'subject': 'Strategic Leadership & Operations', 'file': 'MBA_Sem4_Leadership_2025.pdf'}
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
            {'year': '2025', 'sem': '1st Sem', 'subject': 'Advanced Financial Management', 'file': 'MCom_Sem1_AFM_2025.pdf'},
            {'year': '2025', 'sem': '2nd Sem', 'subject': 'Corporate Tax Planning', 'file': 'MCom_Sem2_Tax_2025.pdf'},
            {'year': '2025', 'sem': '3rd Sem', 'subject': 'Security Analysis & Portfolio Mgmt', 'file': 'MCom_Sem3_SAPM_2025.pdf'},
            {'year': '2025', 'sem': '4th Sem', 'subject': 'Derivatives Markets & Banking', 'file': 'MCom_Sem4_Derivatives_2025.pdf'}
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
            {'year': '2025', 'sem': '1st Sem', 'subject': 'English Literature & Composition', 'file': 'BA_Sem1_Literature_2025.pdf'},
            {'year': '2025', 'sem': '2nd Sem', 'subject': 'Journalism & Mass Media', 'file': 'BA_Sem2_Journalism_2025.pdf'},
            {'year': '2025', 'sem': '3rd Sem', 'subject': 'Indian Constitution & Public Admin', 'file': 'BA_Sem3_Constitution_2025.pdf'},
            {'year': '2025', 'sem': '4th Sem', 'subject': 'Developmental Psychology', 'file': 'BA_Sem4_Psychology_2025.pdf'},
            {'year': '2025', 'sem': '5th Sem', 'subject': 'Political Theory & Diplomacy', 'file': 'BA_Sem5_Politics_2025.pdf'},
            {'year': '2025', 'sem': '6th Sem', 'subject': 'Social Movements & Contemporary India', 'file': 'BA_Sem6_Sociology_2025.pdf'}
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
            {'year': '2025', 'sem': '1st Sem', 'subject': 'Calculus & Linear Algebra', 'file': 'BSc_Sem1_Maths_2025.pdf'},
            {'year': '2025', 'sem': '2nd Sem', 'subject': 'Mechanics & Wave Oscillations', 'file': 'BSc_Sem2_Physics_2025.pdf'},
            {'year': '2025', 'sem': '3rd Sem', 'subject': 'Probability & Statistical Theory', 'file': 'BSc_Sem3_Stats_2025.pdf'},
            {'year': '2025', 'sem': '4th Sem', 'subject': 'Differential Equations & Analysis', 'file': 'BSc_Sem4_Maths_2025.pdf'},
            {'year': '2025', 'sem': '5th Sem', 'subject': 'Electromagnetism & Quantum Physics', 'file': 'BSc_Sem5_Physics_2025.pdf'},
            {'year': '2025', 'sem': '6th Sem', 'subject': 'Applied Statistical Inference', 'file': 'BSc_Sem6_Stats_2025.pdf'}
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
            {'year': '2025', 'sem': '1st Sem', 'subject': 'Advanced Algorithms & Complexity', 'file': 'MSc_Sem1_Algo_2025.pdf'},
            {'year': '2025', 'sem': '2nd Sem', 'subject': 'Quantum Computing Concepts', 'file': 'MSc_Sem2_Quantum_2025.pdf'},
            {'year': '2025', 'sem': '3rd Sem', 'subject': 'Deep Neural Networks & Vision', 'file': 'MSc_Sem3_NN_2025.pdf'},
            {'year': '2025', 'sem': '4th Sem', 'subject': 'Distributed Database Systems', 'file': 'MSc_Sem4_Distributed_2025.pdf'}
        ]
    }
}

def seed_default_courses(college):
    """
    Idempotent seeding function for default academic courses, outcomes, curriculum, and sample question papers.
    """
    for code_key, cdata in DEFAULT_SEED_COURSES.items():
        existing_course = Course.query.filter_by(college_id=college.id, code=cdata['code']).first()
        if not existing_course:
            course = Course(
                college_id=college.id,
                code=cdata['code'],
                name=cdata['name'],
                level=cdata['level'],
                duration=cdata['duration'],
                affiliation=cdata['affiliation'],
                overview=cdata['overview'],
                eligibility=cdata['eligibility']
            )
            db.session.add(course)
            db.session.flush()

            for idx, outcome_text in enumerate(cdata.get('outcomes', [])):
                outcome = CourseOutcome(
                    course_id=course.id,
                    content=outcome_text,
                    display_order=idx + 1
                )
                db.session.add(outcome)

            for s_idx, sem_data in enumerate(cdata.get('curriculum', [])):
                semester = CurriculumSemester(
                    course_id=course.id,
                    semester_name=sem_data['sem'],
                    display_order=s_idx + 1
                )
                db.session.add(semester)
                db.session.flush()

                for subj_idx, subj_name in enumerate(sem_data.get('subjects', [])):
                    subject = CurriculumSubject(
                        semester_id=semester.id,
                        subject_name=subj_name,
                        display_order=subj_idx + 1
                    )
                    db.session.add(subject)

            for paper_data in cdata.get('question_papers', []):
                paper = QuestionPaper(
                    course_id=course.id,
                    year=paper_data['year'],
                    semester=paper_data['sem'],
                    subject=paper_data['subject'],
                    filename=paper_data['file']
                )
                db.session.add(paper)
        else:
            course = existing_course
            for paper_data in cdata.get('question_papers', []):
                existing_paper = QuestionPaper.query.filter_by(course_id=course.id, filename=paper_data['file']).first()
                if not existing_paper:
                    paper = QuestionPaper(
                        course_id=course.id,
                        year=paper_data['year'],
                        semester=paper_data['sem'],
                        subject=paper_data['subject'],
                        filename=paper_data['file']
                    )
                    db.session.add(paper)
                else:
                    existing_paper.semester = paper_data['sem']
                    existing_paper.subject = paper_data['subject']
                    existing_paper.year = paper_data['year']

    db.session.commit()

DEFAULT_CAMPUS_EVENTS = [
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

DEFAULT_ACADEMIC_CALENDAR = [
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

def seed_default_events_and_calendar(college):
    """
    Idempotent seeding function for default campus events and academic calendar timeline items.
    """
    for idx, ev_data in enumerate(DEFAULT_CAMPUS_EVENTS):
        existing = CampusEvent.query.filter_by(
            college_id=college.id,
            title=ev_data['title'],
            date_display=ev_data['date']
        ).first()
        if not existing:
            event = CampusEvent(
                college_id=college.id,
                title=ev_data['title'],
                date_display=ev_data['date'],
                day=ev_data['day'],
                month=ev_data['month'],
                category=ev_data['category'],
                description=ev_data['description'],
                icon=ev_data['icon'],
                display_order=idx + 1
            )
            db.session.add(event)

    for idx, cal_data in enumerate(DEFAULT_ACADEMIC_CALENDAR):
        existing = AcademicCalendarItem.query.filter_by(
            college_id=college.id,
            event_name=cal_data['event'],
            date_display=cal_data['date']
        ).first()
        if not existing:
            item = AcademicCalendarItem(
                college_id=college.id,
                event_name=cal_data['event'],
                date_display=cal_data['date'],
                event_type=cal_data['type'],
                display_order=idx + 1
            )
            db.session.add(item)

    db.session.commit()

def seed_default_college():
    """
    Idempotent seeding function for default Seshadripuram College tenant,
    its institutional settings, initial module configurations, default admin accounts, gallery items, forum posts, courses, events, and calendar items.
    """
    college = College.query.filter_by(slug='seshadripuram-college').first()
    if not college:
        college = College(
            name='Seshadripuram College',
            slug='seshadripuram-college',
            status='active'
        )
        db.session.add(college)
        db.session.commit()

    if not college.settings:
        setting = CollegeSetting(
            college_id=college.id,
            college_name='Seshadripuram College',
            tagline='Affiliated to Bengaluru City University | NAAC Accredited A++',
            email_info='info@spmcollege.ac.in',
            phone_primary='+91 6363179389 / 080-22955354',
            address='Seshadripuram Main Campus, Bengaluru - 560020',
            accreditation='NAAC A++ Accredited',
            hero_title='Shaping Futures, Building Leaders',
            hero_subtitle='Welcome to Seshadripuram College, a premier institution of higher education offering top-tier Undergraduate and Postgraduate degree programs.'
        )
        db.session.add(setting)

    for key, data in DEFAULT_MODULE_MATRIX.items():
        existing_cfg = ModuleConfig.query.filter_by(college_id=college.id, module_key=key).first()
        if not existing_cfg:
            cfg = ModuleConfig(
                college_id=college.id,
                module_key=key,
                name=data['name'],
                enabled=data['enabled'],
                admin_access=data['admin_access']
            )
            db.session.add(cfg)

    db.session.commit()
    seed_default_users(college)
    seed_default_gallery_items(college)
    seed_default_forum_posts(college)
    seed_default_courses(college)
    seed_default_events_and_calendar(college)
    return college

def get_default_college():
    """
    Helper function to resolve the current default college tenant.
    """
    college = College.query.filter_by(slug='seshadripuram-college').first()
    if not college:
        college = seed_default_college()
    return college

def get_database_module_matrix(college_id=None):
    """
    Fetch ModuleConfig rows for a college and convert them into the exact
    dictionary structure expected by existing Jinja templates and routes.
    """
    if college_id is None:
        college = get_default_college()
        college_id = college.id

    configs = ModuleConfig.query.filter_by(college_id=college_id).all()
    
    # Fallback to defaults if no configs found in DB
    if not configs:
        seed_default_college()
        configs = ModuleConfig.query.filter_by(college_id=college_id).all()

    matrix = {}
    for cfg in configs:
        matrix[cfg.module_key] = {
            'name': cfg.name,
            'enabled': cfg.enabled,
            'admin_access': cfg.admin_access
        }
    
    # Ensure any missing keys in DB are filled with default values and inserted
    has_new = False
    for key, data in DEFAULT_MODULE_MATRIX.items():
        if key not in matrix:
            cfg = ModuleConfig(
                college_id=college_id,
                module_key=key,
                name=data['name'],
                enabled=data['enabled'],
                admin_access=data['admin_access']
            )
            db.session.add(cfg)
            has_new = True
            matrix[key] = {
                'name': data['name'],
                'enabled': data['enabled'],
                'admin_access': data['admin_access']
            }
    if has_new:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return matrix
