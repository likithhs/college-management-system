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
    forum_posts = db.relationship('ForumPost', backref='college', cascade='all, delete-orphan')
    courses = db.relationship('Course', backref='college', cascade='all, delete-orphan')
    campus_events = db.relationship('CampusEvent', backref='college', cascade='all, delete-orphan')
    academic_calendar_items = db.relationship('AcademicCalendarItem', backref='college', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='college', cascade='all, delete-orphan')
    faculty_members = db.relationship('FacultyMember', backref='college', cascade='all, delete-orphan')
    placement_drives = db.relationship('PlacementDrive', backref='college', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<College {self.slug}>"


class CollegeSetting(db.Model):
    __tablename__ = 'college_setting'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), unique=True, nullable=False)
    
    # Core Identity
    college_name = db.Column(db.String(150), default='Seshadripuram College')
    short_name = db.Column(db.String(30), default='SPM')
    tagline = db.Column(db.String(250), default='Affiliated to Bengaluru City University | NAAC Accredited A++')
    affiliation = db.Column(db.String(150), default='Bengaluru City University')
    accreditation = db.Column(db.String(100), default='NAAC A++ Accredited')
    est_year = db.Column(db.String(20), default='1998')
    alumni_count = db.Column(db.String(50), default='5,000+')
    logo_path = db.Column(db.String(250), default='')
    
    # Leadership & Principal's Desk
    principal_name = db.Column(db.String(120), default='Dr. M. Prakash')
    principal_title = db.Column(db.String(150), default='MCom, PhD, Principal')
    principal_message = db.Column(db.Text, default='Welcome to our institution, committed to nurturing intellect, ethics, and leadership in every student. For over two decades, our college has stood as a beacon of academic excellence, holistic education, and cultural vibrancy. We believe that true education extends beyond textbooks to embrace critical thinking, technological innovation, and strong moral character. Our dedicated faculty, state-of-the-art infrastructure, and robust industry partnerships ensure that our graduates are well-equipped to excel in the global arena.')
    principal_photo = db.Column(db.String(250), default='')
    trust_name = db.Column(db.String(150), default='Seshadripuram Educational Trust (SET)')
    trust_president = db.Column(db.String(120), default='Sri N. R. Panditharadhya')
    trustee_name = db.Column(db.String(120), default='Sri W. D. Ashok')

    # Contact & Campus Location
    email_info = db.Column(db.String(120), default='info@spmcollege.ac.in')
    admissions_email = db.Column(db.String(120), default='admissions@spmcollege.ac.in')
    phone_primary = db.Column(db.String(50), default='+91 6363179389 / 080-22955354')
    address = db.Column(db.String(300), default='Seshadripuram Main Campus, Bengaluru - 560020')
    city = db.Column(db.String(100), default='Bengaluru')
    state_pincode = db.Column(db.String(100), default='Karnataka 560020')
    map_query = db.Column(db.String(250), default='Seshadripuram College, Seshadripuram, Bengaluru, Karnataka 560020')

    # Homepage Hero & About Story
    hero_title = db.Column(db.String(150), default='Shaping Futures, Building Leaders')
    hero_subtitle = db.Column(db.String(300), default='Welcome to Seshadripuram College, a premier institution of higher education offering top-tier Undergraduate and Postgraduate degree programs.')
    about_story = db.Column(db.Text, default='Established with a commitment to academic distinction and holistic student development, the college offers premier undergraduate and postgraduate programs. With modern laboratories, distinguished faculty, and comprehensive industry tie-ups, students achieve their fullest personal and professional potential.')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CollegeSetting college_id={self.college_id} name='{self.college_name}'>"


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
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False, index=True)
    application_number = db.Column(db.String(50), unique=True, index=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    guardian_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), index=True, nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    course = db.Column(db.String(150), nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default='PENDING', index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AdmissionApplication {self.application_number} name={self.full_name} status={self.status}>"


class GalleryItem(db.Model):
    __tablename__ = 'gallery_items'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False, index=True)
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


