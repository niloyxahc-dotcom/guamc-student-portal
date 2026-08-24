import csv
import os
from app import app, db
from models import Student

def sync_data():
    with app.app_context():
        db.create_all()
        
        csv_file = 'master_students.csv'
        if not os.path.exists(csv_file):
            print(f"File not found: {csv_file}")
            return
            
        print("Clearing old dummy data from database...")
        # পুরোনো ডামি ডেটা মুছে ফ্রেশ করা
        try:
            db.session.query(Student).delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error clearing table: {e}")

        print("Importing fresh data from master_students.csv...")
        count = 0
        with open(csv_file, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # কলামের সম্ভাব্য নামগুলো হ্যান্ডেল করা
                roll = row.get('roll') or row.get('Roll') or row.get('ROLL') or row.get('student_id')
                if not roll:
                    continue
                    
                name_en = row.get('name_english') or row.get('Name') or row.get('name') or row.get('Student Name') or ''
                name_bn = row.get('name_bangla') or row.get('Name (Bangla)') or ''
                email = row.get('personal_email') or row.get('email') or row.get('Email') or ''
                phone = row.get('contact_no') or row.get('phone') or row.get('Phone') or row.get('mobile') or ''
                blood = row.get('blood_group') or row.get('Blood') or row.get('Blood Group') or ''
                course = row.get('course') or row.get('Course') or 'BUMS'
                session = row.get('session') or row.get('Session') or ''

                student = Student(
                    roll=str(roll).strip().zfill(2) if str(roll).strip().isdigit() else str(roll).strip()
                )
                
                # অ্যাট্রিবিউটগুলো সেট করা
                if hasattr(student, 'name_english'): student.name_english = name_en.strip()
                if hasattr(student, 'name_bangla'): student.name_bangla = name_bn.strip()
                if hasattr(student, 'name'): student.name = name_en.strip()
                if hasattr(student, 'personal_email'): student.personal_email = email.strip()
                if hasattr(student, 'email'): student.email = email.strip()
                if hasattr(student, 'contact_no'): student.contact_no = phone.strip()
                if hasattr(student, 'phone'): student.phone = phone.strip()
                if hasattr(student, 'blood_group'): student.blood_group = blood.strip()
                if hasattr(student, 'course'): student.course = course.strip()
                if hasattr(student, 'session'): student.session = session.strip()

                db.session.add(student)
                count += 1

            db.session.commit()
            print(f"Successfully loaded {count} students into database!")

if __name__ == '__main__':
    sync_data()