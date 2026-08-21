import os
import csv
import re
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'guamc-production-secret-2026'

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'portal_live_v5.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models import db, Student
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(int(user_id))

# অফিসিয়াল রোল শিটের মাস্টার ডেটা
OFFICIAL_STUDENTS = {
    # --- BUMS (Department of Unani Medicine & Surgery) ---
    "ARBIN HOSSAIN": {"roll": "01", "course": "BUMS", "name": "MD. ARBIN HOSSAIN PURNA"},
    "MORIOM BEGUM": {"roll": "02", "course": "BUMS", "name": "MORIOM BEGUM SYNTHI"},
    "AYESHA KHATUN": {"roll": "03", "course": "BUMS", "name": "BIBI AYESHA KHATUN"},
    "JOYONTEE": {"roll": "04", "course": "BUMS", "name": "JOYONTEE DEBNATH"},
    "AYESHA BINTE": {"roll": "05", "course": "BUMS", "name": "AYESHA BINTE AMIN"},
    "SHUMAIA": {"roll": "06", "course": "BUMS", "name": "SHUMAIA SHARA"},
    "JANNATARA": {"roll": "07", "course": "BUMS", "name": "MOST. JANNATARA KHATUN"},
    "SHAHRIAR": {"roll": "08", "course": "BUMS", "name": "MD. SHAHRIAR AHMED"},
    "ISRAT ISLAM": {"roll": "09", "course": "BUMS", "name": "ISRAT ISLAM MIM"},
    "SABRINA ALAM": {"roll": "10", "course": "BUMS", "name": "SABRINA ALAM LISA"},
    "TOMA AFRIN": {"roll": "11", "course": "BUMS", "name": "MST. TOMA AFRIN"},
    "MUSFIQUR": {"roll": "12", "course": "BUMS", "name": "MUSFIQUR RAHMAN TAQEE"},
    "JUBEDA": {"roll": "13", "course": "BUMS", "name": "JUBEDA AKTER JUI"},
    "SUROVY": {"roll": "14", "course": "BUMS", "name": "SUROVY MONY TUSTO"},
    "SABIHA": {"roll": "15", "course": "BUMS", "name": "MST. SABIHA TUN NUR"},
    "MOBASHWIRA": {"roll": "16", "course": "BUMS", "name": "MOBASHWIRA MOMIN SNEHA"},
    "RATNA AKTER": {"roll": "18", "course": "BUMS", "name": "MOST. RATNA AKTER SHAIKH"},
    "SWEETY RANI": {"roll": "19", "course": "BUMS", "name": "SWEETY RANI"},
    "SHARMIN": {"roll": "20", "course": "BUMS", "name": "SHARMIN SULTANA"},
    "TABASSUM": {"roll": "21", "course": "BUMS", "name": "MST. UMME TABASSUM"},
    "MAISHA": {"roll": "22", "course": "BUMS", "name": "MAISHA FARZANA"},
    "ANONNO": {"roll": "23", "course": "BUMS", "name": "MST. ANONNO AKTER JONY"},

    # --- BAMS (Department of Ayurvedic Medicine & Surgery) ---
    "SUBAIIA": {"roll": "01", "course": "BAMS", "name": "MST. SUBAIIA YEASMIN"},
    "ARPAN": {"roll": "02", "course": "BAMS", "name": "ARPAN CHANDRA ROY"},
    "ISRAT JAHAN": {"roll": "03", "course": "BAMS", "name": "ISRAT JAHAN"},
    "ABU RASHIED": {"roll": "04", "course": "BAMS", "name": "MD. ABU RASHIED JAMADAR"},
    "AFSANA": {"roll": "06", "course": "BAMS", "name": "MST. AFSANA MIM"},
    "UMMA KHADIJA": {"roll": "07", "course": "BAMS", "name": "MOST. UMMA KHADIJA TULL KUBRA HABIBA"},
    "MONAREALLY": {"roll": "08", "course": "BAMS", "name": "MONAREALLY TRIPURA"},
    "ESRAT JAHAN": {"roll": "09", "course": "BAMS", "name": "ESRAT JAHAN ESHA"},
    "AMIR HOSSAIN": {"roll": "12", "course": "BAMS", "name": "MD. AMIR HOSSAIN"},
    "ZOBAYER": {"roll": "13", "course": "BAMS", "name": "MD. ZOBAYER RAHMAN"},
    "RAWFUN": {"roll": "14", "course": "BAMS", "name": "MST. RAWFUN JANNAT"},
    "RAHUL": {"roll": "15", "course": "BAMS", "name": "RAHUL BABU"},
    "SAMIA": {"roll": "16", "course": "BAMS", "name": "SAMIA AFRIN"},
    "MISHAT": {"roll": "17", "course": "BAMS", "name": "UMME MISHAT TASNIM RINKY"},
    "BUSHRA": {"roll": "18", "course": "BAMS", "name": "BUSHRA NAZIA"},
    "SABA": {"roll": "19", "course": "BAMS", "name": "SABA TASNIM"},
    "OISHY": {"roll": "20", "course": "BAMS", "name": "OISHY SIKDER SWARNA"}
}

