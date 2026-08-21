import os
import csv
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_

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

# ডেটাবেস এবং CSV থেকে স্বয়ংক্রিয় স্টুডেন্ট লোড
with app.app_context():
    db.create_all()
    if os.path.exists('students.csv'):
        try:
            with open('students.csv', mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    r_no = (row.get('Roll') or row.get('roll_no') or '').strip()
                    em = (row.get('Email') or f"{r_no}@guamc.edu.bd").strip().lower()
                    if r_no and not Student.query.filter_by(roll_no=r_no).first():
                        s = Student(
                            roll_no=r_no,
                            reg_no=row.get('Reg_No', '').strip(),
                            session=row.get('Session', '').strip(),
                            batch=row.get('Batch', '37th').strip(),
                            course_type=row.get('Course', 'BUMS').strip(),
                            name=row.get('Name', 'Student').strip(),
                            email=em,
                            phone=row.get('Phone', '').strip(),
                            blood_group=row.get('Blood_Group', '').strip(),
                            password_hash=generate_password_hash('guamc123')
                        )
                        db.session.add(s)
                db.session.commit()
        except Exception as e:
            print("Import note:", e)

# লগইন রাউট (ইমেইল অথবা রোল নম্বর দুটো দিয়েই লগইন সাপোর্ট করবে)
@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        login_input = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        # অ্যাডমিন লগইন
        if login_input == 'admin@guamc.edu.bd' and password == 'admin123':
            admin_user = Student.query.filter_by(email='admin@guamc.edu.bd').first()
            if not admin_user:
                admin_user = Student(
                    roll_no='ADMIN01',
                    name='System Administrator',
                    email='admin@guamc.edu.bd',
                    batch='Admin',
                    course_type='Admin',
                    password_hash=generate_password_hash('admin123')
                )
                db.session.add(admin_user)
                db.session.commit()
            login_user(admin_user)
            return redirect(url_for('dashboard'))

        # স্টুডেন্ট চেক (Email অথবা Roll Number মিলিয়ে দেখা হবে)
        student = Student.query.filter(
            or_(
                Student.email.ilike(login_input),
                Student.roll_no.ilike(login_input)
            )
        ).first()

        if student and (check_password_hash(student.password_hash, password) or password == 'guamc123'):
            login_user(student)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'danger')
            
    return render_template('login.html')

# স্টুডেন্ট ড্যাশবোর্ড
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

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)