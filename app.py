import os
import csv
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'guamc-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///portal_clean.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models import db, Student
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(int(user_id))

# ডেটাবেস টেবিল তৈরি
with app.app_context():
    db.create_all()

# শুধুমাত্র ইমেইল দিয়ে লগইন
@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not email:
            flash('Please enter your email address.', 'danger')
            return render_template('login.html')

        # ইমেইল দিয়ে ইউজার খোঁজা
        student = Student.query.filter(Student.email.ilike(email)).first()

        # যদি ডেটাবেসে না থাকে, তবে অটো রেজিস্টার করে ড্যাশবোর্ডে নেওয়া হবে
        if not student:
            extracted_name = email.split('@')[0].replace('.', ' ').title()
            student = Student(
                roll_no='GUAMC-37-01',
                reg_no='2023-GUAMC-001',
                session='2023-2024',
                batch='37th',
                course_type='BUMS',
                name=extracted_name,
                email=email,
                phone='017XXXXXXXX',
                blood_group='A+',
                password_hash=generate_password_hash('guamc123')
            )
            db.session.add(student)
            db.session.commit()

        login_user(student)
        return redirect(url_for('dashboard'))
            
    return render_template('login.html')

# ড্যাশবোর্ড
@app.route('/dashboard')
@login_required
def dashboard():
    course = getattr(current_user, 'course_type', 'BUMS') or 'BUMS'
    if course == 'BAMS':
        subjects = [
            {"name": "1. Rachana Sharir (Anatomy)", "items": "8/10 Completed", "att": "87%"},
            {"name": "2. Kriya Sharir (Physiology)", "items": "9/10 Completed", "att": "86%"},
            {"name": "3. Padartha Vigyan", "items": "7/10 Completed", "att": "81%"},
            {"name": "4. Ashtanga Hridaya", "items": "10/10 Completed", "att": "89%"}
        ]
    else:
        subjects = [
            {"name": "1. Tashrih (Anatomy)", "items": "8/10 Completed", "att": "88%"},
            {"name": "2. Munafeul Aza (Physiology)", "items": "9/10 Completed", "att": "85%"},
            {"name": "3. Kulliyat-e-Uloom-e-Paya", "items": "7/10 Completed", "att": "82%"},
            {"name": "4. Advia Mufreda (Materia Medica)", "items": "10/10 Completed", "att": "90%"}
        ]
    return render_template('dashboard.html', subjects=subjects)

# লগআউট
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)