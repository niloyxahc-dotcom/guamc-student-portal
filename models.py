from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class Student(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(20), unique=True, nullable=False)
    reg_no = db.Column(db.String(30))
    session = db.Column(db.String(50))
    batch = db.Column(db.String(20))       # যেমন: '34th', '35th', '36th', '37th'
    course_type = db.Column(db.String(20)) # যেমন: 'BUMS' বা 'BAMS'
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    blood_group = db.Column(db.String(10))
    password_hash = db.Column(db.String(256))
    
    # অ্যাডমিন চেক প্রোপার্টি (যদি ইমেইল admin@guamc.edu.bd হয়)
    @property
    def is_admin(self):
        return self.email == 'admin@guamc.edu.bd'