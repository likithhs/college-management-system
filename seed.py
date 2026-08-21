import os
from extensions import db
from models import College, CollegeSetting, ModuleConfig, User, GalleryItem

DEFAULT_MODULE_MATRIX = {
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

def seed_default_college():
    """
    Idempotent seeding function for default Seshadripuram College tenant,
    its institutional settings, initial module configurations, default admin accounts, and gallery items.
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
    
    # Ensure any missing keys in DB are filled with default values
    for key, data in DEFAULT_MODULE_MATRIX.items():
        if key not in matrix:
            matrix[key] = {
                'name': data['name'],
                'enabled': data['enabled'],
                'admin_access': data['admin_access']
            }
            
    return matrix
