import csv
import os
import re
from app import app, db, Student

OCCUPATION_KEYWORDS = [
    'farmer', 'farming', 'agriculture', 'housewife', 'house wife', 'homemaker',
    'business', 'businessman', 'business man', 'service', 'job', 'private', 'govt',
    'doctor', 'teacher', 'engineer', 'driver', 'worker', 'retired', 'deceased', 'late',
    'ব্যবসায়ী', 'কৃষি', 'গৃহিনী', 'গৃহিণী', 'চাকুরীজীবী', 'চাকরি', 'student'
]

def is_likely_occupation(text):
    if not text:
        return False
    t = str(text).strip().lower()
    return any(w in t for w in OCCUPATION_KEYWORDS)

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

def generate_cleaned_master():
    csv_file = 'master_students.csv' if os.path.exists('master_students.csv') else 'students.csv'
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found!")
        return

    with open(csv_file, mode='r', encoding='utf-8-sig', errors='ignore') as f:
        reader = list(csv.reader(f))

    if len(reader) < 2:
        print("CSV file is empty or corrupted!")
        return

    headers = [h.strip() for h in reader[0]]
    cleaned_rows = []

    for row in reader[1:]:
        if not row or not any(row):
            continue

        row_dict = {}
        for h, val in zip(headers, row):
            clean_k = re.sub(r'[^a-zA-Z0-9]', '', h).lower()
            row_dict[clean_k] = val.strip()

        # ফিল্ড এক্সট্র্যাকশন
        email = row_dict.get('emailaddress', '').lower()
        roll_raw = row_dict.get('classroll', '') or row_dict.get('roll', '')
        roll = re.sub(r'\D', '', roll_raw).zfill(2) if roll_raw else ""

        name_en = row_dict.get('nameinenglish', '') or row_dict.get('name', '')
        name_bn = row_dict.get('নামবাংলায়', '') or row_dict.get('নামবাংলা', '') or row_dict.get('banglaname', '')

        course_val = row_dict.get('course', 'BUMS').upper()
        course = 'BAMS' if ('AYURVED' in course_val or 'BAMS' in course_val) else 'BUMS'
        batch = row_dict.get('batch', '37th') or '37th'
        session = row_dict.get('session', '')

        c_digit = "2" if course == 'BAMS' else "1"
        b_digit = re.sub(r'\D', '', str(batch)) or "37"
        unique_id = f"{b_digit}{c_digit}{roll or '01'}"

        f_name = row_dict.get('fathersname', '')
        f_occ = row_dict.get('fathersoccupation', '')
        m_name = row_dict.get('mothersname', '')
        m_occ = row_dict.get('mothersoccupation', '')

        # নাম ও পেশা সোয়াপ ফিক্স
        if is_likely_occupation(f_name) and not is_likely_occupation(f_occ):
            f_name, f_occ = f_occ, f_name
        elif is_likely_occupation(f_name):
            f_occ = f_name
            f_name = ""

        if is_likely_occupation(m_name) and not is_likely_occupation(m_occ):
            m_name, m_occ = m_occ, m_name
        elif is_likely_occupation(m_name):
            m_occ = m_name
            m_name = ""

        contact = format_bd_phone(row_dict.get('yourcontactnumber', '') or row_dict.get('contactnumber', ''))
        f_contact = format_bd_phone(row_dict.get('fatherscontactnumber', ''))
        m_contact = format_bd_phone(row_dict.get('motherscontactnumber', ''))
        guardian_contact = f_contact or m_contact
        emergency_contact = f_contact or m_contact or contact

        dob = row_dict.get('dateofbirth', '')
        nid = row_dict.get('nidbirthregno', '') or row_dict.get('nid', '')
        gender = row_dict.get('gender', '')
        marital = row_dict.get('maritalstatus', '')
        income = row_dict.get('familyincome', '') or row_dict.get('income', '')
        members = row_dict.get('familymembers', '') or row_dict.get('members', '')

        present_addr = row_dict.get('presentaddress', '')
        permanent_addr = row_dict.get('permanentaddress', '')

        blood = ""
        photo = ""
        for cell in row:
            v_c = str(cell).strip()
            if v_c.upper() in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
                blood = v_c.upper()
            if 'drive.google.com' in v_c or 'http' in v_c:
                photo = v_c

        cleaned_rows.append({
            'unique_id': unique_id,
            'roll_no': roll,
            'name_english': name_en,
            'name_bangla': name_bn,
            'course': course,
            'batch': batch,
            'session': session,
            'email': email,
            'contact_number': contact,
            'father_name': f_name,
            'father_occupation': f_occ,
            'mother_name': m_name,
            'mother_occupation': m_occ,
            'guardian_contact': guardian_contact,
            'emergency_medical_contact': emergency_contact,
            'blood_group': blood,
            'date_of_birth': dob,
            'nid_or_birth_cert': nid,
            'gender': gender,
            'marital_status': marital,
            'family_income': income,
            'family_members': members,
            'present_address': present_addr,
            'permanent_address': permanent_addr,
            'photo': photo
        })

    # ১. নতুন ক্লিন করা CSV তৈরি
    out_csv = 'students_cleaned_master.csv'
    fieldnames = list(cleaned_rows[0].keys())
    with open(out_csv, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)
    print(f"✨ Successfully generated cleaned CSV: '{out_csv}' ({len(cleaned_rows)} records)")

    # ২. সরাসরি Supabase ডেটাবেসে সিঙ্ক
    with app.app_context():
        synced_count = 0
        for item in cleaned_rows:
            student = None
            if item['email']:
                student = Student.query.filter(db.func.lower(Student.email) == item['email']).first()
            if not student and item['roll_no']:
                student = Student.query.filter_by(roll_no=item['roll_no']).first()

            if not student:
                student = Student(email=item['email'] or f"student_{item['roll_no']}@portal.local")
                db.session.add(student)

            student.is_approved = True
            student.unique_id = item['unique_id']
            student.roll_no = item['roll_no']
            student.class_roll = item['roll_no']
            student.name_english = item['name_english']
            student.name_bangla = item['name_bangla']
            student.course = item['course']
            student.batch = item['batch']
            student.session = item['session']
            student.father_name = item['father_name']
            student.mother_name = item['mother_name']
            student.blood_group = item['blood_group']
            student.photo = item['photo']

            if hasattr(student, 'father_occupation'): student.father_occupation = item['father_occupation']
            if hasattr(student, 'mother_occupation'): student.mother_occupation = item['mother_occupation']
            if hasattr(student, 'contact_number'): student.contact_number = item['contact_number']
            if hasattr(student, 'guardian_contact'): student.guardian_contact = item['guardian_contact']
            if hasattr(student, 'emergency_medical_contact'): student.emergency_medical_contact = item['emergency_medical_contact']
            if hasattr(student, 'date_of_birth'): student.date_of_birth = item['date_of_birth']
            if hasattr(student, 'nid_or_birth_cert'): student.nid_or_birth_cert = item['nid_or_birth_cert']
            if hasattr(student, 'gender'): student.gender = item['gender']
            if hasattr(student, 'marital_status'): student.marital_status = item['marital_status']
            if hasattr(student, 'family_income'): student.family_income = item['family_income']
            if hasattr(student, 'family_members'): student.family_members = item['family_members']
            if hasattr(student, 'present_address'): student.present_address = item['present_address']
            if hasattr(student, 'permanent_address'): student.permanent_address = item['permanent_address']

            if not student.password_hash:
                student.password_hash = "guamc123"

            synced_count += 1

        db.session.commit()
        print(f"🚀 Database Synced: {synced_count} students updated in Supabase!")

if __name__ == '__main__':
    generate_cleaned_master()