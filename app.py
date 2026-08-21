import os
import csv
import re
import urllib.request
import ssl
from flask import Flask, render_template, redirect, url_for, request, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'guamc-master-portal-2026'

basedir = os.path.abspath(os.path.dirname(__file__))
# ডাটাবেস সম্পূর্ণ নতুন ভার্সনে মাইগ্রেট হবে
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'portal_master_official_final_v3.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

from models import db, Student, Post, Notice
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_drive_id(val):
    if not val:
        return ""
    val = str(val).strip()
    m1 = re.search(r'id=([a-zA-Z0-9_-]{20,})', val)
    if m1:
        return m1.group(1)
    m2 = re.search(r'/d/([a-zA-Z0-9_-]{20,})', val)
    if m2:
        return m2.group(1)
    m3 = re.search(r'open\?id=([a-zA-Z0-9_-]{20,})', val)
    if m3:
        return m3.group(1)
    return ""

def format_bd_phone(raw_val):
    if not raw_val:
        return ""
    val = str(raw_val).strip()
    if 'E+' in val or 'e+' in val:
        try:
            val = str(int(float(val)))
        except Exception:
            pass
    digits = re.sub(r'\D', '', val)
    if not digits:
        return ""
    if len(digits) == 10 and digits.startswith('1'):
        return '0' + digits
    if len(digits) == 11 and digits.startswith('01'):
        return digits
    if len(digits) == 13 and digits.startswith('8801'):
        return digits[2:]
    return val

OFFICIAL_ROLL_MAP = {
    # --- BUMS ---
    "ARBIN": {"roll": "01", "course": "BUMS"},
    "PURNA": {"roll": "01", "course": "BUMS"},
    "MORIOM": {"roll": "02", "course": "BUMS"},
    "SYNTHI": {"roll": "02", "course": "BUMS"},
    "AYESHA KHATUN": {"roll": "03", "course": "BUMS"},
    "JOYONTEE": {"roll": "04", "course": "BUMS"},
    "AYESHA BINTE": {"roll": "05", "course": "BUMS"},
    "SHUMAIA": {"roll": "06", "course": "BUMS"},
    "SHARA": {"roll": "06", "course": "BUMS"},
    "JANNATARA": {"roll": "07", "course": "BUMS"},
    "SHAHRIAR": {"roll": "08", "course": "BUMS"},
    "ISRAT ISLAM": {"roll": "09", "course": "BUMS"},
    "SABRINA ALAM": {"roll": "10", "course": "BUMS"},
    "LISA": {"roll": "10", "course": "BUMS"},
    "TOMA AFRIN": {"roll": "11", "course": "BUMS"},
    "MUSFIQUR": {"roll": "12", "course": "BUMS"},
    "TAQEE": {"roll": "12", "course": "BUMS"},
    "JUBEDA": {"roll": "13", "course": "BUMS"},
    "JUI": {"roll": "13", "course": "BUMS"},
    "SUROVY": {"roll": "14", "course": "BUMS"},
    "TUSTO": {"roll": "14", "course": "BUMS"},
    "SABIHA": {"roll": "15", "course": "BUMS"},
    "MOBASHWIRA": {"roll": "16", "course": "BUMS"},
    "SNEHA": {"roll": "16", "course": "BUMS"},
    "RATNA": {"roll": "18", "course": "BUMS"},
    "SWEETY": {"roll": "19", "course": "BUMS"},
    "SHARMIN": {"roll": "20", "course": "BUMS"},
    "TABASSUM": {"roll": "21", "course": "BUMS"},
    "MAISHA": {"roll": "22", "course": "BUMS"},
    "ANONNO": {"roll": "23", "course": "BUMS"},
    "JONY": {"roll": "23", "course": "BUMS"},

    # --- BAMS ---
    "SUBAIIA": {"roll": "01", "course": "BAMS"},
    "ARPAN": {"roll": "02", "course": "BAMS"},
    "ISRAT JAHAN": {"roll": "03", "course": "BAMS"},
    "ABU RASHIED": {"roll": "04", "course": "BAMS"},
    "AFSANA": {"roll": "06", "course": "BAMS"},
    "UMMA KHADIJA": {"roll": "07", "course": "BAMS"},
    "HABIBA": {"roll": "07", "course": "BAMS"},
    "MONAREALLY": {"roll": "08", "course": "BAMS"},
    "ESRAT JAHAN": {"roll": "09", "course": "BAMS"},
    "ESHA": {"roll": "09", "course": "BAMS"},
    "JAKIA": {"roll": "09", "course": "BAMS"},
    "AMIR HOSSAIN": {"roll": "12", "course": "BAMS"},
    "ZOBAYER": {"roll": "13", "course": "BAMS"},
    "RAWFUN": {"roll": "14", "course": "BAMS"},
    "RAHUL": {"roll": "15", "course": "BAMS"},
    "SAMIA AFRIN": {"roll": "16", "course": "BAMS"},
    "MISHAT": {"roll": "17", "course": "BAMS"},
    "RINKY": {"roll": "17", "course": "BAMS"},
    "BUSHRA NAZIA": {"roll": "18", "course": "BAMS"},
    "SABA TASNIM": {"roll": "19", "course": "BAMS"},
    "OISHY": {"roll": "20", "course": "BAMS"},
    "SWARNA": {"roll": "20", "course": "BAMS"}
}

