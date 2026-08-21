import os
import csv
import re
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'guamc-secret-key-2026'

# Render-এর জন্য ডেটাবেস পাথ নিশ্চিতকরণ
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'portal_live.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models import db, Student
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(int(user_id))

def extract_two_digit_roll(val1, val2):
    raw_str = str(val1).strip() if val1 else ''
    if not raw_str or raw_str.lower() == 'none':
        raw_str = str(val2).strip() if val2 else ''
    digits = re.findall(r'\d+', raw_str)
    if digits:
        num = int(digits[-1])
        return f"{num:02d}"
    return "01"

def generate_diu_id(batch, course, roll_two_digit):
    b_digits = re.findall(r'\d+', str(batch))
    b_num = b_digits[0] if b_digits else "37"
    course_str = str(course).upper()
    c_code = "2" if ('BAMS' in course_str or 'AYURVEDIC' in course_str) else "1"
    return f"{b_num}{c_code}{roll_two_digit}"

def sync_csv():
    csv_path = os.path.join(basedir, 'students.csv')
    if not os.path.exists(csv_path):
        return
    try:
        with open(csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for r in reader:
                em = (r.get('email') or '').strip().lower()
                if not em:
                    continue

                student = Student.query.filter_by(email=em).first()
                if not student:
                    student = Student(email=em)
                    db.session.add(student)

                c_roll_raw = r.get('class_roll')
                r_no_raw = r.get('roll_no')
                clean_two_digit_roll = extract_two_digit_roll(c_roll_raw, r_no_raw)

                student.course = (r.get('course') or 'BUMS').strip()
                student.batch = (r.get('batch') or '37th').strip()
                student.name_english = (r.get('name_english') or '').strip()
                student.name_bangla = (r.get('name_bangla') or '').strip()
                student.photo = (r.get('photo') or '').strip()
                student.roll_no = clean_two_digit_roll
                student.class_roll = clean_two_digit_roll
                student.registration_no = (r.get('registration_no') or '').strip()
                student.contact_number = (r.get('contact_number') or '').strip()
                student.blood_group = (r.get('blood_group') or '').strip()
                student.gender = (r.get('gender') or '').strip()
                student.date_of_birth = (r.get('date_of_birth') or '').strip()
                student.unique_id = generate_diu_id(student.batch, student.course, clean_two_digit_roll)
                student.password_hash = generate_password_hash('guamc123')
            
            db.session.commit()
    except Exception as e:
        print("CSV Sync Exception:", e)

with app.app_context():
    db.create_all()
    sync_csv()

@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not email:
            flash('Please provide an email address.', 'danger')
            return render_template('login.html')

        sync_csv()
        student = Student.query.filter_by(email=email).first()

        # ফলব্যাক: ডেটাবেসে না থাকলেও তাৎক্ষণিক স্টুডেন্ট তৈরি করে লগইন করানো হবে
        if not student:
            name_part = email.split('@')[0].replace('.', ' ').title()
            student = Student(
                email=email,
                name_english=name_part,
                course='BUMS',
                batch='37th',
                roll_no='01',
                class_roll='01',
                unique_id='37101',
                password_hash=generate_password_hash('guamc123')
            )
            db.session.add(student)
            db.session.commit()

        login_user(student)
        return redirect(url_for('dashboard'))
            
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    course = (current_user.course or 'BUMS').upper()
    if 'BAMS' in course:
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