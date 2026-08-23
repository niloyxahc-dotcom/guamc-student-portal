from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Student(UserMixin, db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    unique_id = db.Column(db.String(50), unique=True, index=True)
    name_english = db.Column(db.String(150))
    name_bangla = db.Column(db.String(150))
    father_name = db.Column(db.String(150))
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255))
    course = db.Column(db.String(50), default='BUMS')
    batch = db.Column(db.String(20), default='37th')
    roll_no = db.Column(db.String(20))
    class_roll = db.Column(db.String(20))
    contact_number = db.Column(db.String(30))
    emergency_medical_contact = db.Column(db.String(30))
    blood_group = db.Column(db.String(10))
    photo = db.Column(db.String(255))
    
    total_classes = db.Column(db.Integer, nullable=True)
    attended_classes = db.Column(db.Integer, nullable=True)
    attendance = db.Column(db.Float, nullable=True)
    
    is_approved = db.Column(db.Boolean, default=False)
    performances = db.relationship('DepartmentPerformance', backref='student', cascade="all, delete-orphan")

class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    course = db.Column(db.String(20), nullable=False) # BAMS or BUMS
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
    item_card_status = db.Column(db.String(50), default='In Progress') # In Progress, Cleared, Needs Assessment

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
    file_type = db.Column(db.String(50), default='Item Card') # Item Card, Item Routine, Syllabus, E-Book
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