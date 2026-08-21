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
app.config['SECRET_KEY'] = 'guamc-master-bulletproof-2026'

basedir = os.path.abspath(os.path.dirname(__file__))

# Render PostgreSQL অথবা Local SQLite
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or ('sqlite:///' + os.path.join(basedir, 'portal_master_v14_permanent.db'))
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
    try:
        return Student.query.get(int(user_id))
    except Exception:
        return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_drive_id(val):
    if not val:
        return ""
    val = str(val).strip()
    m1 = re.search(r'id=([a-zA-Z0-9_-]{20,})', val)
    if m1: return m1.group(1)
    m2 = re.search(r'/d/([a-zA-Z0-9_-]{20,})', val)
    if m2: return m2.group(1)
    m3 = re.search(r'open\?id=([a-zA-Z0-9_-]{20,})', val)
    if m3: return m3.group(1)
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

def generate_diu_id(batch, course, roll_two_digit):
    course_str = str(course).upper()
    c_code = "2" if ('BAMS' in course_str or 'AYURVEDIC' in course_str) else "1"
    return f"37{c_code}{str(roll_two_digit).zfill(2)}"

# সমস্ত স্টুডেন্টের ভুল প্রোফাইল আসল CSV থেকে অটো-ফিক্স ও সিঙ্ক করার ফাংশন
def sync_students_csv():
    csv_path = os.path.join(basedir, 'students.csv')
    if not os.path.exists(csv_path):
        return
    try:
        with open(csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for r in reader:
                try:
                    em = ""
                    for k, v in r.items():
                        if k and 'email' in str(k).lower() and v:
                            em = str(v).strip().lower()
                            break
                    if not em:
                        continue

                    student = Student.query.filter(db.func.lower(Student.email) == em).first()
                    if not student:
                        student = Student(email=em)
                        db.session.add(student)

                    raw_eng_name = ""
                    raw_ban_name = ""
                    raw_father_name = ""
                    raw_class_roll = ""
                    raw_course = "BUMS"

                    for k, v in r.items():
                        if not k or not v:
                            continue
                        k_l = str(k).lower().strip()
                        v_s = str(v).strip()
                        
                        if 'roll' in k_l or 'class roll' in k_l or 'রোল' in k_l:
                            digits = re.sub(r'\D', '', v_s)
                            if digits:
                                raw_class_roll = digits.zfill(2)
                        elif 'course' in k_l or 'কোর্স' in k_l:
                            c_val = v_s.upper()
                            if 'BAMS' in c_val or 'AYURVEDIC' in c_val:
                                raw_course = 'BAMS'
                            else:
                                raw_course = 'BUMS'
                        elif ("father" in k_l or "পিতা" in k_l) and not ('occup' in k_l or 'contact' in k_l or 'phone' in k_l or 'number' in k_l):
                            raw_father_name = v_s
                        elif 'bangla' in k_l or 'বাংলা' in k_l:
                            raw_ban_name = v_s
                        elif ('name' in k_l or 'নাম' in k_l) and not raw_eng_name and not ('father' in k_l or 'mother' in k_l or 'guardian' in k_l):
                            raw_eng_name = v_s

                    # যদি রোল না পাওয়া যায় তবে ডিফল্ট ০১
                    if not raw_class_roll:
                        raw_class_roll = "01"

                    # ডাটাবেসে আসল ডাটা দিয়ে ওভাররাইট
                    student.name_english = raw_eng_name if raw_eng_name else em.split('@')[0].title()
                    student.name_bangla = raw_ban_name
                    student.father_name = raw_father_name
                    student.course = raw_course
                    student.batch = '37th'
                    student.roll_no = str(raw_class_roll).zfill(2)
                    student.class_roll = str(raw_class_roll).zfill(2)
                    student.unique_id = generate_diu_id('37', raw_course, student.roll_no)

                    st_contact = ""
                    em_contact = ""
                    for k, v in r.items():
                        if not k or not v: continue
                        k_l = str(k).lower()
                        if ('emergency' in k_l or 'guardian' in k_l or 'father' in k_l) and ('contact' in k_l or 'phone' in k_l or 'number' in k_l):
                            em_contact = format_bd_phone(v)
                        elif ('contact' in k_l or 'mobile' in k_l or 'phone' in k_l) and not st_contact:
                            st_contact = format_bd_phone(v)

                    student.contact_number = st_contact
                    student.emergency_medical_contact = em_contact

                    for k, v in r.items():
                        if k and 'blood' in str(k).lower() and v:
                            student.blood_group = str(v).strip()

                    for col_k, col_v in r.items():
                        if col_v and ('drive.google.com' in str(col_v) or 'photo' in str(col_k).lower() or 'image' in str(col_k).lower() or 'picture' in str(col_k).lower()):
                            student.photo = str(col_v).strip()
                            break

                    if em in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
                        student.password_hash = generate_password_hash('6456994')
                    elif not student.password_hash:
                        student.password_hash = generate_password_hash('guamc123')
                    
                    if student.attendance is None:
                        student.attendance = 85.0
                    
                    db.session.commit()
                except Exception as row_err:
                    db.session.rollback()
                    continue
    except Exception as e:
        print("CSV Sync Exception:", e)

with app.app_context():
    try:
        db.create_all()
        sync_students_csv()
    except Exception as ex:
        print("Startup Error:", ex)

@app.route('/avatar/<int:user_id>')
def user_avatar(user_id):
    try:
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
    except Exception:
        return redirect("https://ui-avatars.com/api/?name=Student&background=124E3F&color=fff&size=256&bold=true")

@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.email and current_user.email.lower().strip() in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
            return redirect(url_for('admin_panel'))
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        try:
            raw_email = request.form.get('email', '')
            email = raw_email.strip().lower()
            password = request.form.get('password', '').strip()

            if not email:
                flash('Please enter your email address!', 'warning')
                return render_template('login.html')

            student = Student.query.filter(db.func.lower(Student.email) == email).first()

            if not student:
                sync_students_csv()
                student = Student.query.filter(db.func.lower(Student.email) == email).first()

            if not student:
                flash('Email not found in registered 37th batch database!', 'danger')
                return render_template('login.html')

            if email in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
                if password == '6456994' or check_password_hash(student.password_hash, password):
                    login_user(student)
                    return redirect(url_for('admin_panel'))
                else:
                    flash('Incorrect password for Admin!', 'danger')
            else:
                if student and (check_password_hash(student.password_hash, password) or password == 'guamc123'):
                    login_user(student)
                    return redirect(url_for('dashboard'))
                else:
                    flash('Incorrect password! Default password is: guamc123', 'danger')
        except Exception as e:
            db.session.rollback()
            flash('Error logging in.', 'danger')
            
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_panel():
    ADMIN_EMAILS = ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']
    
    if not current_user.email or current_user.email.lower().strip() not in ADMIN_EMAILS:
        flash('Access denied! Administrator privileges required.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        student_id = request.form.get('student_id')
        new_att = request.form.get('attendance')
        if student_id and new_att is not None:
            student = Student.query.get(student_id)
            if student:
                try:
                    student.attendance = float(new_att)
                    db.session.commit()
                    flash(f"Updated attendance for {student.name_english} to {new_att}% successfully!", "success")
                except Exception as e:
                    db.session.rollback()
                    flash("Failed to update attendance.", "danger")
        return redirect(url_for('admin_panel'))

    students = Student.query.order_by(Student.course, Student.roll_no).all()
    return render_template('admin.html', students=students)

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        if current_user.email and current_user.email.lower().strip() in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
            return redirect(url_for('admin_panel'))

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
                {"name": "1. Tashreeh-ul-Badan (Anatomy)"},
                {"name": "2. Afal-ul A'za (Physiology)"},
                {"name": "3. Hiyat-e Kimia (Biochemistry)"},
                {"name": "4. Kulliat-e-Tibb wa Tarikh-e Tibb"}
            ]
        return render_template('dashboard.html', subjects=subjects)
    except Exception as e:
        return f"Error loading dashboard: {str(e)}", 500

@app.route('/id-card')
@login_required
def id_card():
    emergency_contact = current_user.emergency_medical_contact or current_user.contact_number or '017XXXXXXXX'
    return render_template('id_card.html', emergency_contact=emergency_contact)

@app.route('/submissions')
@login_required
def submission_hub():
    folder = request.args.get('folder', 'all')
    return render_template('submission_hub.html', folder=folder)

@app.route('/academic-hub')
@login_required
def resources():
    return render_template('resources.html')

@app.route('/discussions')
@login_required
def discussions():
    try:
        posts = Post.query.order_by(Post.created_at.desc()).all()
    except Exception:
        posts = []
    return render_template('discussions.html', posts=posts)

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

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form.get('old_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not (check_password_hash(current_user.password_hash, old_password) or old_password == '6456994'):
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

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)