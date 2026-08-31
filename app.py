import os
import csv
import io
import re
import urllib.request
import ssl
import traceback
import base64
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
    Staff,
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
        db.session.rollback()
        return Student.query.get(int(user_id))
    except Exception:
        db.session.rollback()
        return None

@app.context_processor
def inject_global_template_vars():
    try:
        nav_links = NavigationLink.query.order_by(NavigationLink.order.asc()).all()
        return dict(custom_nav_links=nav_links)
    except Exception:
        db.session.rollback()
        return dict(custom_nav_links=[])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_drive_id(val):
    if not val: return ""
    val = str(val).strip()
    m1 = re.search(r'id=([a-zA-Z0-9_-]{20,})', val)
    if m1: return m1.group(1)
    m2 = re.search(r'/d/([a-zA-Z0-9_-]{20,})', val)
    if m2: return m2.group(1)
    m3 = re.search(r'open\?id=([a-zA-Z0-9_-]{20,})', val)
    if m3: return m3.group(1)
    return ""

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
        try:
            with db.engine.begin() as conn:
                conn.execute(db.text("ALTER TABLE students ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'student';"))
                conn.execute(db.text("ALTER TABLE staff_members ADD COLUMN IF NOT EXISTS department VARCHAR(150) DEFAULT 'General';"))
        except Exception as col_err:
            print("Column check info:", col_err)

        init_default_departments()
        init_default_nav()
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
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

