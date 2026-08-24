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

# 500 KB Max Upload Size Limit for Storage Economy
app.config['MAX_CONTENT_LENGTH'] = 16 * 1026 * 1024 

UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'pdf', 'docx','jpeg'}

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

            # Auto-create admin if not exists in DB
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

            # Normal student authentication
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

@app.route('/admin/student/<int:id>/details-json')
@login_required
def admin_get_student_json(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return jsonify({'error': 'Unauthorized'}), 403
    s = Student.query.get_or_404(id)
    return jsonify({
        'id': s.id,
        'unique_id': s.unique_id,
        'batch': s.batch,
        'course': s.course,
        'roll_no': s.roll_no,
        'session': s.session or 'N/A',
        'name_english': s.name_english,
        'name_bangla': s.name_bangla or 'N/A',
        'gender': s.gender or 'N/A',
        'marital_status': s.marital_status or 'N/A',
        'father_name': s.father_name or 'N/A',
        'father_occupation': s.father_occupation or 'N/A',
        'mother_name': s.mother_name or 'N/A',
        'mother_occupation': s.mother_occupation or 'N/A',
        'date_of_birth': s.date_of_birth or 'N/A',
        'nid_or_birth_cert': s.nid_or_birth_cert or 'N/A',
        'blood_group': s.blood_group or 'N/A',
        'height': s.height or 'N/A',
        'weight': s.weight or 'N/A',
        'wear_glasses': s.wear_glasses or 'N/A',
        'chronic_illness': s.chronic_illness or 'None',
        'known_allergies': s.known_allergies or 'None',
        'regular_medication': s.regular_medication or 'None',
        'emergency_medical_contact': s.emergency_medical_contact or 'N/A',
        'identification_mark': s.identification_mark or 'N/A',
        'family_income': s.family_income or 'N/A',
        'family_members': s.family_members or 'N/A',
        'need_financial_aid': s.need_financial_aid or 'No',
        'has_personal_income': s.has_personal_income or 'No',
        'income_source_details': s.income_source_details or 'None',
        'hsc_background': s.hsc_background or 'N/A',
        'ssc_background': s.ssc_background or 'N/A',
        'library_member': s.library_member or 'No',
        'hall_resident': s.hall_resident or 'No',
        'co_curricular_activities': s.co_curricular_activities or 'None',
        'club_interests': s.club_interests or 'None',
        'contact_number': s.contact_number or 'N/A',
        'guardian_contact': s.guardian_contact or 'N/A',
        'present_address': s.present_address or 'N/A',
        'permanent_address': s.permanent_address or 'N/A',
        'email': s.email,
        'photo': s.photo or url_for('user_avatar', user_id=s.id)
    })

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
        flash(f"✅ Live attendance recorded for {updated_count} students ({selected_course})! Percentages updated instantly.", "success")
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
    flash(f"✅ Approved {student.name_english} (Roll: {student.roll_no})! Student can now log in.", "success")
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
    flash(f"Viewing as: {student_to_view.name_english} (Roll: {student_to_view.roll_no})", "info")
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
    student.guardian_contact = request.form.get('guardian_contact', student.guardian_contact).strip()
    student.present_address = request.form.get('present_address', student.present_address).strip()
    student.permanent_address = request.form.get('permanent_address', student.permanent_address).strip()
    
    new_custom_pass = request.form.get('custom_password', '').strip()
    if new_custom_pass:
        student.password_hash = generate_password_hash(new_custom_pass)
    
    raw_att = request.form.get('attendance', '')
    student.attendance = float(raw_att) if raw_att != '' else None
        
    db.session.commit()
    flash(f"Updated profile & credentials for {student.name_english}!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/reset-password/<int:id>', methods=['POST'])
@login_required
def admin_reset_password(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    student.password_hash = generate_password_hash('guamc123')
    db.session.commit()
    flash(f"Password reset to default 'guamc123' for {student.name_english}", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/move/<int:id>', methods=['POST'])
@login_required
def admin_move_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    target_course = request.form.get('target_course', '').upper()
    if target_course in ['BUMS', 'BAMS']:
        old_course = student.course
        student.course = target_course
        student.unique_id = generate_diu_id(student.batch, target_course, student.roll_no)
        db.session.commit()
        flash(f"Moved {student.name_english} from {old_course} to {target_course}!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/copy/<int:id>', methods=['POST'])
@login_required
def admin_copy_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    src = Student.query.get_or_404(id)
    clone_roll = f"{int(src.roll_no)+50 if src.roll_no.isdigit() else '99'}".zfill(2)
    clone_email = f"copy_{src.id}_{src.email}"
    clone = Student(
        email=clone_email,
        name_english=f"{src.name_english} (Copy)",
        name_bangla=src.name_bangla,
        father_name=src.father_name,
        father_occupation=src.father_occupation,
        mother_name=src.mother_name,
        mother_occupation=src.mother_occupation,
        course=src.course,
        batch=src.batch,
        roll_no=clone_roll,
        class_roll=clone_roll,
        session=src.session,
        unique_id=generate_diu_id(src.batch, src.course, clone_roll),
        blood_group=src.blood_group,
        contact_number=src.contact_number,
        emergency_medical_contact=src.emergency_medical_contact,
        guardian_contact=src.guardian_contact,
        present_address=src.present_address,
        permanent_address=src.permanent_address,
        attendance=src.attendance,
        is_approved=True,
        photo=src.photo,
        password_hash=src.password_hash or generate_password_hash('guamc123')
    )
    db.session.add(clone)
    db.session.commit()
    flash(f"Cloned copy created for {src.name_english}!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    name = student.name_english
    Post.query.filter_by(student_id=student.id).delete()
    db.session.delete(student)
    db.session.commit()
    flash(f"Deleted {name}.", "warning")
    return redirect(url_for('admin_panel'))

# ==================== DEPARTMENT, FOLDER & FILE MANAGEMENT ====================

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
            flash(f"Department '{name}' updated!", "success")
    else:
        new_dept = Department(name=name, course=course, order=order)
        db.session.add(new_dept)
        flash(f"New Department '{name}' added!", "success")
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/department/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_department(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    dept = Department.query.get_or_404(id)
    db.session.delete(dept)
    db.session.commit()
    flash("Department removed.", "warning")
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
        flash(f"Folder '{name}' created!", "success")
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
        new_file = AcademicFile(title=title, file_type=file_type, course=course, file_url=file_url, folder_id=folder_id)
        db.session.add(new_file)
        db.session.commit()
        flash(f"Material '{title}' uploaded successfully!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/file/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_file(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    f = AcademicFile.query.get_or_404(id)
    db.session.delete(f)
    db.session.commit()
    flash("File removed.", "warning")
    return redirect(url_for('admin_panel'))

@app.route('/admin/navigation/save', methods=['POST'])
@login_required
def admin_save_nav_link():
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    link_id = request.form.get('link_id')
    title = request.form.get('title', '').strip()
    url_val = request.form.get('endpoint_or_url', '').strip()
    icon = request.form.get('icon', '🔗').strip()
    order = int(request.form.get('order', 0))
    is_ext = True if request.form.get('is_external') == 'on' else False

    if link_id:
        link = NavigationLink.query.get(link_id)
        if link:
            link.title = title
            link.endpoint_or_url = url_val
            link.icon = icon
            link.order = order
            link.is_external = is_ext
            flash(f"Nav item '{title}' updated!", "success")
    else:
        new_link = NavigationLink(title=title, endpoint_or_url=url_val, icon=icon, order=order, is_external=is_ext)
        db.session.add(new_link)
        flash(f"Nav item '{title}' added!", "success")
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/navigation/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_nav_link(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    link = NavigationLink.query.get_or_404(id)
    db.session.delete(link)
    db.session.commit()
    flash("Nav item removed.", "info")
    return redirect(url_for('admin_panel'))

# ==================== GENERAL & USER PROFILE ROUTES ====================

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
        return redirect(url_for('dashboard'))
    file = request.files['photo']
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_id_val = getattr(current_user, 'unique_id', None) or current_user.id
        filename = f"user_{current_user.id}_{unique_id_val}_{int(datetime.utcnow().timestamp())}.{ext}"
        
        photo_path = None
        try:
            file_bytes = file.read()
            photo_path = upload_to_supabase_storage(file_bytes, filename, file.content_type)
            if not photo_path:
                raise Exception("Supabase upload returned empty URL")
        except Exception as e:
            print(f"Supabase upload fallback: {e}")
            file.seek(0)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            photo_path = url_for('static', filename=f'uploads/{filename}')

        current_user.photo = photo_path
        db.session.commit()
        flash('Profile photo updated successfully!', 'success')
    else:
        flash('Invalid image format! Only PNG/JPG allowed.', 'danger')
        
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
            flash('Password must be at least 6 characters long.', 'warning')
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
import csv
import os

@app.route('/admin/run-dossier-sync')
@login_required
def run_dossier_sync():
    ADMIN_EMAILS = ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']
    if not current_user.email or current_user.email.lower().strip() not in ADMIN_EMAILS:
        return "Access denied!", 403

    csv_file = 'master_students.csv'
    if not os.path.exists(csv_file):
        return f"Error: {csv_file} not found in root folder!", 404

    with open(csv_file, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        updated_count = 0
        created_count = 0

        for row in reader:
            email = (row.get('Email Address') or '').strip().lower()
            roll_no = (row.get('Class roll:') or row.get('Class Roll') or '').strip()
            
            student = None
            if email:
                student = Student.query.filter(Student.email.ilike(email)).first()
            if not student and roll_no:
                student = Student.query.filter_by(roll_no=roll_no).first()

            if not student:
                student = Student(email=email, is_approved=True)
                db.session.add(student)
                created_count += 1
            else:
                updated_count += 1

            student.name_english = row.get('Name (In English)') or student.name_english
            student.name_bangla = row.get('নাম (বাংলায়)') or student.name_bangla
            student.course = row.get('Course:') or student.course
            student.batch = row.get('Batch') or student.batch or '37th'
            student.roll_no = roll_no or student.roll_no
            student.blood_group = (row.get('Blood group?') or '').strip('? ') or student.blood_group
            student.contact_number = row.get('Your contact number:') or student.contact_number

            em_contact = [v for k, v in row.items() if k and 'Emergency Medical Contact Number' in k]
            student.emergency_medical_contact = em_contact[0] if em_contact and em_contact[0] else student.emergency_medical_contact

            student.gender = row.get('Gender?') or student.gender
            student.marital_status = row.get('Marital status?') or student.marital_status
            student.date_of_birth = row.get('Date of birth') or student.date_of_birth
            student.nid_or_birth_cert = row.get('NID/Birth Reg. No') or student.nid_or_birth_cert
            
            student.father_name = row.get("Father's Name") or student.father_name
            student.father_occupation = row.get("Father's occupation:") or student.father_occupation
            student.mother_name = row.get("Mother's Name") or student.mother_name
            student.mother_occupation = row.get("Mother's occupation:") or student.mother_occupation
            student.guardian_contact = row.get("Father's contact number") or row.get("Mother's contact number:") or row.get("Local guardian's contact number?") or student.guardian_contact
            
            student.height = row.get('Height (in feet & inches)') or student.height
            student.weight = row.get('Weight in kg?') or student.weight

            student.family_income = row.get("Family's monthly income (in Taka)") or student.family_income
            student.family_members = row.get('Member of family (in Number)?') or student.family_members
            student.need_financial_aid = row.get('Do you need any financial aid for educational support?') or student.need_financial_aid
            student.has_personal_income = row.get('Do you have any source of income (e.g., tuition)?') or student.has_personal_income
            student.income_source_details = row.get('If yes, please specify:') or student.income_source_details

            student.ssc_background = row.get('SSC background') or student.ssc_background
            student.hsc_background = row.get('HSC background') or student.hsc_background

            student.chronic_illness = row.get("Any chronic illness or major health conditions? (Write 'None' if NA) ") or student.chronic_illness
            
            allergies = [v for k, v in row.items() if k and 'Known Allergies' in k]
            student.known_allergies = allergies[0] if allergies and allergies[0] else student.known_allergies

            medication = [v for k, v in row.items() if k and 'Regular Medication' in k]
            student.regular_medication = medication[0] if medication and medication[0] else student.regular_medication

            student.library_member = row.get('Are you a member of College Library?') or student.library_member
            student.hall_resident = row.get('Resident of Hall?') or student.hall_resident
            
            clubs = []
            if row.get('Any co-curricular activities? '):
                clubs.append(row.get('Any co-curricular activities? ').strip())
            if row.get('Do you want to join any of the following club?'):
                clubs.append(row.get('Do you want to join any of the following club?').strip())
            student.club_interests = ", ".join(filter(None, clubs)) or student.club_interests

            student.is_approved = True

        db.session.commit()
    
    return f"<h1>✅ Perfect Sync Complete! Updated: {updated_count}, Created: {created_count} students in PostgreSQL!</h1><p><a href='/admin'>Go to Admin Panel</a></p>"

@app.after_request
def add_cache_control(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


    import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import request

# ১. সবার কাছে ওয়েলকাম ইমেইল পাঠানোর রুট
@app.route('/admin/send-all-welcome-emails')
@login_required
def send_all_welcome_emails():
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SENDER_EMAIL = "guamc.aims@gmail.com"
    SENDER_PASSWORD = "kfrzcxchnzijxveo"
    PORTAL_URL = "https://guamc-portal.onrender.com"

    students = Student.query.all()
    results = []
    
    for s in students:
        email = getattr(s, 'personal_email', None) or getattr(s, 'email', None)
        name = getattr(s, 'name_english', None) or getattr(s, 'name_bangla', None) or getattr(s, 'name', 'Student')
        roll = getattr(s, 'roll', 'N/A')
        
        if not email or '@' not in email:
            continue
            
        subject = "Welcome to GUAMC Student Portal - Your Login Access"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #1e293b; line-height: 1.6; background-color: #f1f5f9; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background-color: #ffffff; padding: 30px; border-radius: 16px; border: 1px solid #e2e8f0;">
                <div style="text-align: center; margin-bottom: 25px;">
                    <h2 style="color: #0f766e; margin: 0;">GUAMC Student Portal</h2>
                    <p style="color: #64748b; font-size: 14px;">Government Unani & Ayurvedic Medical College & Hospital</p>
                </div>
                <p>Dear <strong>{name}</strong>,</p>
                <p>Your student profile has been integrated into the official GUAMC Student Portal. You can now log in to view your academic records, attendance, and discussions.</p>
                <div style="background-color: #f8fafc; padding: 20px; border-radius: 12px; margin: 20px 0; border: 1px solid #cbd5e1;">
                    <h4 style="margin-top: 0; color: #0f172a;">Portal Credentials:</h4>
                    <p><strong>URL:</strong> <a href="{PORTAL_URL}">{PORTAL_URL}</a></p>
                    <p><strong>Login Email:</strong> <code>{email}</code></p>
                    <p><strong>Class Roll:</strong> {roll}</p>
                    <p><strong>Default Password:</strong> <code>guamc123</code></p>
                </div>
                <p style="color: #e11d48; font-size: 13px;"><em>* Please change your password after logging in.</em></p>
                <p>Best regards,<br><strong>GUAMC Administration</strong></p>
            </div>
        </body>
        </html>
        """
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"GUAMC Portal Admin <{SENDER_EMAIL}>"
        msg["To"] = email
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, email, msg.as_string())
            results.append(f"✅ Sent: {name} ({email})")
        except Exception as e:
            results.append(f"❌ Failed: {name} ({email}) - {e}")

    return "<h2>Welcome Email Broadcast Complete!</h2><br>" + "<br>".join(results)

# ২. যেকোনো কাস্টম নোটিশ পাঠানোর রুট
@app.route('/admin/send-notice', methods=['GET', 'POST'])
def send_custom_notice():
    if request.method == 'POST':
        notice_subject = request.form.get('subject')
        notice_body = request.form.get('body')
        
        SMTP_SERVER = "smtp.gmail.com"
        SMTP_PORT = 587
        SENDER_EMAIL = "guamc.aims@gmail.com"
        SENDER_PASSWORD = "kfrzcxchnzijxveo"

        students = Student.query.all()
        sent_count = 0
        
        for s in students:
            email = getattr(s, 'personal_email', None) or getattr(s, 'email', None)
            name = getattr(s, 'name_english', None) or getattr(s, 'name_bangla', None) or getattr(s, 'name', 'Student')
            
            if not email or '@' not in email:
                continue
                
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #1e293b; line-height: 1.6; background-color: #f1f5f9; padding: 20px;">
                <div style="max-width: 600px; margin: auto; background-color: #ffffff; padding: 30px; border-radius: 16px; border: 1px solid #e2e8f0;">
                    <div style="text-align: center; margin-bottom: 25px;">
                        <h2 style="color: #0f766e; margin: 0;">GUAMC Notice Board</h2>
                        <p style="color: #64748b; font-size: 14px;">Official Announcement</p>
                    </div>
                    <p>Dear <strong>{name}</strong>,</p>
                    <div style="background-color: #f8fafc; padding: 20px; border-radius: 12px; margin: 20px 0; border: 1px solid #cbd5e1;">
                        <p style="white-space: pre-wrap; margin: 0;">{notice_body}</p>
                    </div>
                    <p>Best regards,<br><strong>GUAMC Administration</strong></p>
                </div>
            </body>
            </html>
            """
            
            msg = MIMEMultipart("alternative")
            msg["Subject"] = notice_subject
            msg["From"] = f"GUAMC Administration <{SENDER_EMAIL}>"
            msg["To"] = email
            msg.attach(MIMEText(html_content, "html"))

            try:
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    server.login(SENDER_EMAIL, SENDER_PASSWORD)
                    server.sendmail(SENDER_EMAIL, email, msg.as_string())
                sent_count += 1
            except Exception as e:
                print(f"Failed: {e}")

        return f"<h3>Successfully sent notice to {sent_count} students!</h3><br><a href='/admin/send-notice'>Send Another Notice</a>"

    return """<div style="max-width: 500px; margin: 50px auto; font-family: Arial; padding: 25px; border: 1px solid #cbd5e1; border-radius: 12px; background: #f8fafc;"><h2 style="color: #0f766e; margin-top: 0;">Send Broadcast Notice to All Students</h2><form method="POST"><label style="font-weight: bold;">Subject:</label><br><input type="text" name="subject" style="width: 100%; padding: 10px; margin: 8px 0 15px 0; border: 1px solid #cbd5e1; border-radius: 6px;" required><br><label style="font-weight: bold;">Notice Message:</label><br><textarea name="body" rows="6" style="width: 100%; padding: 10px; margin: 8px 0 15px 0; border: 1px solid #cbd5e1; border-radius: 6px;" required></textarea><br><button type="submit" style="background: #0f766e; color: white; padding: 12px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold;">Send Notice to All</button></form></div>"""


import csv
import os

@app.route('/admin/secret-sync-now')
def secret_sync_now():
    csv_file = 'master_students.csv'
    if not os.path.exists(csv_file):
        return f"<h3>File Error:</h3> <p>{csv_file} not found in directory.</p>"

    added_count = 0
    updated_count = 0
    raw_preview = []

    try:
        with open(csv_file, mode='r', encoding='utf-8-sig', errors='ignore') as f:
            content = f.read()

        if not content.strip():
            return "<h3>Error:</h3> <p>master_students.csv is empty!</p>"

        # ডিলিমিটার ডিটেক্ট করা (, নাকি ;)
        first_line = content.strip().split('\n')[0]
        delimiter = ';' if ';' in first_line and ',' not in first_line else ','
        
        lines = content.strip().splitlines()
        reader = csv.DictReader(lines, delimiter=delimiter)
        headers = reader.fieldnames or []

        for row in reader:
            if not row:
                continue
            
            # কোনো না কোনো ফিল্ড থেকে রোল নম্বর খুঁজে বের করা
            roll_val = None
            for k, v in row.items():
                if k and any(x in k.lower() for x in ['roll', 'id', 'student_id', 'class_roll']) and v:
                    roll_val = v
                    break
            
            # রোল না পেলে প্রথম কলামের মানকে রোল হিসেবে ধরা
            if not roll_val:
                vals = [v for v in row.values() if v]
                if vals:
                    roll_val = vals[0]

            if not roll_val:
                continue

            roll_str = str(roll_val).strip()
            if roll_str.isdigit():
                roll_str = roll_str.zfill(2)

            student = Student.query.filter_by(roll_no=roll_str).first()
            if not student:
                student = Student(roll_no=roll_str)
                db.session.add(student)
                added_count += 1
            else:
                updated_count += 1

            for col_name, val in row.items():
                if not col_name or not val or str(val).strip() == '':
                    continue
                
                v_str = str(val).strip()
                c_clean = col_name.strip().lower().replace(' ', '_')

                if c_clean == 'id':
                    if hasattr(student, 'unique_id') and not student.unique_id:
                        student.unique_id = v_str
                    continue

                if hasattr(student, c_clean) and not getattr(student, c_clean, None):
                    setattr(student, c_clean, v_str)
                
                # কমন ফিল্ড অ্যাসাইনমেন্ট
                if ('name' in c_clean and 'bangla' not in c_clean) and hasattr(student, 'name_english') and not student.name_english:
                    student.name_english = v_str
                elif 'bangla' in c_clean and hasattr(student, 'name_bangla') and not student.name_bangla:
                    student.name_bangla = v_str
                elif ('phone' in c_clean or 'contact' in c_clean or 'mobile' in c_clean) and hasattr(student, 'contact_number') and not student.contact_number:
                    student.contact_number = v_str
                elif 'blood' in c_clean and hasattr(student, 'blood_group') and not student.blood_group:
                    student.blood_group = v_str

        db.session.commit()
        return f"<h2>Sync Successful!</h2><p><b>Headers:</b> {headers}</p><p><b>Added New:</b> {added_count}</p><p><b>Updated/Preserved:</b> {updated_count}</p><br><a href='/admin'>Go to Admin Portal</a>"

    except Exception as e:
        db.session.rollback()
        return f"<h3>Error:</h3> <p>{str(e)}</p>"