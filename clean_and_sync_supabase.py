import csv
import os
from app import app, db, Student

def sync_from_clean_csv():
    csv_file = 'clean_master_students.csv'
    
    if not os.path.exists(csv_file):
        print(f"❌ Error: '{csv_file}' not found! Run generate_fresh_csv.py first.")
        return

    with open(csv_file, mode='r', encoding='utf-8-sig') as f:
        reader = list(csv.DictReader(f))

    if not reader:
        print("❌ CSV file is empty!")
        return

    with app.app_context():
        synced_count = 0
        for row in reader:
            if not row:
                continue

            email = (row.get('email') or '').strip().lower()
            roll = (row.get('class_roll') or row.get('roll_no') or '').strip().zfill(2)

            student = None
            if email:
                student = Student.query.filter(db.func.lower(Student.email) == email).first()
            if not student and roll:
                student = Student.query.filter_by(roll_no=roll).first()

            if not student:
                student = Student(email=email or f"student_{roll}@portal.local")
                db.session.add(student)

            # সরাসরি ক্লিন ফিল্ড অ্যাসাইনমেন্ট
            student.is_approved = True
            student.unique_id = row.get('unique_id', '')
            student.roll_no = roll
            student.class_roll = roll
            student.name_english = row.get('name_english', '')
            student.name_bangla = row.get('name_bangla', '')
            student.course = row.get('course', 'BUMS')
            student.batch = row.get('batch', '37th')
            student.session = row.get('session', '')
            student.father_name = row.get('father_name', '')
            student.mother_name = row.get('mother_name', '')
            student.blood_group = row.get('blood_group', '')
            student.photo = row.get('photo_url') or row.get('photo', '')

            # অ্যাডিশনাল প্রোফাইল ফিল্ড
            if hasattr(student, 'father_occupation'): 
                student.father_occupation = row.get('father_occupation', '')
            if hasattr(student, 'mother_occupation'): 
                student.mother_occupation = row.get('mother_occupation', '')
            if hasattr(student, 'contact_number'): 
                student.contact_number = row.get('contact_number', '')
            if hasattr(student, 'guardian_contact'): 
                student.guardian_contact = row.get('guardian_contact', '')
            if hasattr(student, 'emergency_medical_contact'): 
                student.emergency_medical_contact = row.get('guardian_contact', '')
            if hasattr(student, 'date_of_birth'): 
                student.date_of_birth = row.get('date_of_birth', '')
            if hasattr(student, 'nid_or_birth_cert'): 
                student.nid_or_birth_cert = row.get('nid_or_birth_cert', '')
            if hasattr(student, 'gender'): 
                student.gender = row.get('gender', '')
            if hasattr(student, 'marital_status'): 
                student.marital_status = row.get('marital_status', '')
            if hasattr(student, 'present_address'): 
                student.present_address = row.get('present_address', '')
            if hasattr(student, 'permanent_address'): 
                student.permanent_address = row.get('permanent_address', '')

            if not student.password_hash:
                student.password_hash = "guamc123"

            synced_count += 1

        db.session.commit()
        print(f"🚀 Direct Sync Success: {synced_count} students updated from clean CSV!")

if __name__ == '__main__':
    sync_from_clean_csv()