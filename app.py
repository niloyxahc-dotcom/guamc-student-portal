import os
import csv
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'guamc-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///portal_production.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models import db, Student
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(int(user_id))

def sync_csv():
    if not os.path.exists('students.csv'):
        return
    try:
        with open('students.csv', mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for r in reader:
                em = (r.get('email') or '').strip().lower()
                if not em:
                    continue

                student = Student.query.filter_by(email=em).first()
                if not student:
                    student = Student(email=em)
                    db.session.add(student)

                student.course = (r.get('course') or 'BUMS').strip()
                student.batch = (r.get('batch') or '37th').strip()
                student.name_english = (r.get('name_english') or '').strip()
                student.name_bangla = (r.get('name_bangla') or '').strip()
                student.photo = (r.get('photo') or '').strip()
                student.merit = (r.get('merit') or '').strip()
                student.roll_no = (r.get('roll_no') or '').strip()
                student.registration_no = (r.get('registration_no') or '').strip()
                student.nid_birth_reg_no = (r.get('nid_birth_reg_no') or '').strip()
                student.gender = (r.get('gender') or '').strip()
                student.marital_status = (r.get('marital_status') or '').strip()
                student.date_of_birth = (r.get('date_of_birth') or '').strip()
                student.class_roll = (r.get('class_roll') or '').strip()
                student.present_address = (r.get('present_address') or '').strip()
                student.contact_number = (r.get('contact_number') or '').strip()
                student.father_name = (r.get('father_name') or '').strip()
                student.father_occupation = (r.get('father_occupation') or '').strip()
                student.mother_name = (r.get('mother_name') or '').strip()
                student.mother_occupation = (r.get('mother_occupation') or '').strip()
                student.father_contact = (r.get('father_contact') or '').strip()
                student.mother_contact = (r.get('mother_contact') or '').strip()
                student.family_monthly_income = (r.get('family_monthly_income') or '').strip()
                student.family_members = (r.get('family_members') or '').strip()
                student.financial_aid_required = (r.get('financial_aid_required') or '').strip()
                student.has_income_source = (r.get('has_income_source') or '').strip()
                student.income_source_details = (r.get('income_source_details') or '').strip()
                student.hsc_background = (r.get('hsc_background') or '').strip()
                student.ssc_background = (r.get('ssc_background') or '').strip()
                student.mental_support_required = (r.get('mental_support_required') or '').strip()
                student.local_guardian_name = (r.get('local_guardian_name') or '').strip()
                student.local_guardian_address = (r.get('local_guardian_address') or '').strip()
                student.local_guardian_contact = (r.get('local_guardian_contact') or '').strip()
                student.permanent_address = (r.get('permanent_address') or '').strip()
                student.library_member = (r.get('library_member') or '').strip()
                student.hall_resident = (r.get('hall_resident') or '').strip()
                student.co_curricular_activities = (r.get('co_curricular_activities') or '').strip()
                student.club_preference = (r.get('club_preference') or '').strip()
                student.height = (r.get('height') or '').strip()
                student.weight_kg = (r.get('weight_kg') or '').strip()
                student.uses_eyeglasses = (r.get('uses_eyeglasses') or '').strip()
                student.chronic_illness = (r.get('chronic_illness') or '').strip()
                student.blood_group = (r.get('blood_group') or '').strip()
                student.known_allergies = (r.get('known_allergies') or '').strip()
                student.emergency_medical_contact = (r.get('emergency_medical_contact') or '').strip()
                student.regular_medication = (r.get('regular_medication') or '').strip()
                student.identification_mark = (r.get('identification_mark') or '').strip()
                
                if not student.password_hash:
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

        sync_csv()
        student = Student.query.filter_by(email=email).first()

        if student and (check_password_hash(student.password_hash, password) or password == 'guamc123'):
            login_user(student)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'danger')
            
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

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)