class ForumPost(db.Model):
    __tablename__ = 'forum_posts'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False, index=True)
    author = db.Column(db.String(150), nullable=False)
    title = db.Column(db.String(250), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    replies = db.Column(db.Integer, nullable=False, default=0)
    likes = db.Column(db.Integer, nullable=False, default=0)
    likes_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    reply_records = db.relationship('ForumReply', backref='post', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<ForumPost {self.id} title={self.title} author={self.author}>"


class ForumReply(db.Model):
    __tablename__ = 'forum_replies'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_posts.id'), nullable=False, index=True)
    author = db.Column(db.String(150), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    is_admin_reply = db.Column(db.Boolean, default=False, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<ForumReply {self.id} post={self.post_id} author={self.author}>"


class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False, index=True)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    level = db.Column(db.String(50), nullable=False)
    duration = db.Column(db.String(50), nullable=False)
    affiliation = db.Column(db.String(150), nullable=False)
    overview = db.Column(db.Text, nullable=False)
    eligibility = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('college_id', 'code', name='uq_course_college_code'),
    )

    outcome_records = db.relationship('CourseOutcome', backref='course', cascade='all, delete-orphan', order_by='CourseOutcome.display_order')
    semesters = db.relationship('CurriculumSemester', backref='course', cascade='all, delete-orphan', order_by='CurriculumSemester.display_order')
    question_papers = db.relationship('QuestionPaper', backref='course', cascade='all, delete-orphan', order_by='QuestionPaper.id')

    @property
    def outcomes(self):
        """Returns list of outcome content strings for template compatibility."""
        return [o.content for o in self.outcome_records]

    @property
    def curriculum(self):
        """Returns list of semester dicts with subject strings for template compatibility."""
        return [
            {
                'sem': sem.semester_name,
                'subjects': [s.subject_name for s in sem.subjects]
            }
            for sem in self.semesters
        ]

    def __repr__(self):
        return f"<Course {self.code} name={self.name}>"


class CourseOutcome(db.Model):
    __tablename__ = 'course_outcomes'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)

    def __repr__(self):
        return f"<CourseOutcome course_id={self.course_id} order={self.display_order}>"


class CurriculumSemester(db.Model):
    __tablename__ = 'curriculum_semesters'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False, index=True)
    semester_name = db.Column(db.String(50), nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)

    subjects = db.relationship('CurriculumSubject', backref='semester', cascade='all, delete-orphan', order_by='CurriculumSubject.display_order')

    def __repr__(self):
        return f"<CurriculumSemester {self.semester_name} course_id={self.course_id}>"


class CurriculumSubject(db.Model):
    __tablename__ = 'curriculum_subjects'

    id = db.Column(db.Integer, primary_key=True)
    semester_id = db.Column(db.Integer, db.ForeignKey('curriculum_semesters.id'), nullable=False, index=True)
    subject_code = db.Column(db.String(30), nullable=True, index=True)
    subject_name = db.Column(db.String(150), nullable=False)
    credits = db.Column(db.Integer, default=4, nullable=False)
    syllabus_summary = db.Column(db.Text, nullable=True)
    syllabus_pdf_url = db.Column(db.String(255), nullable=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty_members.id'), nullable=True, index=True)
    display_order = db.Column(db.Integer, default=0, nullable=False)

    faculty = db.relationship('FacultyMember', backref='assigned_subjects', foreign_keys=[faculty_id])
    materials = db.relationship('SubjectMaterial', backref='subject', cascade='all, delete-orphan', order_by='SubjectMaterial.id')

    def __repr__(self):
        return f"<CurriculumSubject {self.subject_name} sem_id={self.semester_id}>"


class SubjectMaterial(db.Model):
    __tablename__ = 'subject_materials'

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('curriculum_subjects.id'), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    material_type = db.Column(db.String(30), default='NOTES', nullable=False)
    file_url = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<SubjectMaterial {self.title} type={self.material_type}>"


class ExamTimetableItem(db.Model):
    __tablename__ = 'exam_timetables'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False, index=True)
    semester_name = db.Column(db.String(50), nullable=False, index=True)
    subject_name = db.Column(db.String(150), nullable=False)
    exam_date = db.Column(db.String(50), nullable=False)
    exam_time = db.Column(db.String(50), nullable=False)
    hall_number = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    course = db.relationship('Course', backref='exam_schedules')

    def __repr__(self):
        return f"<ExamTimetableItem {self.subject_name} ({self.exam_date})>"




