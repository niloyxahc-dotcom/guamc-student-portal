import os
import csv
import re
from datetime import datetime
from werkzeug.security import generate_password_hash
from app import app
from models import db, Student

def clean_phone(val):
    if not val:
        return None
    val = str(val).strip()
    digits = re.sub(r'\D', '', val)
    if digits.startswith('8801') and len(digits) == 13:
        return digits[2:]
    if digits.startswith('1') and len(digits) == 10:
        return '0' + digits
    if digits.startswith('01') and len(digits) == 11:
        return digits
    return val if len(val) <= 15 else None

def clean_drive_url(url):
    if not url:
        return None
    url = str(url).strip()
    m = re.search(r'id=([a-zA-Z0-9_-]{20,})', url) or re.search(r'/d/([a-zA-Z0-9_-]{20,})', url)
    if m:
        return f"https://drive.google.com/thumbnail?id={m.group(1)}&sz=w600"
    return url

def clean_text(val):
    if not val or str(val).strip().lower() in ['none', 'na', 'n/a', 'no', 'nai', '']:
        return None
    return str(val).strip()

def run_sync():
    csv_file = 'master_students.csv'
    if not os.path.exists(csv_file):
        print(f"❌ Error: {csv_file} not found!")
        return

    print("🚀 Starting robust CSV parsing & Supabase sync...")
    
    with app.app_context():
        with open(csv_file, mode='r', encoding='utf-8-sig', errors='ignore') as f:
            reader = csv.DictReader(f)
            
            success_count = 0
            for row in reader:
                # ১. বাধ্যতামূলক তথ্য
                email = str(row.get('Email Address', '')).strip().lower()
                if not email or '@' not in email:
                    continue

                course = str(row.get('Course:', 'BUMS')).strip().upper()
                batch = str(row.get('Batch', '37')).strip()
                name_eng = str(row.get('Name (In English)', '')).strip()
                name_ban = str(row.get('নাম (বাংলায়)', '')).strip()
                
                # রোল নম্বর
                raw_roll = re.sub(r'\D', '', str(row.get('Class roll:', '01')))
                roll_no = raw_roll.zfill(2) if raw_roll else '01'
                
                # DIU / College Unique ID
                dept_code = "2" if "BAMS" in course else "1"
                unique_id = f"37{dept_code}{roll_no}"

                # ২. পিতা-মাতার নাম ও পেশা (১০০% নির্ভুল ম্যাপিং)
                father_name = clean_text(row.get("Father's Name"))
                father_occup = clean_text(row.get("Father's occupation:"))
                mother_name = clean_text(row.get("Mother's Name"))
                mother_occup = clean_text(row.get("Mother's occupation:"))

                # ৩. যোগাযোগ নম্বর
                contact = clean_phone(row.get("Your contact number:"))
                em_contact = clean_phone(row.get("Emergency Medical Contact Number:  অসুস্থতার মতো জরুরি মুহূর্তে দ্রুত যোগাযোগের জন্য নম্বর। ")) or clean_phone(row.get("Father's contact number")) or clean_phone(row.get("Mother's contact number:"))
                guardian_contact = clean_phone(row.get("Local guardian's contact number?"))

                # ৪. ঠিকানা ও ব্যক্তিগত তথ্য
                present_addr = clean_text(row.get("Present address:"))
                permanent_addr = clean_text(row.get("Your Permanent address:"))
                blood = str(row.get("Blood group?", "")).strip().upper()
                if blood not in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
                    blood = None
                
                gender = clean_text(row.get("Gender?"))
                marital = clean_text(row.get("Marital status?"))
                dob = clean_text(row.get("Date of birth"))
                nid = clean_text(row.get("NID/Birth Reg. No"))
                photo = clean_drive_url(row.get("Upload Recent Passport Size Photo "))

                # ৫. ডেটাবেস অবজেক্ট তৈরি বা আপডেট (UPSERT)
                student = Student.query.filter(db.func.lower(Student.email) == email).first()
                if not student:
                    student = Student.query.filter_by(roll_no=roll_no, course=course).first()

                if not student:
                    student = Student(email=email)
                    db.session.add(student)

                student.email = email
                student.course = course
                student.batch = batch
                student.roll_no = roll_no
                student.class_roll = roll_no
                student.unique_id = unique_id
                student.name_english = name_eng
                student.name_bangla = name_ban
                student.father_name = father_name
                student.father_occupation = father_occup
                student.mother_name = mother_name
                student.mother_occupation = mother_occup
                student.contact_number = contact
                student.emergency_medical_contact = em_contact
                student.guardian_contact = guardian_contact
                student.present_address = present_addr
                student.permanent_address = permanent_addr
                student.blood_group = blood
                student.gender = gender
                student.marital_status = marital
                student.date_of_birth = dob
                student.nid_or_birth_cert = nid
                if photo:
                    student.photo = photo
                student.is_approved = True

                # অ্যাডমিন ও ডিফল্ট পাসওয়ার্ড
                if email in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
                    student.password_hash = generate_password_hash('6456994')
                elif not student.password_hash:
                    student.password_hash = generate_password_hash(f"guamc{roll_no}")

                success_count += 1

            db.session.commit()
            print(f"✅ Success! Cleaned & Synced {success_count} students permanently to Supabase.")

if __name__ == '__main__':
    run_sync()