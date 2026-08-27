import os
import csv
import re
import urllib.request
import ssl
import traceback
from datetime import datetime, date
from flask import Flask, render_template, redirect, url_for, request, flash, Response, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
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

with app.app_context():
    try:
        db.create_all()
        init_default_departments()
        init_default_nav()
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
                flash('⚠️ Access Restricted! Your account is pending Administrator verification.', 'warning')
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
                flash('This email is already registered!', 'warning')
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

            new_student = Student(
                batch=batch,
                course=course,
                roll_no=roll_no,
                class_roll=roll_no,
                session=session_yr,
                name_bangla=name_bangla,
                name_english=name_english,
                gender=gender,
                marital_status=marital_status,
                father_name=father_name,
                mother_name=mother_name,
                date_of_birth=date_of_birth,
                nid_or_birth_cert=nid_or_birth_cert,
                guardian_contact=guardian_contact,
                present_address=present_address,
                permanent_address=permanent_address,
                email=email,
                photo=photo_path,
                is_approved=False
            )
            
            if hasattr(new_student, 'income_source_details'):
                new_student.income_source_details = f"Father: {father_occupation} | Mother: {mother_occupation}"

            new_student.password_hash = generate_password_hash(password)
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

    try:
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
        departments = Department.query.order_by(Department.course, Department.order).all() if 'Department' in globals() else []
        folders = FileFolder.query.all() if 'FileFolder' in globals() else []
        files = AcademicFile.query.order_by(AcademicFile.id.desc()).all() if 'AcademicFile' in globals() else []
        nav_links = NavigationLink.query.order_by(NavigationLink.order.asc()).all() if 'NavigationLink' in globals() else []
        notices = Notice.query.order_by(Notice.id.desc()).all() if 'Notice' in globals() else []
        posts = Post.query.order_by(Post.id.desc()).all() if 'Post' in globals() else []
        
        return render_template('admin.html',
                               students=approved_students,
                               pending_students=pending_students,
                               departments=departments,
                               folders=folders,
                               files=files,
                               nav_links=nav_links,
                               notices=notices,
                               posts=posts,
                               search_q=search_q,
                               course_filter=course_filter)
    except Exception as e:
        err_details = traceback.format_exc()
        return f"<pre style='color:red; background:#fff; padding:20px; font-size:14px;'>Admin Panel Error:\n{err_details}</pre>", 500

# ==================== DOSSIER API ====================

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

    raw_occ = getattr(s, 'income_source_details', '') or ''
    f_occ = getattr(s, 'father_occupation', None)
    m_occ = getattr(s, 'mother_occupation', None)

    if not f_occ or f_occ == 'N/A' or 'Father:' in str(f_occ):
        if 'Father:' in raw_occ:
            f_occ = raw_occ.split('Father:')[1].split('|')[0].strip()
        else:
            f_occ = raw_occ or "N/A"

    if not m_occ or m_occ == 'N/A' or 'Mother:' in str(m_occ):
        if 'Mother:' in raw_occ:
            m_occ = raw_occ.split('Mother:')[1].split('|')[0].strip()
        else:
            m_occ = "N/A"

    data['id'] = s.id
    data['name'] = getattr(s, 'name_english', None) or getattr(s, 'name', 'N/A')
    data['name_english'] = data['name']
    data['name_bangla'] = getattr(s, 'name_bangla', 'N/A') or 'N/A'
    data['father_name'] = getattr(s, 'father_name', 'N/A') or 'N/A'
    data['mother_name'] = getattr(s, 'mother_name', 'N/A') or 'N/A'
    data['father_occupation'] = f_occ or 'N/A'
    data['mother_occupation'] = m_occ or 'N/A'
    data['income_source_details'] = raw_occ or 'N/A'
    data['roll_no'] = getattr(s, 'roll_no', 'N/A')
    data['session'] = getattr(s, 'session', '2023-24')
    data['batch'] = getattr(s, 'batch', '37th')
    data['contact_number'] = getattr(s, 'contact_number', 'N/A')
    data['guardian_contact'] = getattr(s, 'guardian_contact', None) or getattr(s, 'emergency_medical_contact', 'N/A')
    data['family_income'] = getattr(s, 'family_income', 'N/A')
    data['family_members'] = getattr(s, 'family_members', 'N/A')
    data['present_address'] = getattr(s, 'present_address', 'N/A')
    data['permanent_address'] = getattr(s, 'permanent_address', 'N/A')
    data['nid_or_birth_cert'] = getattr(s, 'nid_or_birth_cert', 'N/A')
    data['date_of_birth'] = getattr(s, 'date_of_birth', 'N/A')
    data['blood_group'] = getattr(s, 'blood_group', 'N/A')
    data['photo'] = photo_url

    return jsonify({
        "status": "success",
        "student": data,
        **data
    })

# ==================== LIVE ATTENDANCE & PERFORMANCE ====================

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
            
            if st.total_classes is None: st.total_classes = 0
            if st.attended_classes is None: st.attended_classes = 0
            
            st.total_classes += 1
            if status == 'P': st.attended_classes += 1
            
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

    perf_map = {p.department_id: p for p in student.performances}
    return render_template('student_performance.html', student=student, departments=depts, perf_map=perf_map)

# ==================== STUDENT ACTIONS (MOVE, COPY, EDIT, APPROVE, DELETE) ====================

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
    student.mother_name = request.form.get('mother_name', student.mother_name).strip()
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
    
    f_occ = request.form.get('father_occupation', '').strip()
    m_occ = request.form.get('mother_occupation', '').strip()
    if hasattr(student, 'income_source_details') and (f_occ or m_occ):
        student.income_source_details = f"Father: {f_occ} | Mother: {m_occ}"
    
    new_custom_pass = request.form.get('custom_password', '').strip()
    if new_custom_pass:
        student.password_hash = generate_password_hash(new_custom_pass)
    
    raw_att = request.form.get('attendance', '')
    student.attendance = float(raw_att) if raw_att != '' else None
    
    db.session.commit()
    flash(f"Updated profile for {student.name_english}!", "success")
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
        mother_name=src.mother_name,
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

@app.route('/admin/student/reset-password/<int:id>', methods=['POST'])
@app.route('/admin/student/reset_password/<int:id>', methods=['POST'])
@login_required
def admin_reset_password(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    student.password_hash = generate_password_hash('guamc123')
    db.session.commit()
    flash(f"Password reset to default 'guamc123' for {student.name_english}", "success")
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
    else:
        db.session.add(Department(name=name, course=course, order=order))
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
    emergency_contact = getattr(current_user, 'emergency_medical_contact', None) or getattr(current_user, 'contact_number', None) or '017XXXXXXXX'
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)