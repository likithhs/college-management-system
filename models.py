from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db

class College(db.Model):
    __tablename__ = 'college'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(100), unique=True, index=True, nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    settings = db.relationship('CollegeSetting', uselist=False, backref='college', cascade='all, delete-orphan')
    module_configs = db.relationship('ModuleConfig', backref='college', cascade='all, delete-orphan')
    users = db.relationship('User', backref='college', cascade='all, delete-orphan')
    applications = db.relationship('AdmissionApplication', backref='college', cascade='all, delete-orphan')
    gallery_items = db.relationship('GalleryItem', backref='college', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<College {self.slug}>"


class CollegeSetting(db.Model):
    __tablename__ = 'college_setting'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), unique=True, nullable=False)
    
    college_name = db.Column(db.String(150), default='Seshadripuram College')
    tagline = db.Column(db.String(250), default='Affiliated to Bengaluru City University | NAAC Accredited A++')
    logo_path = db.Column(db.String(250), default='')
    email_info = db.Column(db.String(120), default='info@spmcollege.ac.in')
    phone_primary = db.Column(db.String(50), default='+91 6363179389 / 080-22955354')
    address = db.Column(db.String(300), default='Seshadripuram Main Campus, Bengaluru - 560020')
    accreditation = db.Column(db.String(100), default='NAAC A++ Accredited')
    hero_title = db.Column(db.String(150), default='Shaping Futures, Building Leaders')
    hero_subtitle = db.Column(db.String(300), default='Welcome to Seshadripuram College, a premier institution of higher education.')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CollegeSetting college_id={self.college_id}>"


class ModuleConfig(db.Model):
    __tablename__ = 'module_config'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    module_key = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    admin_access = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('college_id', 'module_key', name='uix_college_module_key'),
    )

    def __repr__(self):
        return f"<ModuleConfig {self.module_key} enabled={self.enabled} admin_access={self.admin_access}>"


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=True)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(30), default='COLLEGE_ADMIN', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_super_admin(self):
        return self.role == 'PLATFORM_SUPER_ADMIN'

    @property
    def is_college_admin(self):
        return self.role == 'COLLEGE_ADMIN'

    def __repr__(self):
        return f"<User {self.email} role={self.role}>"


class AdmissionApplication(db.Model):
    __tablename__ = 'admission_applications'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    application_number = db.Column(db.String(50), unique=True, index=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    guardian_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    course = db.Column(db.String(150), nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default='UNDER_REVIEW', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AdmissionApplication {self.application_number} name={self.full_name} status={self.status}>"


class GalleryItem(db.Model):
    __tablename__ = 'gallery_items'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    category_label = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True, default='')
    icon = db.Column(db.String(100), nullable=True, default='fa-solid fa-image')
    gradient = db.Column(db.String(100), nullable=True, default='from-blue-900 to-indigo-700')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<GalleryItem {self.id} title={self.title} category={self.category}>"
