from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class Student(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(50), unique=True, nullable=False)
    reg_no = db.Column(db.String(50), nullable=True)
    session = db.Column(db.String(50), nullable=True)
    batch = db.Column(db.String(50), nullable=True, default='37th')
    course_type = db.Column(db.String(50), nullable=True, default='BUMS')
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    blood_group = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(256), nullable=True)