from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Student(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    course = db.Column(db.String(50))
    batch = db.Column(db.String(50))
    roll_no = db.Column(db.String(50))
    phone = db.Column(db.String(30))
    guardian_name = db.Column(db.String(150))
    address = db.Column(db.String(255))
    ssc_school = db.Column(db.String(200))
    ssc_gpa = db.Column(db.String(20))
    ssc_year = db.Column(db.String(20))
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class StudentRepresentative(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course = db.Column(db.String(20), nullable=False)       # BUMS or BAMS
    batch = db.Column(db.String(50), nullable=False)
    role_type = db.Column(db.String(50), nullable=False)    # CR or Intern Coordinator
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(150))

class ExamResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    exam_title = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    written_marks = db.Column(db.Float, default=0.0)
    viva_marks = db.Column(db.Float, default=0.0)
    practical_marks = db.Column(db.Float, default=0.0)
    total_marks = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="Passed")
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship('Student', backref='results')

class ExamClearance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    prof_name = db.Column(db.String(50), nullable=False, default="1st Professional")
    term_1_status = db.Column(db.String(30), default="Cleared")
    term_2_status = db.Column(db.String(30), default="In Progress")
    attendance_pct = db.Column(db.Float, default=85.0)
    card_completion = db.Column(db.String(30), default="Completed")
    is_eligible = db.Column(db.Boolean, default=True)
    student = db.relationship('Student', backref='clearances')

class ClubMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    club_name = db.Column(db.String(100), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship('Student', backref='clubs')

class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100), default="Authority")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class VideoVlog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    submitted_by = db.Column(db.String(100), nullable=False)
    video_id = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ForumTopic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_name = db.Column(db.String(100), nullable=False)
    course_tag = db.Column(db.String(20), default="General") # BUMS, BAMS, General
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    replies = db.relationship('ForumReply', backref='topic', cascade='all, delete-orphan')

class ForumReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('forum_topic.id'), nullable=False)
    author_name = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)