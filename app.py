import os
import csv
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Student

app = Flask(__name__)
app.config['SECRET_KEY'] = 'guamc-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///portal_clean.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(int(user_id))

with app.app_context():
    db.create_all()
    if os.path.exists('students.csv'):
        try:
            with open('students.csv', mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    r_no = row.get('Roll') or row.get('roll_no')
                    if r_no and not Student.query.filter_by(roll_no=r_no).first():
                        s = Student(
                            roll_no=r_no,
                            reg_no=row.get('Reg_No', ''),
                            session=row.get('Session', ''),
                            batch=row.get('Batch', '37th'),
                            course_type=row.get('Course', 'BUMS'),
                            name=row.get('Name', 'Student'),
                            email=row.get('Email', f"{r_no}@guamc.edu.bd"),
                            phone=row.get('Phone', ''),
                            blood_group=row.get('Blood_Group', ''),
                            password_hash=generate_password_hash('guamc123')
                        )
                        db.session.add(s)
                db.session.commit()
        except Exception as e:
            print("Import info:", e)

@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        student = Student.query.filter_by(email=email).first()
        if student and check_password_hash(student.password_hash, password):
            login_user(student)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'danger')
            
    return render_template('login.html')

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

@app.route('/academic')
@login_required
def academic():
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)