from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Student(UserMixin, db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    unique_id = db.Column(db.String(50), unique=True, nullable=False)
    name_english = db.Column(db.String(150))
    name_bangla = db.Column(db.String(150))
    father_name = db.Column(db.String(150))
    course = db.Column(db.String(50))
    batch = db.Column(db.String(50))
    roll_no = db.Column(db.String(50))
    class_roll = db.Column(db.String(50))
    email = db.Column(db.String(120), unique=True, nullable=False)
    contact_number = db.Column(db.String(50))
    emergency_medical_contact = db.Column(db.String(50))
    blood_group = db.Column(db.String(10))
    gender = db.Column(db.String(20))
    date_of_birth = db.Column(db.String(50))
    registration_no = db.Column(db.String(100))
    photo = db.Column(db.String(300))
    password_hash = db.Column(db.String(255))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship('Post', backref='author', lazy=True)


class Post(db.Model):
    __tablename__ = 'posts'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='General')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)


class Notice(db.Model):
    __tablename__ = 'notices'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(300), nullable=True)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)