from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Student(UserMixin, db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    unique_id = db.Column(db.String(50), unique=True, index=True)
    
    # Academic & Identity
    batch = db.Column(db.String(20), default='37th')
    course = db.Column(db.String(50), default='BUMS')
    roll_no = db.Column(db.String(20))
    class_roll = db.Column(db.String(20))
    session = db.Column(db.String(30))
    photo = db.Column(db.String(255))
    name_bangla = db.Column(db.String(150))
    name_english = db.Column(db.String(150))
    gender = db.Column(db.String(30))
    marital_status = db.Column(db.String(50))
    father_name = db.Column(db.String(150))
    father_occupation = db.Column(db.String(100))
    mother_name = db.Column(db.String(150))
    mother_occupation = db.Column(db.String(100))
    date_of_birth = db.Column(db.String(30))
    nid_or_birth_cert = db.Column(db.String(50))
    
    # Support & Aid
    family_income = db.Column(db.String(50))
    family_members = db.Column(db.String(20))
    need_financial_aid = db.Column(db.String(10))
    has_personal_income = db.Column(db.String(10))
    income_source_details = db.Column(db.Text)
    
    # Educational Background
    hsc_background = db.Column(db.Text)
    ssc_background = db.Column(db.Text)
    
    # Campus Involvement & Activities
    library_member = db.Column(db.String(10))
    hall_resident = db.Column(db.String(50))
    co_curricular_activities = db.Column(db.Text)
    club_interests = db.Column(db.Text)
    
    # Health & Medical Information
    height = db.Column(db.String(50))
    weight = db.Column(db.String(30))
    wear_glasses = db.Column(db.String(10))
    blood_group = db.Column(db.String(10))
    chronic_illness = db.Column(db.Text)
    known_allergies = db.Column(db.Text)
    regular_medication = db.Column(db.Text)
    emergency_medical_contact = db.Column(db.String(30))
    identification_mark = db.Column(db.String(150))
    
    # Contact & Credentials
    contact_number = db.Column(db.String(30))
    guardian_contact = db.Column(db.String(30))
    present_address = db.Column(db.Text)
    permanent_address = db.Column(db.Text)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255))
    
    # Attendance & Clearance
    total_classes = db.Column(db.Integer, nullable=True)
    attended_classes = db.Column(db.Integer, nullable=True)
    attendance = db.Column(db.Float, nullable=True)
    
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    performances = db.relationship('DepartmentPerformance', backref='student', cascade="all, delete-orphan")

class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    course = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(50), nullable=True)
    order = db.Column(db.Integer, default=0)
    performances = db.relationship('DepartmentPerformance', backref='department', cascade="all, delete-orphan")

class DepartmentPerformance(db.Model):
    __tablename__ = 'department_performances'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    attendance_rate = db.Column(db.Float, nullable=True)
    item_card_status = db.Column(db.String(50), default='In Progress')

class AttendanceRecord(db.Model):
    __tablename__ = 'attendance_records'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    date = db.Column(db.String(20), nullable=False)
    subject = db.Column(db.String(100), default='General')
    status = db.Column(db.String(10), default='P')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FileFolder(db.Model):
    __tablename__ = 'file_folders'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    course = db.Column(db.String(20), default='ALL')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    files = db.relationship('AcademicFile', backref='folder', cascade="all, delete-orphan")

class AcademicFile(db.Model):
    __tablename__ = 'academic_files'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    file_type = db.Column(db.String(50), default='Item Card')
    course = db.Column(db.String(20), default='ALL')
    file_url = db.Column(db.String(300), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('file_folders.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class NavigationLink(db.Model):
    __tablename__ = 'navigation_links'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    endpoint_or_url = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(50), default='🔗')
    order = db.Column(db.Integer, default=0)
    is_external = db.Column(db.Boolean, default=False)

class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='General')
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship('Student', backref='posts')

class Notice(db.Model):
    __tablename__ = 'notices'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    pdf_url = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)