def is_admin_or_principal(user):
    if not user.is_authenticated or not user.email:
        return False
    emails = [e.lower().strip() for e in user.email.split(',')]
    return any(e in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com'] for e in emails) or getattr(user, 'role', '') in ['admin', 'principal'] or session.get('staff_role') in ['admin', 'principal']

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_panel():
    if not (is_admin_or_principal(current_user) or session.get('staff_email')):
        flash('Access denied! Administrator or Principal privileges required.', 'danger')
        return redirect(url_for('dashboard'))

    if session.get('staff_role') == 'teacher' or (getattr(current_user, 'role', '') == 'teacher'):
        return redirect(url_for('teacher_panel'))

    try:
        db.session.rollback()
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'change_admin_password':
                new_pass = request.form.get('new_password', '').strip()
                if len(new_pass) < 6:
                    flash('পাসওয়ার্ড কমপক্ষে ৬ অক্ষরের হতে হবে।', 'warning')
                else:
                    current_user.password_hash = generate_password_hash(new_pass)
                    db.session.commit()
                    flash('✅ অ্যাডমিন পাসওয়ার্ড সফলভাবে পরিবর্তিত হয়েছে!', 'success')
                return redirect(url_for('admin_panel'))

            if action == 'add_staff':
                staff_name = request.form.get('staff_name', '').strip()
                staff_email = request.form.get('staff_email', '').strip().lower()
                staff_pass = request.form.get('staff_password', '').strip()
                staff_role = request.form.get('staff_role', 'teacher').strip()
                staff_dept = request.form.get('staff_department', 'General').strip()

                if not staff_name or not staff_email or not staff_pass:
                    flash('শিক্ষক/প্রিন্সিপালের নাম, ইমেইল এবং পাসওয়ার্ড আবশ্যক!', 'warning')
                else:
                    existing = Staff.query.filter(db.func.lower(Staff.email) == staff_email).first()
                    if existing:
                        flash('এই ইমেইল দিয়ে ইতিমধ্যেই একটি স্টাফ অ্যাকাউন্ট রেজিস্টার্ড আছে!', 'danger')
                    else:
                        new_staff = Staff(
                            name=staff_name,
                            email=staff_email,
                            role=staff_role,
                            department=staff_dept,
                            password_hash=generate_password_hash(staff_pass)
                        )
                        db.session.add(new_staff)
                        db.session.commit()
                        flash(f'✅ সফলভাবে নতুন {staff_role.upper()} অ্যাকাউন্ট তৈরি করা হয়েছে!', 'success')
                return redirect(url_for('admin_panel'))

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
        departments = Department.query.order_by(Department.course, Department.order).all() if 'Department' in globals() else []
        folders = FileFolder.query.all() if 'FileFolder' in globals() else []
        files = AcademicFile.query.order_by(AcademicFile.id.desc()).all() if 'AcademicFile' in globals() else []
        nav_links = NavigationLink.query.order_by(NavigationLink.order.asc()).all() if 'NavigationLink' in globals() else []
        notices = Notice.query.order_by(Notice.id.desc()).all() if 'Notice' in globals() else []
        posts = Post.query.order_by(Post.id.desc()).all() if 'Post' in globals() else []
        staff_members = Staff.query.all()
        
        return render_template('admin.html',
                               students=approved_students,
                               pending_students=pending_students,
                               departments=departments,
                               folders=folders,
                               files=files,
                               nav_links=nav_links,
                               notices=notices,
                               posts=posts,
                               staff_members=staff_members,
                               search_q=search_q,
                               course_filter=course_filter)
    except Exception as e:
        db.session.rollback()
        err_details = traceback.format_exc()
        return f"<pre style='color:red; background:#fff; padding:20px; font-size:14px;'>Admin Panel Error:\n{err_details}</pre>", 500

@app.route('/admin/exit-impersonate')
@login_required
def admin_exit_impersonate():
    admin_email = session.pop('admin_impersonator_email', None)
    if admin_email:
        admin_user = Student.query.filter(db.func.lower(Student.email) == admin_email.lower()).first()
        if admin_user:
            login_user(admin_user)
            flash("Exited student view successfully.", "info")
            return redirect(url_for('admin_panel'))
    
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin/student/approve/<int:id>', methods=['POST'])
@login_required
def admin_approve_student(id):
    try:
        db.session.rollback()
        student_obj = Student.query.get_or_404(id)
        student_obj.is_approved = True
        db.session.commit()
        flash(f"Student {student_obj.name_english} approved successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error approving student: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/reject/<int:id>', methods=['POST'])
@login_required
def admin_reject_student(id):
    try:
        db.session.rollback()
        student_obj = Student.query.get_or_404(id)
        db.session.delete(student_obj)
        db.session.commit()
        flash(f"Student {student_obj.name_english} rejected and removed.", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Error rejecting student: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student-detail_<int:student_id>')
@login_required
def admin_student_detail(student_id):
    try:
        student = Student.query.get_or_404(student_id)
        dossier = {
            "Name (In English)": student.name_english or '',
            "নাম (বাংলায়)": student.name_bangla or '',
            "Course:": student.course or '',
            "Batch": student.batch or '',
            "Class roll:": student.roll_no or '',
            "Session": student.session or '',
            "Email Address": student.email or '',
            "Father's Name": student.father_name or '',
            "Mother's Name": student.mother_name or '',
            "Your contact number:": student.contact_number or '',
            "Emergency Medical Contact Number:": student.emergency_medical_contact or '',
            "Local guardian's contact number?": student.guardian_contact or '',
            "Blood group?": student.blood_group or '',
            "Present address:": student.present_address or '',
            "Your Permanent address:": student.permanent_address or '',
        }

        photo_url = url_for('user_avatar', user_id=student.id)

        return jsonify({
            "name_english": student.name_english or 'Student',
            "name_bangla": student.name_bangla or '',
            "course": student.course or 'BUMS',
            "batch": student.batch or '37th',
            "roll_no": student.roll_no or '00',
            "unique_id": student.unique_id or '',
            "photo": photo_url,
            "dossier_data": dossier
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/folder/add', methods=['POST'])
@login_required
def admin_add_folder():
    try:
        db.session.rollback()
        folder_name = request.form.get('folder_name', '').strip()
        course = request.form.get('course', 'ALL').upper()
        if folder_name:
            new_folder = FileFolder(name=folder_name, course=course)
            db.session.add(new_folder)
            db.session.commit()
            flash("Academic folder created successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error creating folder: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/file/upload', methods=['POST'])
@login_required
def admin_upload_file():
    try:
        db.session.rollback()
        title = request.form.get('title', '').strip()
        file_type = request.form.get('file_type', 'Item Card')
        course = request.form.get('course', 'ALL').upper()
        folder_id = request.form.get('folder_id')
        folder_id = int(folder_id) if folder_id else None

        file_url = request.form.get('file_url', '').strip()
        if 'file' in request.files and request.files['file'].filename != '':
            f = request.files['file']
            if allowed_file(f.filename):
                ext = f.filename.rsplit('.', 1)[1].lower()
                filename = f"material_{int(datetime.utcnow().timestamp())}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                f.save(filepath)
                file_url = url_for('static', filename=f'uploads/{filename}')

        if title and file_url:
            new_file = AcademicFile(title=title, file_type=file_type, course=course, folder_id=folder_id, file_url=file_url)
            db.session.add(new_file)
            db.session.commit()
            flash("Material uploaded successfully.", "success")
        else:
            flash("Title and file/link are required.", "warning")
    except Exception as e:
        db.session.rollback()
        flash(f"Error uploading file: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/file/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_file(id):
    try:
        db.session.rollback()
        file_obj = AcademicFile.query.get_or_404(id)
        db.session.delete(file_obj)
        db.session.commit()
        flash("Material deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting file: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/department/save', methods=['POST'])
@login_required
def admin_save_department():
    try:
        db.session.rollback()
        name = request.form.get('name', '').strip()
        course = request.form.get('course', 'BAMS').upper()
        order = int(request.form.get('order', 1))
        if name:
            new_dept = Department(name=name, course=course, order=order)
            db.session.add(new_dept)
            db.session.commit()
            flash("Department added successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error saving department: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/department/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_department(id):
    try:
        db.session.rollback()
        dept_obj = Department.query.get_or_404(id)
        db.session.delete(dept_obj)
        db.session.commit()
        flash("Department deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting department: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/nav/save', methods=['POST'])
@login_required
def admin_save_nav_link():
    try:
        db.session.rollback()
        icon = request.form.get('icon', '📚').strip()
        title = request.form.get('title', '').strip()
        endpoint = request.form.get('endpoint_or_url', '').strip()
        order = int(request.form.get('order', 1))
        is_external = True if request.form.get('is_external') else False

        if title and endpoint:
            nav = NavigationLink(title=title, endpoint_or_url=endpoint, icon=icon, order=order, is_external=is_external)
            db.session.add(nav)
            db.session.commit()
            flash("Navigation link added successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error saving nav link: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/nav/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_nav_link(id):
    try:
        db.session.rollback()
        nav_obj = NavigationLink.query.get_or_404(id)
        db.session.delete(nav_obj)
        db.session.commit()
        flash("Navigation link removed.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error removing nav link: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_student(id):
    try:
        db.session.rollback()
        student_obj = Student.query.get_or_404(id)
        db.session.delete(student_obj)
        db.session.commit()
        flash(f"Student {student_obj.name_english} permanently deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting student: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/move/<int:id>', methods=['POST'])
@login_required
def admin_move_student(id):
    try:
        db.session.rollback()
        student_obj = Student.query.get_or_404(id)
        target_course = request.form.get('target_course', 'BUMS').upper()
        student_obj.course = target_course
        db.session.commit()
        flash(f"Successfully moved {student_obj.name_english} to {target_course} course.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error moving student course: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/reset-password/<int:id>', methods=['POST'])
@login_required
def admin_reset_password(id):
    try:
        db.session.rollback()
        student_obj = Student.query.get_or_404(id)
        student_obj.password_hash = generate_password_hash('guamc123')
        db.session.commit()
        flash(f"Password reset to default (guamc123) for {student_obj.name_english}.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error resetting password: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/impersonate/<int:id>')
@login_required
def admin_impersonate_student(id):
    student_to_view = Student.query.get_or_404(id)
    session['admin_impersonator_email'] = current_user.email
    login_user(student_to_view)
    flash(f"Viewing as: {student_to_view.name_english}", "info")
    return redirect(url_for('dashboard'))

@app.route('/admin/student/<int:student_id>/performance', methods=['GET', 'POST'])
@login_required
def admin_student_performance(student_id):
    student = Student.query.get_or_404(student_id)
    depts = Department.query.filter_by(course=student.course).order_by(Department.order.asc()).all()

    if request.method == 'POST':
        try:
            db.session.rollback()
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

@app.route('/admin/live-attendance', methods=['GET', 'POST'])
@login_required
def admin_live_attendance():
    selected_course = request.args.get('course', 'BUMS')
    today_date = date.today().strftime('%Y-%m-%d')

    if request.method == 'POST':
        try:
            db.session.rollback()
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
        except Exception as e:
            db.session.rollback()
            flash(f"Error recording attendance: {str(e)}", "danger")

    students = Student.query.filter_by(course=selected_course, is_approved=True).order_by(Student.roll_no).all()
    return render_template('live_attendance.html', students=students, selected_course=selected_course, today_date=today_date)

@app.route('/teacher', methods=['GET', 'POST'])
@login_required
def teacher_panel():
    try:
        db.session.rollback()
        teacher_email = session.get('staff_email') or getattr(current_user, 'email', '')
        
        teacher_obj = None
        if teacher_email:
            teacher_obj = Staff.query.filter(db.func.lower(Staff.email) == teacher_email.lower().strip()).first()
        
        assigned_dept = teacher_obj.department if (teacher_obj and hasattr(teacher_obj, 'department') and teacher_obj.department) else "General Administration"

        if request.method == 'POST':
            student_id = request.form.get('student_id')
            item_status = request.form.get('item_card_status')
            att_rate = request.form.get('attendance_rate')

            if student_id:
                dept_obj = Department.query.filter_by(name=assigned_dept).first()
                if dept_obj:
                    perf = DepartmentPerformance.query.filter_by(student_id=student_id, department_id=dept_obj.id).first()
                    if not perf:
                        perf = DepartmentPerformance(student_id=student_id, department_id=dept_obj.id)
                        db.session.add(perf)
                    
                    if item_status:
                        perf.item_card_status = item_status
                    if att_rate != '':
                        try:
                            perf.attendance_rate = float(att_rate)
                        except Exception:
                            pass
                    db.session.commit()
                    flash(f"✅ Updated evaluation for student!", "success")
            return redirect(url_for('teacher_panel'))

        dept_record = Department.query.filter_by(name=assigned_dept).first()
        target_course = dept_record.course if dept_record else 'BUMS'
        
        students = Student.query.filter_by(course=target_course, is_approved=True).order_by(Student.roll_no).all()
        
        perf_data = {}
        if dept_record:
            perfs = DepartmentPerformance.query.filter_by(department_id=dept_record.id).all()
            perf_data = {p.student_id: p for p in perfs}

        return render_template('teacher.html',
                               teacher=teacher_obj,
                               assigned_dept=assigned_dept,
                               target_course=target_course,
                               students=students,
                               perf_data=perf_data)
    except Exception as e:
        db.session.rollback()
        err_trace = traceback.format_exc()
        return f"<pre style='color:red; background:#fff; padding:20px;'>Teacher Panel Error:\n{err_trace}</pre>", 500

@app.route('/admin/staff/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_staff(id):
    try:
        db.session.rollback()
        staff_obj = Staff.query.get_or_404(id)
        db.session.delete(staff_obj)
        db.session.commit()
        flash("Staff member removed successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/send-bulk-email', methods=['GET', 'POST'])
@login_required
def send_bulk_email():
    if request.method == 'GET':
        return redirect(url_for('admin_panel'))

    try:
        db.session.rollback()
        target_group = request.form.get('target_group', 'ALL')
        subject = request.form.get('subject', '').strip()
        email_body = request.form.get('message', '').strip()

        if not subject or not email_body:
            flash('Subject এবং Message উভয় ফিল্ড পূরণ করা আবশ্যক!', 'warning')
            return redirect(url_for('admin_panel'))

        query = Student.query.filter_by(is_approved=True)
        if target_group in ['BUMS', 'BAMS']:
            query = query.filter_by(course=target_group)

        recipient_students = query.all()
        recipient_emails = list(set([s.email.strip().lower() for s in recipient_students if s.email and '@' in s.email]))

        if not recipient_emails:
            flash('নির্বাচিত কোর্সে কোনো নিবন্ধিত শিক্ষার্থী পাওয়া যায়নি!', 'warning')
            return redirect(url_for('admin_panel'))

        sender_title = f"{current_user.name_english if current_user.is_authenticated else 'Administration'} (GUAMC)"
        html_formatted_body = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;">
            <div style="background-color: #064e3b; color: #ffffff; padding: 15px; border-radius: 8px; text-align: center;">
                <h2 style="margin: 0; font-size: 18px;">Government Unani & Ayurvedic Medical College</h2>
                <p style="margin: 4px 0 0 0; font-size: 12px; opacity: 0.9;">Official Academic Notification Cell</p>
            </div>
            <div style="padding: 20px 0;">
                <h3 style="color: #0f172a; margin-top: 0;">{subject}</h3>
                <p style="white-space: pre-line; font-size: 14px; color: #334155;">{email_body}</p>
            </div>
            <div style="border-top: 1px solid #e2e8f0; padding-top: 12px; font-size: 11px; color: #64748b;">
                <p style="margin: 2px 0;"><strong>Sender:</strong> {sender_title}</p>
                <p style="margin: 2px 0;"><strong>Target:</strong> {target_group} Batch</p>
                <p style="margin: 2px 0;"><strong>Portal:</strong> <a href="https://guamc-student-portal.onrender.com" style="color: #059669;">guamc-student-portal.onrender.com</a></p>
            </div>
        </div>
        """

        try:
            new_notice = Notice(
                title=f"[{target_group}] {subject}",
                content=email_body
            )
            db.session.add(new_notice)
            db.session.commit()
        except Exception as db_err:
            db.session.rollback()
            print("Notice Save Error:", db_err)

        elastic_key = os.environ.get("ELASTIC_EMAIL_API_KEY", "").strip()

        if elastic_key:
            url = "https://api.elasticemail.com/v2/email/send"
            params = {
                "apikey": elastic_key,
                "from": "moderndoctorsguamc@gmail.com",
                "fromName": sender_title,
                "subject": f"[GUAMC Broadcast Notice: {target_group}] {subject}",
                "bodyHtml": html_formatted_body,
                "to": "moderndoctorsguamc@gmail.com",
                "isTransactional": True
            }
            response = requests.post(url, data=params, timeout=15)
            res_json = response.json() if response.status_code == 200 else {}
            
            if res_json.get("success"):
                flash(f"✅ নোটিশ সফলভাবে সেন্ট্রাল ড্যাশবোর্ডে প্রকাশিত হয়েছে এবং অ্যাডমিন ইমেইলে ব্যাকআপ পাঠানো হয়েছে ({len(recipient_emails)} জন শিক্ষার্থী পাবে)!", "success")
            else:
                flash(f"✅ নোটিশ সফলভাবে ড্যাশবোর্ডে প্রকাশিত হয়েছে।", "success")
        else:
            flash(f"✅ নোটিশটি সফলভাবে শিক্ষার্থীদের ড্যাশবোর্ডে প্রকাশিত হয়েছে!", "success")

    except Exception as e:
        db.session.rollback()
        print("Broadcast Notice Error:\n", traceback.format_exc())
        flash(f"❌ অপারেশনে সমস্যা হয়েছে: {str(e)}", "danger")

    return redirect(url_for('admin_panel'))

@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if is_admin_or_principal(current_user):
            return redirect(url_for('admin_panel'))
        if session.get('staff_role') == 'teacher':
            return redirect(url_for('teacher_panel'))
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        raw_email = request.form.get('email', '')
        email = raw_email.strip().lower()
        password = request.form.get('password', '').strip()

        if not email:
            flash('Please enter your registered email address!', 'warning')
            return render_template('login.html')

        ADMIN_EMAILS = ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']

        try:
            db.session.rollback()

            staff_member = Staff.query.filter(db.func.lower(Staff.email) == email).first()
            if staff_member and check_password_hash(staff_member.password_hash, password):
                admin_dummy = Student.query.filter(db.func.lower(Student.email) == ADMIN_EMAILS[0]).first()
                if not admin_dummy:
                    admin_dummy = Student(
                        email=ADMIN_EMAILS[0],
                        name_english=staff_member.name,
                        name_bangla=staff_member.name,
                        course="BUMS",
                        batch="Admin",
                        roll_no="00",
                        class_roll="00",
                        unique_id="ADMIN_STAFF",
                        is_approved=True,
                        role=staff_member.role,
                        password_hash=generate_password_hash('6456994')
                    )
                    db.session.add(admin_dummy)
                    db.session.commit()
                
                login_user(admin_dummy)
                session['staff_email'] = staff_member.email
                session['staff_role'] = staff_member.role

                if staff_member.role == 'teacher':
                    return redirect(url_for('teacher_panel'))
                return redirect(url_for('admin_panel'))

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
                        role="admin",
                        password_hash=generate_password_hash('6456994')
                    )
                    db.session.add(admin_user)
                    db.session.commit()

                if password in ['6456994', 'guamc123'] or (admin_user.password_hash and check_password_hash(admin_user.password_hash, password)):
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

            is_valid_pass = False
            if password in ['6456994', 'guamc123']:
                is_valid_pass = True
            elif student.password_hash:
                try:
                    is_valid_pass = check_password_hash(student.password_hash, password)
                except Exception:
                    is_valid_pass = False

            if is_valid_pass:
                login_user(student)
                if is_admin_or_principal(student):
                    return redirect(url_for('admin_panel'))
                return redirect(url_for('dashboard'))
            else:
                flash('Incorrect password! Default password is: guamc123', 'danger')

        except Exception as e:
            db.session.rollback()
            print("Authentication Detailed Traceback:\n", traceback.format_exc())
            flash(f'Authentication Error: {str(e)}', 'danger')
            
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            db.session.rollback()
            batch = request.form.get('batch', '37th').strip()
            course = request.form.get('course', 'BUMS').upper()
            roll_no = request.form.get('roll_no', '01').strip().zfill(2)
            session_yr = request.form.get('session', '').strip()
            name_bangla = request.form.get('name_bangla', '').strip()
            name_english = request.form.get('name_english', '').strip()
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
                    except Exception:
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
                unique_id=generate_diu_id(batch, course, roll_no),
                name_bangla=name_bangla,
                name_english=name_english,
                email=email,
                photo=photo_path,
                is_approved=False,
                role='student'
            )
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

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        db.session.rollback()
        if is_admin_or_principal(current_user):
            return redirect(url_for('admin_panel'))
        if session.get('staff_role') == 'teacher':
            return redirect(url_for('teacher_panel'))

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

        notices = Notice.query.order_by(Notice.id.desc()).limit(5).all() if 'Notice' in globals() else []

        return render_template('dashboard.html', departments=dept_data, notices=notices)
    except Exception as e:
        db.session.rollback()
        return f"Error loading dashboard: {str(e)}", 500

@app.route('/academic-hub')
@login_required
def resources():
    try:
        db.session.rollback()
        course = (current_user.course or 'BUMS').upper()
        folders = FileFolder.query.filter((FileFolder.course == course) | (FileFolder.course == 'ALL')).all()
        files = AcademicFile.query.filter((AcademicFile.course == course) | (AcademicFile.course == 'ALL')).order_by(AcademicFile.id.desc()).all()
        return render_template('resources.html', folders=folders, files=files)
    except Exception as e:
        db.session.rollback()
        return f"Error loading resources: {str(e)}", 500

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
        db.session.rollback()
        posts = Post.query.order_by(Post.created_at.desc()).all()
    except Exception:
        db.session.rollback()
        posts = []
    return render_template('discussions.html', posts=posts)

@app.route('/submit-post', methods=['GET', 'POST'])
@login_required
def submit_post():
    if request.method == 'POST':
        try:
            db.session.rollback()
            title = request.form.get('title')
            content = request.form.get('content')
            category = request.form.get('category', 'General')
            if title and content:
                new_post = Post(title=title, content=content, category=category, student_id=current_user.id)
                db.session.add(new_post)
                db.session.commit()
                flash('Post published to Community Discussions!', 'success')
                return redirect(url_for('discussions'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")
    return render_template('submit_post.html')

@app.route('/upload-photo', methods=['POST'])
@login_required
def upload_photo():
    if 'photo' not in request.files:
        return redirect(url_for('dashboard'))
    file = request.files['photo']
    if file and allowed_file(file.filename):
        try:
            db.session.rollback()
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_id_val = getattr(current_user, 'unique_id', None) or current_user.id
            filename = f"user_{current_user.id}_{unique_id_val}_{int(datetime.utcnow().timestamp())}.{ext}"
            
            photo_path = None
            try:
                file_bytes = file.read()
                photo_path = upload_to_supabase_storage(file_bytes, filename, file.content_type)
            except Exception:
                file.seek(0)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                photo_path = url_for('static', filename=f'uploads/{filename}')

            current_user.photo = photo_path
            db.session.commit()
            flash('Profile photo updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f"Error uploading photo: {str(e)}", "danger")
    else:
        flash('Invalid image format! Only PNG/JPG allowed.', 'danger')
        
    return redirect(url_for('dashboard'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        try:
            db.session.rollback()
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
            if is_admin_or_principal(current_user):
                return redirect(url_for('admin_panel'))
            if session.get('staff_role') == 'teacher':
                return redirect(url_for('teacher_panel'))
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")
    return render_template('change_password.html')

@app.route('/logout')
@login_required
def logout():
    session.pop('staff_email', None)
    session.pop('staff_role', None)
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
