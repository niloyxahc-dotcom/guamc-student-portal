import os
import csv
import re
import urllib.request
import ssl
from datetime import datetime, date
from flask import Flask, render_template, redirect, url_for, request, flash, Response, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://jtrcajaqybqzzoznsruz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp0cmNhamFxeWJxenpvem5zcnV6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc1MDUwODQsImV4cCI6MjEwMzA4MTA4NH0.kVlonjuIyEWxPL3aygsyX-UtMBbBL1wZZ2cizHOfq5c")

def upload_to_supabase_storage(file_bytes, filename, content_type):
    upload_url = f"{SUPABASE_URL}/storage/v1/object/student-photos/{filename}"
    headers = {
        "apiKey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": content_type or "image/jpeg"
    }
    response = requests.post(upload_url, headers=headers, data=file_bytes)
    if response.status_code in [200, 201]:
        return f"{SUPABASE_URL}/storage/v1/object/public/student-photos/{filename}"
    else:
        print(f"Supabase REST Error: {response.status_code} - {response.text}")
        return None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'guamc-aims-master-bulletproof-2026'

basedir = os.path.abspath(os.path.dirname(__file__))

db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or ('sqlite:///' + os.path.join(basedir, 'portal_master_v14_permanent.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 16 MB Max Upload Size Limit
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'pdf', 'docx', 'jpeg'}

from models import (
    db, 
    Student, 
    Department, 
    DepartmentPerformance, 
    AttendanceRecord, 
    FileFolder, 
    AcademicFile, 
    NavigationLink, 
    Post, 
    Notice
)
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

@app.context_processor
def inject_global_template_vars():
    try:
        nav_links = NavigationLink.query.order_by(NavigationLink.order.asc()).all()
        return dict(custom_nav_links=nav_links)
    except Exception:
        return dict(custom_nav_links=[])

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

def generate_diu_id(batch, course, roll_two_digit):
    course_str = str(course).upper()
    c_code = "2" if ('BAMS' in course_str or 'AYURVEDIC' in course_str) else "1"
    b_digits = re.sub(r'\D', '', str(batch)) or "37"
    return f"{b_digits}{c_code}{str(roll_two_digit).zfill(2)}"

def init_default_departments():
    bams_depts = [
        "Ayurvedic Moulik Siddhanta (Basic Principles)",
        "Dravyaguna (Pharmacology & Pharmacognosy)",
        "Sharir Rachana (Anatomy)",
        "Sharir Kriya (Physiology)",
        "Pran Rasayan (Biochemistry)"
    ]
    bums_depts = [
        "Tashreeh-ul-Badan (Anatomy)",
        "Afal-ul A'za (Physiology)",
        "Hiyat-e Kimia (Biochemistry)",
        "Kulliat-e-Tibb wa Tarikh-e Tibb",
        "Ilmul Advia (Pharmacology)"
    ]
    if Department.query.count() == 0:
        for i, name in enumerate(bams_depts, 1):
            db.session.add(Department(course='BAMS', name=name, order=i))
        for i, name in enumerate(bums_depts, 1):
            db.session.add(Department(course='BUMS', name=name, order=i))
        db.session.commit()
    else:
        for i, name in enumerate(bams_depts, 1):
            d = Department.query.filter_by(course='BAMS', order=i).first()
            if d:
                d.name = name
        for i, name in enumerate(bums_depts, 1):
            d = Department.query.filter_by(course='BUMS', order=i).first()
            if d:
                d.name = name
        db.session.commit()

def init_default_nav():
    if NavigationLink.query.count() == 0:
        defaults = [
            ("Dashboard", "dashboard", "🏠", 1, False),
            ("Submissions", "submission_hub", "📁", 2, False),
            ("Academic Hub", "resources", "📚", 3, False),
            ("ID Card", "id_card", "🪪", 4, False),
            ("Discussions", "discussions", "💬", 5, False),
        ]
        for title, endpoint, icon, order, is_ext in defaults:
            db.session.add(NavigationLink(title=title, endpoint_or_url=endpoint, icon=icon, order=order, is_external=is_ext))
        db.session.commit()

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

                    if not raw_class_roll:
                        raw_class_roll = "01"

                    student.name_english = raw_eng_name if raw_eng_name else em.split('@')[0].title()
                    if raw_ban_name:
                        student.name_bangla = raw_ban_name
                    if raw_father_name:
                        student.father_name = raw_father_name
                    student.course = raw_course
                    student.batch = '37th'
                    student.roll_no = str(raw_class_roll).zfill(2)
                    student.class_roll = str(raw_class_roll).zfill(2)
                    student.unique_id = generate_diu_id('37', raw_course, student.roll_no)
                    student.is_approved = True

                    st_contact = ""
                    em_contact = ""
                    for k, v in r.items():
                        if not k or not v:
                            continue
                        k_l = str(k).lower()
                        if ('emergency' in k_l or 'guardian' in k_l or 'father' in k_l) and ('contact' in k_l or 'phone' in k_l or 'number' in k_l):
                            em_contact = format_bd_phone(v)
                        elif ('contact' in k_l or 'mobile' in k_l or 'phone' in k_l) and not st_contact:
                            st_contact = format_bd_phone(v)

                    if st_contact:
                        student.contact_number = st_contact
                    if em_contact:
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
                    
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    continue
    except Exception as e:
        print("CSV Sync Exception:", e)

with app.app_context():
    try:
        db.create_all()
        sync_students_csv()
        init_default_departments()
        init_default_nav()
        
        Student.query.filter_by(total_classes=None).update({Student.attendance: None})
        DepartmentPerformance.query.filter_by(attendance_rate=85.0).update({DepartmentPerformance.attendance_rate: None})
        db.session.commit()
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
        return redirect(f"https://ui-avatars.com/api/?name={name}&background=093829&color=fff&size=256&bold=true")
    except Exception:
        return redirect("https://ui-avatars.com/api/?name=Student&background=093829&color=fff&size=256&bold=true")

# ==================== AUTHENTICATION ====================

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
                flash('Please enter your registered email address!', 'warning')
                return render_template('login.html')

            ADMIN_EMAILS = ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']

            if email in ADMIN_EMAILS:
                admin_user = Student.query.filter(db.func.lower(Student.email) == email).first()
                if not admin_user:
                    admin_user = Student(
                        email=email,
                        name_english="System Administrator",
                        name_bangla="সিস্টেম অ্যাডমিন",
                        course="BUMS",
                        batch="Admin",
                        roll_no="00",
                        class_roll="00",
                        unique_id="ADMIN01",
                        is_approved=True,
                        password_hash=generate_password_hash('6456994')
                    )
                    db.session.add(admin_user)
                    db.session.commit()

                if password == '6456994' or check_password_hash(admin_user.password_hash, password):
                    login_user(admin_user)
                    return redirect(url_for('admin_panel'))
                else:
                    flash('Incorrect password for Administrator!', 'danger')
                    return render_template('login.html')

            student = Student.query.filter(db.func.lower(Student.email) == email).first()

            if not student:
                flash('Invalid email address! Please check your registered email spelling or Sign Up first.', 'danger')
                return render_template('login.html')

            if not student.is_approved:
                flash('⚠️ Access Restricted! Your account is pending Administrator verification. Please wait until Admin approves your registration.', 'warning')
                return render_template('login.html')

            if check_password_hash(student.password_hash, password) or password == 'guamc123':
                login_user(student)
                return redirect(url_for('dashboard'))
            else:
                flash('Incorrect password! Default password is: guamc123', 'danger')
        except Exception:
            db.session.rollback()
            flash('An error occurred during authentication.', 'danger')
            
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            batch = request.form.get('batch', '37th').strip()
            course = request.form.get('course', 'BUMS').upper()
            roll_no = request.form.get('roll_no', '01').strip().zfill(2)
            session_yr = request.form.get('session', '').strip()
            name_bangla = request.form.get('name_bangla', '').strip()
            name_english = request.form.get('name_english', '').strip()
            gender = request.form.get('gender', '').strip()
            marital_status = request.form.get('marital_status', '').strip()
            father_name = request.form.get('father_name', '').strip()
            father_occupation = request.form.get('father_occupation', '').strip()
            mother_name = request.form.get('mother_name', '').strip()
            mother_occupation = request.form.get('mother_occupation', '').strip()
            date_of_birth = request.form.get('date_of_birth', '').strip()
            nid_or_birth_cert = request.form.get('nid_or_birth_cert', '').strip()

            family_income = request.form.get('family_income', '').strip()
            family_members = request.form.get('family_members', '').strip()
            guardian_contact = request.form.get('guardian_contact', '').strip()
            present_address = request.form.get('present_address', '').strip()
            permanent_address = request.form.get('permanent_address', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()

            if not email or not name_english or not roll_no or not password:
                flash('Please fill in all mandatory fields (*)!', 'warning')
                return render_template('signup.html')

            if password != confirm_password:
                flash('Passwords do not match!', 'danger')
                return render_template('signup.html')

            existing = Student.query.filter(db.func.lower(Student.email) == email).first()
            if existing:
                flash('This email is already registered! Please login or wait for Admin approval.', 'warning')
                return redirect(url_for('login'))

            photo_path = None
            if 'photo' in request.files and request.files['photo'].filename != '':
                f = request.files['photo']
                if allowed_file(f.filename):
                    ext = f.filename.rsplit('.', 1)[1].lower()
                    unique_filename = f"signup_{batch}_{course}_{roll_no}_{int(datetime.utcnow().timestamp())}.{ext}"
                    try:
                        file_bytes = f.read()
                        photo_path = upload_to_supabase_storage(file_bytes, unique_filename, f.content_type)
                        if not photo_path:
                            raise Exception("Failed to upload to Supabase")
                    except Exception as e:
                        print(f"Supabase upload fallback: {e}")
                        f.seek(0)
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        f.save(filepath)
                        photo_path = url_for('static', filename=f'uploads/{unique_filename}')
                else:
                    flash('Invalid photo format! Only JPG and PNG (Max: 500 KB) allowed.', 'warning')
                    return render_template('signup.html')

            new_student = Student(
                batch=batch,
                course=course,
                roll_no=roll_no,
                session=session_yr,
                name_bangla=name_bangla,
                name_english=name_english,
                gender=gender,
                marital_status=marital_status,
                father_name=father_name,
                father_occupation=father_occupation,
                mother_name=mother_name,
                mother_occupation=mother_occupation,
                date_of_birth=date_of_birth,
                nid_or_birth_cert=nid_or_birth_cert,
                family_income=family_income,
                family_members=family_members,
                guardian_contact=guardian_contact,
                present_address=present_address,
                permanent_address=permanent_address,
                email=email,
                photo=photo_path,
                is_approved=False
            )
            new_student.set_password(password)
            db.session.add(new_student)
            db.session.commit()

            flash('Registration successful! Please wait for Admin approval.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
            return render_template('signup.html')

    return render_template('signup.html')

# ==================== STUDENT DASHBOARD ====================

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        if current_user.email and current_user.email.lower().strip() in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
            return redirect(url_for('admin_panel'))

        course = (current_user.course or 'BUMS').upper()
        depts = Department.query.filter_by(course=course).order_by(Department.order.asc()).all()
        
        dept_data = []
        for d in depts:
            perf = DepartmentPerformance.query.filter_by(student_id=current_user.id, department_id=d.id).first()
            dept_data.append({
                'id': d.id,
                'name': d.name,
                'attendance_rate': perf.attendance_rate if (perf and perf.attendance_rate is not None) else None,
                'item_card_status': perf.item_card_status if perf else 'In Progress'
            })

        return render_template('dashboard.html', departments=dept_data)
    except Exception as e:
        return f"Error loading dashboard: {str(e)}", 500

# ==================== ACADEMIC HUB ====================

@app.route('/academic-hub')
@login_required
def resources():
    course = (current_user.course or 'BUMS').upper()
    folders = FileFolder.query.filter((FileFolder.course == course) | (FileFolder.course == 'ALL')).all()
    files = AcademicFile.query.filter((AcademicFile.course == course) | (AcademicFile.course == 'ALL')).order_by(AcademicFile.id.desc()).all()
    return render_template('resources.html', folders=folders, files=files)

# ==================== ADMIN CONTROL PANEL ====================

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
                    student.attendance = float(new_att) if new_att != '' else None
                    db.session.commit()
                    flash(f"Updated attendance for {student.name_english} ({new_att}%)!", "success")
                except Exception:
                    db.session.rollback()
                    flash("Failed to update attendance.", "danger")
        return redirect(url_for('admin_panel'))

    search_q = request.args.get('q', '').strip()
    course_filter = request.args.get('course', 'ALL')
    
    pending_students = Student.query.filter_by(is_approved=False).order_by(Student.id.desc()).all()

    query = Student.query.filter_by(is_approved=True)
    if course_filter in ['BUMS', 'BAMS']:
        query = query.filter(Student.course == course_filter)
    if search_q:
        query = query.filter(
            (Student.name_english.ilike(f'%{search_q}%')) |
            (Student.email.ilike(f'%{search_q}%')) |
            (Student.roll_no.ilike(f'%{search_q}%')) |
            (Student.unique_id.ilike(f'%{search_q}%'))
        )
    
    approved_students = query.order_by(Student.course, Student.roll_no).all()
    departments = Department.query.order_by(Department.course, Department.order).all()
    folders = FileFolder.query.all()
    files = AcademicFile.query.order_by(AcademicFile.id.desc()).all()
    nav_links = NavigationLink.query.order_by(NavigationLink.order.asc()).all()
    
    return render_template('admin.html',
                           students=approved_students,
                           pending_students=pending_students,
                           departments=departments,
                           folders=folders,
                           files=files,
                           nav_links=nav_links,
                           search_q=search_q,
                           course_filter=course_filter)

# ==================== DOSSIER API (FULL COLUMN MAPPING) ====================

@app.route('/admin/student-detail_<int:id>')
@app.route('/admin/student-detail/<int:id>')
@app.route('/admin/student_detail/<int:id>')
@app.route('/admin/student_details/<int:id>')
@app.route('/admin/get_student/<int:id>')
@app.route('/admin/student/<int:id>/details-json')
@login_required
def admin_get_student_json(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return jsonify({'error': 'Unauthorized'}), 403

    s = Student.query.get_or_404(id)

    photo_url = getattr(s, 'photo', '') or ''
    if photo_url and 'drive.google.com' in photo_url:
        file_id = None
        if 'id=' in photo_url:
            file_id = photo_url.split('id=')[-1].split('&')[0]
        elif '/d/' in photo_url:
            file_id = photo_url.split('/d/')[1].split('/')[0]
        if file_id:
            photo_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w600"

    data = {}
    for column in s.__table__.columns:
        try:
            val = getattr(s, column.name)
            if val is None:
                data[column.name] = "N/A"
            elif hasattr(val, 'strftime'):
                data[column.name] = val.strftime('%Y-%m-%d')
            else:
                data[column.name] = str(val)
        except Exception:
            data[column.name] = "N/A"

    # সঠিকভাবে সঠিক ফিল্ড নিশ্চিত করা (পিতা ও মাতার নাম যেন পেশা বা অন্য কিছু দিয়ে ওভাররাইট না হয়)
    data['id'] = s.id
    data['name'] = getattr(s, 'name_english', None) or getattr(s, 'name', 'N/A')
    data['name_english'] = data['name']
    data['name_bangla'] = getattr(s, 'name_bangla', 'N/A')
    data['father_name'] = getattr(s, 'father_name', 'N/A')
    data['mother_name'] = getattr(s, 'mother_name', 'N/A')
    data['roll_no'] = getattr(s, 'roll_no', 'N/A')
    data['contact_number'] = getattr(s, 'contact_number', 'N/A')
    data['blood_group'] = getattr(s, 'blood_group', 'N/A')
    data['photo'] = photo_url

    return jsonify({
        "status": "success",
        "student": data,
        **data
    })

# ==================== CSV MASTER SYNC (ROBUST PARSER) ====================

@app.route('/admin/secret-sync-now')
@app.route('/admin/run-dossier-sync')
def secret_sync_now():
    csv_file = 'master_students.csv'
    if not os.path.exists(csv_file):
        csv_file = 'students.csv'
    
    csv_processed = 0

    try:
        if os.path.exists(csv_file):
            with open(csv_file, mode='r', encoding='utf-8-sig', errors='ignore') as f:
                content = f.read()

            lines = [l for l in content.strip().splitlines() if l.strip()]
            if lines:
                delimiter = ';' if ';' in lines[0] and ',' not in lines[0] else ','
                reader = csv.DictReader(lines, delimiter=delimiter)

                for row in reader:
                    if not row or not any(row.values()):
                        continue

                    email_val = None
                    class_roll = None
                    detected_course = 'BUMS'

                    for k, v in row.items():
                        if not k or v is None:
                            continue
                        k_clean = k.strip().lower()
                        v_str = str(v).strip()
                        if not v_str:
                            continue

                        if '@' in v_str and '.' in v_str:
                            email_val = v_str
                        elif any(r in k_clean for r in ['class_roll', 'college_roll', 'roll_no', 'বর্তমান রোল', 'roll']) and v_str.isdigit() and len(v_str) <= 3:
                            class_roll = v_str.zfill(2)
                        
                        if any(c in k_clean for c in ['course', 'dept', 'department', 'বিভাগ', 'কোর্স']):
                            if 'ayurved' in v_str.lower() or 'bams' in v_str.lower():
                                detected_course = 'BAMS'
                            elif 'unani' in v_str.lower() or 'bums' in v_str.lower():
                                detected_course = 'BUMS'

                    student = None
                    if email_val:
                        student = Student.query.filter_by(email=email_val).first()
                    if not student and class_roll:
                        student = Student.query.filter_by(roll_no=class_roll).first()

                    if not student:
                        student = Student()
                        db.session.add(student)

                    student.is_approved = True

                    if class_roll:
                        student.roll_no = class_roll
                        student.class_roll = class_roll
                    if email_val:
                        student.email = email_val
                    
                    if hasattr(student, 'course'):
                        student.course = detected_course

                    if hasattr(student, 'unique_id') and class_roll:
                        dept_digit = "2" if detected_course == 'BAMS' else "1"
                        student.unique_id = f"37{dept_digit}{class_roll}"

                    # নিখুঁত ফিল্ড পার্সিং (পিতা/মাতা ও পেশা আলাদা করা)
                    for k, v in row.items():
                        if not k or v is None:
                            continue
                        k_clean = k.strip().lower()
                        v_str = str(v).strip()
                        if not v_str:
                            continue

                        # ফোন নম্বর ফিল্টারিং
                        if (v_str.startswith('01') or v_str.startswith('+8801')) and len(v_str.replace('+88', '')) >= 11:
                            if 'emergency' in k_clean or 'অভিভাবক' in k_clean or 'guardian' in k_clean:
                                if hasattr(student, 'emergency_contact'): student.emergency_contact = v_str
                            else:
                                if hasattr(student, 'contact_number'): student.contact_number = v_str
                            continue

                        if v_str.upper() in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
                            if hasattr(student, 'blood_group'): student.blood_group = v_str.upper()
                            continue

                        if 'drive.google.com' in v_str or 'photo' in k_clean:
                            if hasattr(student, 'photo'): student.photo = v_str
                            continue

                        # সুনির্দিষ্ট ফিল্ড ম্যাপিং
                        if 'father_name' in k_clean or k_clean in ['father', 'পিতা', 'বাবার নাম', 'পিতার নাম']:
                            student.father_name = v_str
                        elif 'mother_name' in k_clean or k_clean in ['mother', 'মাতা', 'মায়ের নাম', 'মায়ের নাম']:
                            student.mother_name = v_str
                        elif 'father_occupation' in k_clean or 'পিতার পেশা' in k_clean:
                            if hasattr(student, 'father_occupation'): student.father_occupation = v_str
                        elif 'mother_occupation' in k_clean or 'মাতার পেশা' in k_clean:
                            if hasattr(student, 'mother_occupation'): student.mother_occupation = v_str
                        elif any(b in k_clean for b in ['bangla', 'বাংলা']) and 'father' not in k_clean and 'mother' not in k_clean:
                            student.name_bangla = v_str
                        elif any(n in k_clean for n in ['name', 'student_name', 'পূর্ণ নাম', 'নাম']) and not any(x in k_clean for x in ['father', 'mother', 'guardian', 'পিতা', 'মাতা', 'অভিভাবক', 'school', 'college', 'bangla', 'বাংলা', 'occupation', 'পেশা']):
                            student.name_english = v_str

                        # বাকি সব ফিল্ড ডাইনামিকালি সেট করা
                        attr = k_clean.replace(' ', '_').replace('-', '_')
                        if hasattr(student, attr) and not getattr(student, attr, None):
                            setattr(student, attr, v_str)

                    csv_processed += 1

        all_students = Student.query.all()
        for idx, s in enumerate(all_students, start=1):
            s.is_approved = True
            c_name = getattr(s, 'course', 'BUMS') or 'BUMS'
            d_code = "2" if c_name == 'BAMS' else "1"
            r_num = getattr(s, 'roll_no', str(idx).zfill(2)) or str(idx).zfill(2)

            if hasattr(s, 'unique_id'):
                s.unique_id = f"37{d_code}{r_num}"

            default_pwd = f"guamc{r_num}"
            if hasattr(s, 'password_hash') and not s.password_hash:
                s.password_hash = generate_password_hash(default_pwd)

        db.session.commit()
        total_students = Student.query.count()
        return f"<h2>All {total_students} Students Cleaned & Synced!</h2><p><b>From CSV:</b> {csv_processed}</p><br><a href='/admin'>Go to Admin Dashboard</a>"

    except Exception as e:
        db.session.rollback()
        return f"<h3>Error:</h3> <p>{str(e)}</p>"

@app.route('/admin/live-attendance', methods=['GET', 'POST'])
@login_required
def admin_live_attendance():
    ADMIN_EMAILS = ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']
    if not current_user.email or current_user.email.lower().strip() not in ADMIN_EMAILS:
        return redirect(url_for('dashboard'))

    selected_course = request.args.get('course', 'BUMS')
    today_date = date.today().strftime('%Y-%m-%d')

    if request.method == 'POST':
        subject_name = request.form.get('subject_name', 'General Session')
        session_date = request.form.get('session_date', today_date)
        students_in_course = Student.query.filter_by(course=selected_course, is_approved=True).all()
        
        updated_count = 0
        for st in students_in_course:
            status = request.form.get(f'status_{st.id}', 'P')
            rec = AttendanceRecord(student_id=st.id, date=session_date, subject=subject_name, status=status)
            db.session.add(rec)
            
            if st.total_classes is None:
                st.total_classes = 0
            if st.attended_classes is None:
                st.attended_classes = 0
            
            st.total_classes += 1
            if status == 'P':
                st.attended_classes += 1
            
            st.attendance = round((st.attended_classes / st.total_classes) * 100, 1) if st.total_classes > 0 else None
            updated_count += 1
            
        db.session.commit()
        flash(f"✅ Live attendance recorded for {updated_count} students ({selected_course})!", "success")
        return redirect(url_for('admin_panel'))

    students = Student.query.filter_by(course=selected_course, is_approved=True).order_by(Student.roll_no).all()
    return render_template('live_attendance.html', students=students, selected_course=selected_course, today_date=today_date)

@app.route('/admin/student/<int:student_id>/performance', methods=['GET', 'POST'])
@login_required
def admin_student_performance(student_id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    
    student = Student.query.get_or_404(student_id)
    depts = Department.query.filter_by(course=student.course).order_by(Department.order.asc()).all()

    if request.method == 'POST':
        try:
            for d in depts:
                att = request.form.get(f'att_{d.id}', '')
                status = request.form.get(f'status_{d.id}', 'In Progress')

                perf = DepartmentPerformance.query.filter_by(student_id=student.id, department_id=d.id).first()
                if not perf:
                    perf = DepartmentPerformance(student_id=student.id, department_id=d.id)
                    db.session.add(perf)
                
                perf.attendance_rate = float(att) if att != '' else None
                perf.item_card_status = status

            db.session.commit()
            flash(f"Departmental evaluation updated for {student.name_english}!", "success")
            return redirect(url_for('admin_panel'))
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to update performance: {str(e)}", "danger")

    perf_map = {}
    for p in student.performances:
        perf_map[p.department_id] = p

    return render_template('student_performance.html', student=student, departments=depts, perf_map=perf_map)

@app.route('/admin/student/approve/<int:id>', methods=['POST'])
@login_required
def admin_approve_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    student.is_approved = True
    db.session.commit()
    flash(f"✅ Approved {student.name_english} (Roll: {student.roll_no})!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/reject/<int:id>', methods=['POST'])
@login_required
def admin_reject_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    db.session.delete(student)
    db.session.commit()
    flash("Registration request rejected & removed.", "warning")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/impersonate/<int:id>')
@login_required
def admin_impersonate_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student_to_view = Student.query.get_or_404(id)
    session['admin_impersonator_email'] = current_user.email
    login_user(student_to_view)
    flash(f"Viewing as: {student_to_view.name_english}", "info")
    return redirect(url_for('dashboard'))

@app.route('/admin/student/exit-impersonate')
@login_required
def admin_exit_impersonate():
    admin_email = session.get('admin_impersonator_email')
    if not admin_email:
        return redirect(url_for('dashboard'))
    admin_user = Student.query.filter(db.func.lower(Student.email) == admin_email.lower().strip()).first()
    if admin_user:
        session.pop('admin_impersonator_email', None)
        login_user(admin_user)
        flash("Returned to Admin Control Panel.", "success")
        return redirect(url_for('admin_panel'))
    return redirect(url_for('login'))

@app.route('/admin/student/edit/<int:id>', methods=['POST'])
@login_required
def admin_edit_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    student.name_english = request.form.get('name_english', student.name_english).strip()
    student.name_bangla = request.form.get('name_bangla', student.name_bangla).strip()
    student.father_name = request.form.get('father_name', student.father_name).strip()
    student.father_occupation = request.form.get('father_occupation', student.father_occupation).strip()
    student.mother_name = request.form.get('mother_name', student.mother_name).strip()
    student.mother_occupation = request.form.get('mother_occupation', student.mother_occupation).strip()
    student.email = request.form.get('email', student.email).strip().lower()
    student.course = request.form.get('course', student.course).strip().upper()
    student.batch = request.form.get('batch', student.batch).strip()
    student.roll_no = request.form.get('roll_no', student.roll_no).strip().zfill(2)
    student.class_roll = student.roll_no
    student.session = request.form.get('session', student.session).strip()
    student.unique_id = generate_diu_id(student.batch, student.course, student.roll_no)
    student.blood_group = request.form.get('blood_group', student.blood_group).strip()
    student.contact_number = request.form.get('contact_number', student.contact_number).strip()
    student.emergency_medical_contact = request.form.get('emergency_medical_contact', student.emergency_medical_contact).strip()
    
    db.session.commit()
    flash(f"Updated profile for {student.name_english}!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    Post.query.filter_by(student_id=student.id).delete()
    db.session.delete(student)
    db.session.commit()
    flash("Student removed.", "warning")
    return redirect(url_for('admin_panel'))

# ==================== DEPARTMENT & FILE MANAGEMENT ====================

@app.route('/admin/department/save', methods=['POST'])
@login_required
def admin_save_department():
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    dept_id = request.form.get('dept_id')
    name = request.form.get('name', '').strip()
    course = request.form.get('course', 'BAMS').strip().upper()
    order = int(request.form.get('order', 0))

    if dept_id:
        dept = Department.query.get(dept_id)
        if dept:
            dept.name = name
            dept.course = course
            dept.order = order
    else:
        db.session.add(Department(name=name, course=course, order=order))
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/folder/add', methods=['POST'])
@login_required
def admin_add_folder():
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    name = request.form.get('folder_name', '').strip()
    course = request.form.get('course', 'ALL').strip().upper()
    if name:
        db.session.add(FileFolder(name=name, course=course))
        db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/file/upload', methods=['POST'])
@login_required
def admin_upload_file():
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    title = request.form.get('title', '').strip()
    file_type = request.form.get('file_type', 'Item Card')
    course = request.form.get('course', 'ALL').upper()
    folder_id = request.form.get('folder_id') or None
    
    file_url = ""
    if 'file' in request.files and request.files['file'].filename != '':
        f = request.files['file']
        filename = f"file_{int(os.urandom(3).hex(), 16)}_{secure_filename(f.filename)}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(filepath)
        file_url = url_for('static', filename=f'uploads/{filename}')
    else:
        file_url = request.form.get('file_url', '').strip()

    if title and file_url:
        db.session.add(AcademicFile(title=title, file_type=file_type, course=course, file_url=file_url, folder_id=folder_id))
        db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/file/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_file(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    f = AcademicFile.query.get_or_404(id)
    db.session.delete(f)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))