def resolve_official_roll(name_str, email_str, default_course='BUMS'):
    combined = f"{name_str} {email_str}".upper()
    for key, data in OFFICIAL_ROLL_MAP.items():
        if key in combined:
            return data["roll"], data["course"]
    return "01", default_course

def generate_diu_id(batch, course, roll_two_digit):
    course_str = str(course).upper()
    c_code = "2" if ('BAMS' in course_str or 'AYURVEDIC' in course_str) else "1"
    return f"37{c_code}{str(roll_two_digit).zfill(2)}"

with app.app_context():
    db.create_all()
    csv_path = os.path.join(basedir, 'students.csv')
    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for r in reader:
                    em = ""
                    for k, v in r.items():
                        if k and 'email' in str(k).lower() and v:
                            em = str(v).strip().lower()
                            break
                    if not em:
                        continue

                    student = Student.query.filter_by(email=em).first()
                    if not student:
                        student = Student(email=em)
                        db.session.add(student)

                    raw_eng_name = ""
                    raw_ban_name = ""
                    raw_father_name = ""

                    for k, v in r.items():
                        if not k or not v:
                            continue
                        k_l = str(k).lower().strip()
                        
                        if ("father's name" in k_l or "father name" in k_l or (k_l.startswith('father') and 'name' in k_l) or 'পিতা' in k_l) and not ('occup' in k_l or 'contact' in k_l or 'phone' in k_l or 'number' in k_l):
                            raw_father_name = str(v).strip()
                        elif 'bangla' in k_l:
                            raw_ban_name = str(v).strip()
                        elif ('name' in k_l or 'নাম' in k_l) and not raw_eng_name and not ('father' in k_l or 'mother' in k_l or 'guardian' in k_l):
                            raw_eng_name = str(v).strip()

                    raw_course = 'BUMS'
                    for k, v in r.items():
                        if k and 'course' in str(k).lower() and v:
                            raw_course = str(v).strip().upper()

                    official_roll, official_course = resolve_official_roll(raw_eng_name, em, default_course=raw_course)

                    student.name_english = raw_eng_name if raw_eng_name else em.split('@')[0].title()
                    student.name_bangla = raw_ban_name
                    student.father_name = raw_father_name
                    student.course = official_course
                    student.batch = '37th'
                    student.roll_no = str(official_roll).zfill(2)
                    student.class_roll = str(official_roll).zfill(2)

                    # কন্টাক্ট নম্বর
                    st_contact = ""
                    em_contact = ""
                    for k, v in r.items():
                        if not k or not v:
                            continue
                        k_l = str(k).lower()
                        if ('emergency' in k_l or 'guardian' in k_l or 'father' in k_l) and ('contact' in k_l or 'number' in k_l or 'phone' in k_l):
                            em_contact = format_bd_phone(v)
                        elif ('contact' in k_l or 'mobile' in k_l or 'phone' in k_l) and not st_contact:
                            st_contact = format_bd_phone(v)

                    student.contact_number = st_contact
                    student.emergency_medical_contact = em_contact

                    for k, v in r.items():
                        if k and 'blood' in str(k).lower() and v:
                            student.blood_group = str(v).strip()

                    found_img = ""
                    for col_k, col_v in r.items():
                        if col_v and ('drive.google.com' in str(col_v) or 'photo' in str(col_k).lower() or 'image' in str(col_k).lower() or 'picture' in str(col_k).lower()):
                            found_img = str(col_v).strip()
                            break
                    if found_img:
                        student.photo = found_img

                    student.unique_id = generate_diu_id('37', official_course, student.roll_no)
                    student.password_hash = generate_password_hash('guamc123')
                
                db.session.commit()
        except Exception as e:
            print("CSV Startup Sync:", e)

