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
    attendance = db.Column(db.Float, default=85.0)  # <-- এই লাইনটি যুক্ত করা হয়েছে

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