from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class Student(UserMixin, db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    batch = db.Column(db.String(20), default='37th')
    course = db.Column(db.String(20), default='BUMS')
    roll_no = db.Column(db.String(20))
    class_roll = db.Column(db.String(20))
    session = db.Column(db.String(50))
    unique_id = db.Column(db.String(50), unique=True, index=True)

    name_bangla = db.Column(db.String(150))
    name_english = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True, index=True)
    password_hash = db.Column(db.String(255))
    photo = db.Column(db.String(500))

    father_name = db.Column(db.String(150))
    mother_name = db.Column(db.String(150))
    contact_number = db.Column(db.String(50))
    emergency_medical_contact = db.Column(db.String(50))
    guardian_contact = db.Column(db.String(50))
    blood_group = db.Column(db.String(10))
    present_address = db.Column(db.Text)
    permanent_address = db.Column(db.Text)
    income_source_details = db.Column(db.Text)

    attendance = db.Column(db.Float, default=None)
    attended_classes = db.Column(db.Integer, default=0)
    total_classes = db.Column(db.Integer, default=0)

    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    performances = db.relationship('DepartmentPerformance', backref='student', lazy=True, cascade="all, delete-orphan")
    attendance_records = db.relationship('AttendanceRecord', backref='student', lazy=True, cascade="all, delete-orphan")
    posts = db.relationship('Post', backref='author', lazy=True, cascade="all, delete-orphan")

class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    course = db.Column(db.String(20), default='BAMS')
    name = db.Column(db.String(150), nullable=False)
    order = db.Column(db.Integer, default=0)

    performances = db.relationship('DepartmentPerformance', backref='department', lazy=True, cascade="all, delete-orphan")

class DepartmentPerformance(db.Model):
    __tablename__ = 'department_performances'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    attendance_rate = db.Column(db.Float, default=None)
    item_card_status = db.Column(db.String(50), default='In Progress')

class AttendanceRecord(db.Model):
    __tablename__ = 'attendance_records'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(150), default='General Session')
    status = db.Column(db.String(10), default='P')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FileFolder(db.Model):
    __tablename__ = 'file_folders'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    course = db.Column(db.String(20), default='ALL')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    files = db.relationship('AcademicFile', backref='folder', lazy=True, cascade="all, delete-orphan")

class AcademicFile(db.Model):
    __tablename__ = 'academic_files'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50), default='Item Card')
    course = db.Column(db.String(20), default='ALL')
    file_url = db.Column(db.String(500), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('file_folders.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class NavigationLink(db.Model):
    __tablename__ = 'navigation_links'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    endpoint_or_url = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(20), default='🔗')
    order = db.Column(db.Integer, default=0)
    is_external = db.Column(db.Boolean, default=False)

class Post(db.Model):
    __tablename__ = 'posts'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='General')
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notice(db.Model):
    __tablename__ = 'notices'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)