# ফটো প্রক্সি
@app.route('/avatar/<int:user_id>')
def user_avatar(user_id):
    student = Student.query.get(user_id)
    if student and student.photo:
        if student.photo.startswith('/static/'):
            return redirect(student.photo)
        
        drive_id = extract_drive_id(student.photo)
        if drive_id:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            headers = {'User-Agent': 'Mozilla/5.0'}
            
            for fetch_url in [f"https://lh3.googleusercontent.com/d/{drive_id}", f"https://drive.google.com/thumbnail?id={drive_id}&sz=w1000"]:
                try:
                    req = urllib.request.Request(fetch_url, headers=headers)
                    with urllib.request.urlopen(req, context=ctx, timeout=3) as resp:
                        data = resp.read()
                        if len(data) > 800:
                            return Response(data, mimetype="image/jpeg")
                except Exception:
                    continue

    name = student.name_english if (student and student.name_english) else 'Student'
    return redirect(f"https://ui-avatars.com/api/?name={name}&background=124E3F&color=fff&size=256&bold=true")

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
            off_roll, off_course = resolve_official_roll("", email, "BUMS")
            student = Student(
                email=email,
                name_english=email.split('@')[0].title(),
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

        if student and (check_password_hash(student.password_hash, password) or password == 'guamc123'):
            login_user(student)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'danger')
            
    return render_template('login.html')

# ড্যাশবোর্ড
@app.route('/dashboard')
@login_required
def dashboard():
    course = (current_user.course or 'BUMS').upper()
    if 'BAMS' in course:
        subjects = [
            {"name": "1. Rachana Sharir (Anatomy)"},
            {"name": "2. Kriya Sharir (Physiology)"},
            {"name": "3. Padartha Vigyan"},
            {"name": "4. Ashtanga Hridaya"}
        ]
    else:
        subjects = [
            {"name": "1. Tashrih (Anatomy)"},
            {"name": "2. Munafeul Aza (Physiology)"},
            {"name": "3. Kulliyat-e-Uloom-e-Paya"},
            {"name": "4. Advia Mufreda (Materia Medica)"}
        ]
    return render_template('dashboard.html', subjects=subjects)

# ডিজিটাল আইডি কার্ড
@app.route('/id-card')
@login_required
def id_card():
    emergency_contact = current_user.emergency_medical_contact or current_user.contact_number or '017XXXXXXXX'
    return render_template('id_card.html', emergency_contact=emergency_contact)

# সাবমিশন হাব (৪টি ফোল্ডার ও আপলোড)
@app.route('/submissions')
@login_required
def submission_hub():
    folder = request.args.get('folder', 'all')
    return render_template('submission_hub.html', folder=folder)

# একাডেমিক হাব / ই-বুক
@app.route('/academic-hub')
@login_required
def resources():
    return render_template('resources.html')

# ফোরাম ও ডিসকাশন
@app.route('/discussions')
@login_required
def discussions():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('discussions.html', posts=posts)

# পোস্ট সাবমিট রাউট
@app.route('/submit-post', methods=['GET', 'POST'])
@login_required
def submit_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category', 'General')
        if title and content:
            new_post = Post(title=title, content=content, category=category, student_id=current_user.id)
            db.session.add(new_post)
            db.session.commit()
            flash('Post published to Community Discussions!', 'success')
            return redirect(url_for('discussions'))
    return render_template('submit_post.html')

# ফটো আপলোড
@app.route('/upload-photo', methods=['POST'])
@login_required
def upload_photo():
    if 'photo' not in request.files:
        flash('No file selected!', 'danger')
        return redirect(url_for('dashboard'))
    
    file = request.files['photo']
    if file.filename == '':
        flash('No file selected!', 'danger')
        return redirect(url_for('dashboard'))
    
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"user_{current_user.id}_{current_user.unique_id}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        current_user.photo = url_for('static', filename=f'uploads/{filename}')
        db.session.commit()
        flash('Profile photo updated successfully!', 'success')
    else:
        flash('Allowed formats: JPG, PNG, JPEG, WEBP', 'warning')
        
    return redirect(url_for('dashboard'))

# পাসওয়ার্ড পরিবর্তন
@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form.get('old_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not (check_password_hash(current_user.password_hash, old_password) or old_password == 'guamc123'):
            flash('Current password is incorrect!', 'danger')
            return render_template('change_password.html')

        if len(new_password) < 6:
            flash('New password must be at least 6 characters long.', 'warning')
            return render_template('change_password.html')

        if new_password != confirm_password:
            flash('New passwords do not match!', 'danger')
            return render_template('change_password.html')

        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash('Password changed successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('change_password.html')

# লগআউট
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)