def resolve_official_data(name_str, email_str, default_course='BUMS'):
    combined = f"{name_str} {email_str}".upper()
    for key, data in OFFICIAL_STUDENTS.items():
        if key in combined:
            return data["roll"], data["course"], data["name"]
    return "01", default_course, (name_str or email_str.split('@')[0].title())

def generate_diu_id(batch, course, roll_two_digit):
    course_str = str(course).upper()
    c_code = "2" if ('BAMS' in course_str or 'AYURVEDIC' in course_str) else "1"
    return f"37{c_code}{roll_two_digit}"

# সার্ভার স্টার্টআপের সময় একবারই ডাটাবেস ইনিশিয়ালাইজ ও সিঙ্ক হবে
with app.app_context():
    db.create_all()
    csv_path = os.path.join(basedir, 'students.csv')
    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for r in reader:
                    clean_r = {str(k).strip().lower(): str(v).strip() for k, v in r.items() if k}
                    em = clean_r.get('email', '').lower()
                    if not em:
                        continue

                    student = Student.query.filter_by(email=em).first()
                    if not student:
                        student = Student(email=em)
                        db.session.add(student)

                    raw_name = clean_r.get('name_english') or clean_r.get('name') or em.split('@')[0]
                    raw_course = clean_r.get('course', 'BUMS')

                    official_roll, official_course, official_name = resolve_official_data(raw_name, em, raw_course)

                    student.name_english = official_name
                    student.name_bangla = clean_r.get('name_bangla', '')
                    student.course = official_course
                    student.batch = '37th'
                    student.roll_no = official_roll
                    student.class_roll = official_roll
                    student.registration_no = clean_r.get('registration_no', '')
                    student.contact_number = clean_r.get('contact_number', '')
                    student.blood_group = clean_r.get('blood_group', 'A+')
                    student.gender = clean_r.get('gender', '')
                    student.date_of_birth = clean_r.get('date_of_birth', '')
                    student.unique_id = generate_diu_id('37', official_course, official_roll)
                    student.password_hash = generate_password_hash('guamc123')
                
                db.session.commit()
        except Exception as e:
            print("CSV Startup Sync Note:", e)

# লগইন
@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        student = Student.query.filter_by(email=email).first()

        if not student:
            off_roll, off_course, off_name = resolve_official_data("", email, "BUMS")
            student = Student(
                email=email,
                name_english=off_name,
                course=off_course,
                batch='37th',
                roll_no=off_roll,
                class_roll=off_roll,
                unique_id=generate_diu_id('37', off_course, off_roll),
                blood_group='A+',
                password_hash=generate_password_hash('guamc123')
            )
            db.session.add(student)
            db.session.commit()

        login_user(student)
        return redirect(url_for('dashboard'))
            
    return render_template('login.html')

# স্টুডেন্ট ড্যাশবোর্ড
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

# লগআউট
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)