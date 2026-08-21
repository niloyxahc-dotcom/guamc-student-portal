import os
import pandas as pd
from werkzeug.security import generate_password_hash
from flask import Flask
from models import db, Student, ExamClearance, ExamResult, StudentRepresentative, Notice, Article, VideoVlog, ForumTopic

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///portal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def load_data():
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        # অ্যাডমিন অ্যাকাউন্ট
        admin_user = Student(
            email="admin@guamc.edu.bd",
            name="Principal / Academic Admin",
            course="Administration",
            batch="Faculty",
            roll_no="ADMIN-01",
            phone="01700000000",
            guardian_name="GUAMC Authority",
            address="Mirpur-13, Dhaka-1221",
            ssc_school="N/A",
            ssc_gpa="5.00",
            ssc_year="2010",
            password=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin_user)
        
        # রিপ্রেজেনটেটিভ ও কো-অর্ডিনেটর ডাটা
        reps = [
            StudentRepresentative(course="BUMS", batch="Intern Batch (2025-26)", role_type="Intern Coordinator (Roster Lead)", name="Dr. Mahfuzur Rahman", phone="01711-000111", email="mahfuz.bums@guamc.edu.bd"),
            StudentRepresentative(course="BUMS", batch="Batch 37 (1st Prof)", role_type="Class Representative (CR)", name="Surovy Mony Tusto", phone="01722-111222", email="surovy8182@gmail.com"),
            StudentRepresentative(course="BUMS", batch="Batch 36 (2nd Prof)", role_type="Class Representative (CR)", name="Tanvir Ahmed", phone="01733-222333", email="tanvir.bums@guamc.edu.bd"),
            StudentRepresentative(course="BAMS", batch="Intern Batch (2025-26)", role_type="Intern Coordinator (Roster Lead)", name="Dr. Joyonto Sen", phone="01811-666777", email="joyonto.bams@guamc.edu.bd"),
            StudentRepresentative(course="BAMS", batch="Batch 37 (1st Prof)", role_type="Class Representative (CR)", name="Amitav Roy", phone="01822-777888", email="amitav.bams@guamc.edu.bd"),
            StudentRepresentative(course="BAMS", batch="Batch 36 (2nd Prof)", role_type="Class Representative (CR)", name="Priyanka Das", phone="01833-888999", email="priyanka.bams@guamc.edu.bd"),
        ]
        db.session.add_all(reps)
        
        # ডিফল্ট ভিডিও ভ্লগ ও ফোরাম পোস্ট
        vlogs = [
            VideoVlog(title="Campus Tour & Anatomy Dissection Lab", submitted_by="Academic Cell", video_id="M7lc1UVf-VE"),
            VideoVlog(title="Herbal Garden & Pharmacognosy Study Tour", submitted_by="Batch 36", video_id="dQw4w9WgXcQ")
        ]
        db.session.add_all(vlogs)
        
        sample_topic = ForumTopic(
            title="Clinical correlation between Mizaj (Temperament) and Dosha Prakriti",
            content="How do modern clinical findings correlate with classical Mizaj assessment in BUMS and Dosha analysis in BAMS? Let's discuss clinical case applications.",
            author_name="Academic Research Cell",
            course_tag="General"
        )
        db.session.add(sample_topic)
        
        # শিক্ষার্থীদের লোড করা
        df = pd.read_csv('students.csv')
        df.columns = df.columns.str.strip()
        
        count = 0
        for index, row in df.iterrows():
            email = str(row.get('Email Address', '')).strip()
            name = str(row.get('Name (In English)', '')).strip()
            course = str(row.get('Course:', '')).strip()
            batch = str(row.get('Batch', '')).strip()
            phone = str(row.get('Phone Number (Self):', row.get('Phone', ''))).strip()
            guardian = str(row.get("Father's Name (English):", row.get("Mother's Name (English):", ''))).strip()
            address = str(row.get('Present Address:', '')).strip()
            school = str(row.get('School name', row.get('1.School name', ''))).strip()
            gpa = str(row.get('Result: GPA 5', row.get('3. GPA 5.00', ''))).strip()
            year = str(row.get('Passing year', row.get('2. Passing year', ''))).strip()
            roll = str(row.get('Class Roll', f"GUAMC-{batch}-{index+1:02d}")).strip()
            
            hashed_password = generate_password_hash('guamc123')
            
            if email and email != 'nan':
                student = Student(
                    email=email,
                    name=name,
                    course=course,
                    batch=batch,
                    roll_no=roll,
                    phone=phone if phone != 'nan' else 'N/A',
                    guardian_name=guardian if guardian != 'nan' else 'N/A',
                    address=address if address != 'nan' else 'N/A',
                    ssc_school=school if school != 'nan' else 'N/A',
                    ssc_gpa=gpa if gpa != 'nan' else 'N/A',
                    ssc_year=year if year != 'nan' else 'N/A',
                    password=hashed_password,
                    is_admin=False
                )
                db.session.add(student)
                db.session.flush()
                
                clearance = ExamClearance(
                    student_id=student.id,
                    prof_name="1st Professional Examination",
                    term_1_status="Cleared",
                    term_2_status="In Progress",
                    attendance_pct=86.5,
                    card_completion="Completed",
                    is_eligible=True
                )
                db.session.add(clearance)
                
                sample_results = [
                    ExamResult(student_id=student.id, exam_title="1st Term Assessment", subject="Anatomy & Histology (Tashreeh)", written_marks=72.0, viva_marks=80.0, practical_marks=78.0, total_marks=230.0, status="Honours / Passed"),
                    ExamResult(student_id=student.id, exam_title="1st Term Assessment", subject="Physiology & Biochemistry (Munafeul Aza)", written_marks=68.0, viva_marks=74.0, practical_marks=72.0, total_marks=214.0, status="Passed"),
                    ExamResult(student_id=student.id, exam_title="1st Term Assessment", subject="Basic Principles (Kulliyat/Sanskrit)", written_marks=76.0, viva_marks=82.0, practical_marks=75.0, total_marks=233.0, status="Honours / Passed"),
                ]
                db.session.add_all(sample_results)
                count += 1
        
        db.session.commit()
        print(f"Loaded {count} students with Forum, Vlogs, Results, and CR listings successfully!")

if __name__ == '__main__':
    load_data()