import os
import csv
import re
import urllib.request
import ssl
from datetime import datetime, date
from flask import Flask, render_template, redirect, url_for, request, flash, Response, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'guamc-master-bulletproof-2026'

basedir = os.path.abspath(os.path.dirname(__file__))

db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or ('sqlite:///' + os.path.join(basedir, 'portal_master_v14_permanent.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'pdf', 'docx', 'xlsx'}

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
    return f"37{c_code}{str(roll_two_digit).zfill(2)}"

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
                    is_new = False
                    if not student:
                        student = Student(email=em)
                        is_new = True
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
        
        # পূর্বের স্ট্যাটিক ৮৫% ক্লিয়ার করে Ongoing করা
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
        return redirect(f"https://ui-avatars.com/api/?name={name}&background=124E3F&color=fff&size=256&bold=true")
    except Exception:
        return redirect("https://ui-avatars.com/api/?name=Student&background=124E3F&color=fff&size=256&bold=true")

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

            student = Student.query.filter(db.func.lower(Student.email) == email).first()

            if not student:
                flash('Invalid email address! Please check your registered email spelling or Sign Up first.', 'danger')
                return render_template('login.html')

            if email in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
                if password == '6456994' or check_password_hash(student.password_hash, password):
                    login_user(student)
                    return redirect(url_for('admin_panel'))
                else:
                    flash('Incorrect password for Administrator!', 'danger')
                    return render_template('login.html')

            if not student.is_approved:
                flash('⚠️ Access Restricted! Your account is pending Administrator approval. Please wait until Admin approves your registration.', 'warning')
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
            name_eng = request.form.get('name_english', '').strip()
            name_ban = request.form.get('name_bangla', '').strip()
            father = request.form.get('father_name', '').strip()
            email = request.form.get('email', '').strip().lower()
            course = request.form.get('course', 'BUMS').upper()
            roll_no = request.form.get('roll_no', '01').strip().zfill(2)
            phone = request.form.get('contact_number', '').strip()
            emergency = request.form.get('emergency_medical_contact', '').strip()
            blood = request.form.get('blood_group', '').strip()
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()

            if not email or not name_eng or not roll_no or not password:
                flash('Please fill in all mandatory fields!', 'warning')
                return render_template('signup.html')

            if password != confirm_password:
                flash('Passwords do not match!', 'danger')
                return render_template('signup.html')

            existing = Student.query.filter(db.func.lower(Student.email) == email).first()
            if existing:
                flash('This email is already registered! Please login or wait for Admin approval.', 'warning')
                return redirect(url_for('login'))

            new_student = Student(
                email=email,
                name_english=name_eng,
                name_bangla=name_ban,
                father_name=father,
                course=course,
                batch='37th',
                roll_no=roll_no,
                class_roll=roll_no,
                unique_id=generate_diu_id('37', course, roll_no),
                contact_number=format_bd_phone(phone),
                emergency_medical_contact=format_bd_phone(emergency),
                blood_group=blood,
                attendance=None,
                is_approved=False,
                password_hash=generate_password_hash(password)
            )
            db.session.add(new_student)
            db.session.commit()

            flash('Registration submitted successfully! Your account is pending Administrator approval. You can log in once approved by the Admin.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error during registration: {str(e)}", 'danger')

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

@app.route('/admin/student/add', methods=['POST'])
@login_required
def admin_add_student():
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    try:
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash('Email is required!', 'danger')
            return redirect(url_for('admin_panel'))
        
        if Student.query.filter_by(email=email).first():
            flash('A student with this email already exists!', 'warning')
            return redirect(url_for('admin_panel'))

        name_eng = request.form.get('name_english', '').strip()
        course = request.form.get('course', 'BUMS').upper()
        roll = request.form.get('roll_no', '01').strip().zfill(2)
        batch = request.form.get('batch', '37th').strip()
        blood = request.form.get('blood_group', '').strip()
        phone = request.form.get('contact_number', '').strip()
        emergency = request.form.get('emergency_medical_contact', '').strip()
        raw_att = request.form.get('attendance', '')
        att = float(raw_att) if raw_att != '' else None

        new_st = Student(
            email=email,
            name_english=name_eng if name_eng else email.split('@')[0].title(),
            course=course,
            batch=batch,
            roll_no=roll,
            class_roll=roll,
            unique_id=generate_diu_id('37', course, roll),
            blood_group=blood,
            contact_number=phone,
            emergency_medical_contact=emergency,
            attendance=att,
            is_approved=True,
            password_hash=generate_password_hash('guamc123')
        )
        db.session.add(new_st)
        db.session.commit()
        flash(f"Student {new_st.name_english} added successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding student: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/edit/<int:id>', methods=['POST'])
@login_required
def admin_edit_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    student.name_english = request.form.get('name_english', student.name_english).strip()
    student.name_bangla = request.form.get('name_bangla', student.name_bangla).strip()
    student.father_name = request.form.get('father_name', student.father_name).strip()
    student.email = request.form.get('email', student.email).strip().lower()
    student.course = request.form.get('course', student.course).strip().upper()
    student.roll_no = request.form.get('roll_no', student.roll_no).strip().zfill(2)
    student.class_roll = student.roll_no
    student.unique_id = generate_diu_id('37', student.course, student.roll_no)
    student.blood_group = request.form.get('blood_group', student.blood_group).strip()
    student.contact_number = request.form.get('contact_number', student.contact_number).strip()
    student.emergency_medical_contact = request.form.get('emergency_medical_contact', student.emergency_medical_contact).strip()
    
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
        student.unique_id = generate_diu_id('37', target_course, student.roll_no)
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
        course=src.course,
        batch=src.batch,
        roll_no=clone_roll,
        class_roll=clone_roll,
        unique_id=generate_diu_id('37', src.course, clone_roll),
        blood_group=src.blood_group,
        contact_number=src.contact_number,
        emergency_medical_contact=src.emergency_medical_contact,
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
        filename = f"file_{int(os.urandom(3).hex(), 16)}_{f.filename}"
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
        filename = f"user_{current_user.id}_{current_user.unique_id}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        current_user.photo = url_for('static', filename=f'uploads/{filename}')
        db.session.commit()
        flash('Profile photo updated successfully!', 'success')
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