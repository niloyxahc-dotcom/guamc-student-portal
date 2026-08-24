import csv
import os
import re
from app import app, db, Student

def clean_phone(val):
    if not val:
        return ""
    val = str(val).strip()
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

def run_clean_sync():
    csv_file = 'master_students.csv' if os.path.exists('master_students.csv') else 'students.csv'
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found!")
        return

    with app.app_context():
        with open(csv_file, mode='r', encoding='utf-8-sig', errors='ignore') as f:
            content = f.read()

        lines = [l for l in content.strip().splitlines() if l.strip()]
        delimiter = ';' if ';' in lines[0] and ',' not in lines[0] else ','
        reader = csv.DictReader(lines, delimiter=delimiter)

        updated_count = 0
        for r in reader:
            if not r:
                continue

            # হেডার ক্লিন করে ডিকশনারি তৈরি
            data = {re.sub(r'[^a-zA-Z0-9]', '', k).lower(): str(v).strip() for k, v in r.items() if k}

            email = data.get('emailaddress', '').lower()
            roll = data.get('classroll', '') or data.get('roll', '')
            roll = re.sub(r'\D', '', roll).zfill(2) if roll else ""

            if not email and not roll:
                continue

            student = None
            if email:
                student = Student.query.filter(db.func.lower(Student.email) == email).first()
            if not student and roll:
                student = Student.query.filter_by(roll_no=roll).first()

            if not student:
                student = Student(email=email or f"student_{roll}@portal.local")
                db.session.add(student)

            student.is_approved = True
            if roll:
                student.roll_no = roll
                student.class_roll = roll

            # নাম
            name_en = data.get('nameinenglish', '') or data.get('name', '')
            name_bn = data.get('নামবাংলায়', '') or data.get('নামবাংলা', '')
            if name_en: student.name_english = name_en
            if name_bn: student.name_bangla = name_bn

            # কোর্স ও ব্যাচ
            course_val = data.get('course', 'BUMS').upper()
            student.course = 'BAMS' if 'AYURVED' in course_val or 'BAMS' in course_val else 'BUMS'
            student.batch = data.get('batch', '37th') or '37th'
            student.session = data.get('session', '')

            # ইউনিক আইডি
            c_digit = "2" if student.course == 'BAMS' else "1"
            b_digit = re.sub(r'\D', '', str(student.batch)) or "37"
            student.unique_id = f"{b_digit}{c_digit}{student.roll_no or '01'}"

            # পিতা ও মাতার তথ্য (নিখুঁত হেডার ম্যাপিং)
            f_name = data.get('fathersname', '')
            f_occ = data.get('fathersoccupation', '')
            m_name = data.get('mothersname', '')
            m_occ = data.get('mothersoccupation', '')

            if f_name: student.father_name = f_name
            if f_occ and hasattr(student, 'father_occupation'): student.father_occupation = f_occ
            if m_name: student.mother_name = m_name
            if m_occ and hasattr(student, 'mother_occupation'): student.mother_occupation = m_occ

            # ফোন নম্বর
            st_contact = clean_phone(data.get('yourcontactnumber', '') or data.get('contactnumber', ''))
            f_contact = clean_phone(data.get('fatherscontactnumber', ''))
            m_contact = clean_phone(data.get('motherscontactnumber', ''))
            
            if st_contact and hasattr(student, 'contact_number'):
                student.contact_number = st_contact
            if hasattr(student, 'guardian_contact'):
                student.guardian_contact = f_contact or m_contact
            if hasattr(student, 'emergency_medical_contact'):
                student.emergency_medical_contact = f_contact or m_contact or st_contact

            # অন্যান্য তথ্য
            if data.get('dateofbirth', '') and hasattr(student, 'date_of_birth'):
                student.date_of_birth = data.get('dateofbirth', '')
            if data.get('nidbirthregno', '') and hasattr(student, 'nid_or_birth_cert'):
                student.nid_or_birth_cert = data.get('nidbirthregno', '')
            if data.get('gender', '') and hasattr(student, 'gender'):
                student.gender = data.get('gender', '')
            if data.get('maritalstatus', '') and hasattr(student, 'marital_status'):
                student.marital_status = data.get('maritalstatus', '')
            if data.get('presentaddress', '') and hasattr(student, 'present_address'):
                student.present_address = data.get('presentaddress', '')
            if data.get('permanentaddress', '') and hasattr(student, 'permanent_address'):
                student.permanent_address = data.get('permanentaddress', '')

            # রক্ত ও ছবি
            for k, v in r.items():
                if not v: continue
                v_clean = str(v).strip()
                if v_clean.upper() in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
                    student.blood_group = v_clean.upper()
                if 'drive.google.com' in v_clean or 'http' in v_clean:
                    student.photo = v_clean

            if not student.password_hash:
                student.password_hash = "guamc123"

            updated_count += 1

        db.session.commit()
        print(f"✅ Cleaned & permanently updated {updated_count} students to Supabase!")

if __name__ == '__main__':
    run_clean_sync()