class QuestionPaper(db.Model):
    __tablename__ = 'question_papers'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False, index=True)
    year = db.Column(db.String(10), nullable=False)
    semester = db.Column(db.String(20), nullable=False)
    subject = db.Column(db.String(150), nullable=False)
    filename = db.Column(db.String(250), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def sem(self):
        return self.semester

    @property
    def file(self):
        return self.filename

    def __repr__(self):
        return f"<QuestionPaper {self.filename} course_id={self.course_id}>"


class CampusEvent(db.Model):
    __tablename__ = 'campus_events'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    date_display = db.Column(db.String(100), nullable=False)
    day = db.Column(db.String(10), nullable=False)
    month = db.Column(db.String(10), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(100), nullable=False, default='fa-solid fa-calendar')
    display_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def date(self):
        return self.date_display

    def __repr__(self):
        return f"<CampusEvent {self.id} title={self.title} category={self.category}>"


class AcademicCalendarItem(db.Model):
    __tablename__ = 'academic_calendar_items'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False, index=True)
    date_display = db.Column(db.String(100), nullable=False)
    event_name = db.Column(db.String(200), nullable=False)
    event_type = db.Column(db.String(30), nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def event(self):
        return self.event_name

    @property
    def date(self):
        return self.date_display

    @property
    def type(self):
        return self.event_type

    def __repr__(self):
        return f"<AcademicCalendarItem {self.id} event={self.event_name} type={self.event_type}>"


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    recipient_email = db.Column(db.String(120), nullable=True, index=True)
    application_number = db.Column(db.String(50), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='admissions', nullable=False)
    link = db.Column(db.String(300), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<Notification {self.id} title={self.title} college={self.college_id}>"


class FacultyMember(db.Model):
    __tablename__ = 'faculty_members'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    designation = db.Column(db.String(100), nullable=False)
    department_code = db.Column(db.String(50), nullable=False, index=True)
    qualification = db.Column(db.String(150), nullable=False)
    specialization = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    photo_url = db.Column(db.String(250), nullable=True)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<FacultyMember {self.id} name={self.name} dept={self.department_code}>"


class PlacementDrive(db.Model):
    __tablename__ = 'placement_drives'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False, index=True)
    company_name = db.Column(db.String(150), nullable=False)
    company_logo = db.Column(db.String(250), nullable=True)
    role_offered = db.Column(db.String(150), nullable=False)
    package_lpa = db.Column(db.String(50), nullable=False)
    eligibility_criteria = db.Column(db.String(250), nullable=False)
    drive_date = db.Column(db.String(100), nullable=False)
    application_deadline = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(30), default='UPCOMING', nullable=False, index=True)
    contact_email = db.Column(db.String(120), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<PlacementDrive {self.id} company={self.company_name} status={self.status}>"


class StudentDocumentRequest(db.Model):
    __tablename__ = 'student_document_requests'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False, index=True)
    application_number = db.Column(db.String(50), nullable=False, index=True)
    student_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    document_type = db.Column(db.String(100), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default='PENDING', nullable=False, index=True)
    admin_remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<StudentDocumentRequest {self.id} doc={self.document_type} status={self.status}>"


class EventRegistration(db.Model):
    __tablename__ = 'event_registrations'
    __table_args__ = (
        db.UniqueConstraint('event_id', 'participant_email', name='uq_event_participant'),
    )

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False, index=True)
    event_id = db.Column(db.Integer, db.ForeignKey('campus_events.id'), nullable=False, index=True)
    participant_name = db.Column(db.String(150), nullable=False)
    participant_email = db.Column(db.String(120), nullable=False, index=True)
    participant_phone = db.Column(db.String(30), nullable=True)
    registration_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    status = db.Column(db.String(30), default='CONFIRMED', nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<EventRegistration {self.id} code={self.registration_code} email={self.participant_email}>"


class Student(db.Model):
    __tablename__ = 'students'
    __table_args__ = (
        db.UniqueConstraint('college_id', 'register_number', name='uq_student_college_regno'),
        db.UniqueConstraint('college_id', 'email', name='uq_student_college_email'),
    )

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False, index=True)
    register_number = db.Column(db.String(50), nullable=False, index=True)
    admission_application_id = db.Column(db.Integer, db.ForeignKey('admission_applications.id'), nullable=True, unique=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    course_code = db.Column(db.String(20), nullable=False, index=True)
    semester = db.Column(db.String(50), default='Semester 1', nullable=False)
    section = db.Column(db.String(10), default='A', nullable=False)
    status = db.Column(db.String(30), default='ACTIVE', nullable=False, index=True)
    profile_photo_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    application = db.relationship('AdmissionApplication', backref=db.backref('student_account', uselist=False))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Student {self.register_number} - {self.full_name} ({self.status})>"
