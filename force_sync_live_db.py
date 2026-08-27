import os
import re
import pandas as pd
from app import app, db, Student

OCCUPATION_KEYWORDS = [
    'farmer', 'farming', 'agriculture', 'housewife', 'house wife', 'homemaker',
    'business', 'businessman', 'service', 'job', 'private', 'govt',
    'doctor', 'teacher', 'engineer', 'driver', 'worker', 'retired', 'deceased', 'late',
    'ব্যবসায়ী', 'কৃষি', 'গৃহিনী', 'গৃহিণী', 'চাকুরীজীবী', 'চাকরি', 'student', 'none', 'nil'
]

def is_occ(text):
    if not text or pd.isna(text):
        return False
    t = str(text).strip().lower()
    return any(w in t for w in OCCUPATION_KEYWORDS)

def clean_phone(val):
    if not val or pd.isna(val):
        return ""
    digits = re.sub(r'\D', '', str(val).split('.')[0])
    if len(digits) == 10 and digits.startswith('1'):
        return '0' + digits
    if len(digits) == 11 and digits.startswith('01'):
        return digits
    if len(digits) == 13 and digits.startswith('8801'):
        return digits[2:]
    return digits

def run_sync():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = ['clean_master_students.csv', 'master_students.csv', 'students.csv']
    src_file = None
    for c in candidates:
        p = os.path.join(base_dir, c)
        if os.path.exists(p):
            src_file = p
            break

    if not src_file:
        print("❌ No CSV file found!")
        return

    print(f"🔄 Reading from: {src_file}")
    df = pd.read_csv(src_file, dtype=str).fillna('')
    
    # কলামের নাম লোয়ারকেস ও ক্লিন করা
    clean_cols = {col: re.sub(r'[^a-zA-Z0-9]', '', col).lower() for col in df.columns}
    
    with app.app_context():
        print(f"🌐 Connected Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI', '').split('@')[-1]}")
        updated_count = 0
        
        for _, row in df.iterrows():
            # ডিকশনারি ম্যাপিং
            data = {clean_cols[k]: str(v).strip() for k, v in row.items()}
            
            email = data.get('email', '') or data.get('emailaddress', '')
            email = email.lower()
            roll = data.get('classroll', '') or data.get('rollno', '') or data.get('roll', '')
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

            # নাম ও কোর্স
            name_en = data.get('nameenglish', '') or data.get('nameinenglish', '') or data.get('name', '')
            name_bn = data.get('namebangla', '') or data.get('নামবাংলায়', '') or data.get('নামবাংলা', '')
            if name_en: student.name_english = name_en
            if name_bn: student.name_bangla = name_bn

            course_val = data.get('course', 'BUMS').upper()
            student.course = 'BAMS' if ('AYURVED' in course_val or 'BAMS' in course_val) else 'BUMS'
            student.batch = data.get('batch', '37th') or '37th'

            # পিতা ও মাতার তথ্য ইন্টেলিজেন্ট ফিক্স
            f_name = data.get('fathername', '') or data.get('fathersname', '')
            f_occ = data.get('fatheroccupation', '') or data.get('fathersoccupation', '')
            m_name = data.get('mothername', '') or data.get('mothersname', '')
            m_occ = data.get('motheroccupation', '') or data.get('mothersoccupation', '')

            if is_occ(f_name) and not is_occ(f_occ):
                f_name, f_occ = f_occ, f_name
            elif is_occ(f_name):
                f_occ = f_name
                f_name = ""

            if is_occ(m_name) and not is_occ(m_occ):
                m_name, m_occ = m_occ, m_name
            elif is_occ(m_name):
                m_occ = m_name
                m_name = ""

            student.father_name = f_name
            student.mother_name = m_name
            if hasattr(student, 'father_occupation'): student.father_occupation = f_occ
            if hasattr(student, 'mother_occupation'): student.mother_occupation = m_occ

            # ফোন নম্বর
            st_p = clean_phone(data.get('contactnumber', '') or data.get('yourcontactnumber', ''))
            f_p = clean_phone(data.get('fathercontact', '') or data.get('fatherscontactnumber', ''))
            m_p = clean_phone(data.get('mothercontact', '') or data.get('motherscontactnumber', ''))
            g_p = clean_phone(data.get('guardiancontact', '')) or f_p or m_p

            if hasattr(student, 'contact_number') and st_p: student.contact_number = st_p
            if hasattr(student, 'guardian_contact'): student.guardian_contact = g_p
            if hasattr(student, 'emergency_medical_contact'): student.emergency_medical_contact = g_p

            # অন্যান্য তথ্য
            dob = data.get('dateofbirth', '')
            nid = data.get('nidorbirthcert', '') or data.get('nidbirthregno', '')
            if hasattr(student, 'date_of_birth') and dob: student.date_of_birth = dob
            if hasattr(student, 'nid_or_birth_cert') and nid: student.nid_or_birth_cert = nid
            if hasattr(student, 'present_address'): student.present_address = data.get('presentaddress', '')
            if hasattr(student, 'permanent_address'): student.permanent_address = data.get('permanentaddress', '')

            # ব্লাড গ্রুপ ও ফটো
            blood = data.get('bloodgroup', '')
            if blood: student.blood_group = blood
            photo = data.get('photourl', '') or data.get('photo', '')
            if photo: student.photo = photo

            c_digit = "2" if student.course == 'BAMS' else "1"
            b_digit = re.sub(r'\D', '', str(student.batch)) or "37"
            student.unique_id = f"{b_digit}{c_digit}{student.roll_no or '01'}"

            if not student.password_hash:
                student.password_hash = "guamc123"

            updated_count += 1

        db.session.commit()
        print(f"✅ Successfully updated {updated_count} students in live database!")

if __name__ == '__main__':
    run_sync()