import csv
import os
import re
from app import app, db, Student

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# যে ফাইলগুলো ক্রমানুসারে চেক করবে
candidates = ['students_cleaned_master.csv', 'clean_master_students.csv', 'master_students.csv', 'students.csv']
csv_file = None
for c in candidates:
    p = os.path.join(BASE_DIR, c)
    if os.path.exists(p):
        csv_file = p
        break

if not csv_file:
    print("❌ No CSV source file found!")
    exit(1)

print(f"Reading data from: {csv_file}")

OCCUPATION_KEYWORDS = [
    'farmer', 'farming', 'agriculture', 'housewife', 'house wife', 'homemaker',
    'business', 'businessman', 'business man', 'service', 'job', 'private', 'govt',
    'doctor', 'teacher', 'engineer', 'driver', 'worker', 'retired', 'deceased', 'late',
    'ব্যবসায়ী', 'কৃষি', 'গৃহিনী', 'গৃহিণী', 'চাকুরীজীবী', 'চাকরি', 'student', 'nil', 'none'
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

with open(csv_file, mode='r', encoding='utf-8-sig', errors='ignore') as f:
    reader = list(csv.DictReader(f))

with app.app_context():
    updated = 0
    for row in reader:
        # হেডার নরম্যালাইজেশন (স্পেস, কোলন বা বিশেষ চিহ্ন মুক্ত করা)
        clean_dict = {re.sub(r'[^a-zA-Z0-9]', '', k).lower(): str(v).strip() for k, v in row.items() if k}

        email = (clean_dict.get('email') or clean_dict.get('emailaddress') or '').lower()
        roll_raw = clean_dict.get('classroll') or clean_dict.get('rollno') or clean_dict.get('roll') or ''
        roll = re.sub(r'\D', '', roll_raw).zfill(2) if roll_raw else ""

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

        # নাম ও ভাষা
        name_en = clean_dict.get('nameenglish') or clean_dict.get('nameinenglish') or clean_dict.get('name') or ''
        name_bn = clean_dict.get('namebangla') or clean_dict.get('নামবাংলায়') or clean_dict.get('নামবাংলা') or clean_dict.get('banglaname') or ''
        if name_en:
            student.name_english = name_en
        if name_bn:
            student.name_bangla = name_bn

        # পিতা ও মাতার তথ্য হ্যান্ডলিং
        f_name = clean_dict.get('fathername') or clean_dict.get('fathersname') or ''
        f_occ = clean_dict.get('fatheroccupation') or clean_dict.get('fathersoccupation') or ''
        m_name = clean_dict.get('mothername') or clean_dict.get('mothersname') or ''
        m_occ = clean_dict.get('motheroccupation') or clean_dict.get('mothersoccupation') or ''

        # ইন্টেলিজেন্ট সোয়াপ ডিটেকশন
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

        student.father_name = f_name
        student.mother_name = m_name

        # পেশা ও আয়ের তথ্য income_source_details কলামে সংরক্ষণ
        occ_details = []
        if f_occ:
            occ_details.append(f"Father: {f_occ}")
        if m_occ:
            occ_details.append(f"Mother: {m_occ}")
        
        occ_combined = " | ".join(occ_details)
        if hasattr(student, 'income_source_details'):
            student.income_source_details = occ_combined or f_occ or m_occ

        # যোগাযোগ নম্বর
        contact = format_bd_phone(clean_dict.get('contactnumber') or clean_dict.get('yourcontactnumber') or '')
        f_contact = format_bd_phone(clean_dict.get('fathercontact') or clean_dict.get('fatherscontactnumber') or '')
        m_contact = format_bd_phone(clean_dict.get('mothercontact') or clean_dict.get('motherscontactnumber') or '')
        guardian = format_bd_phone(clean_dict.get('guardiancontact') or '') or f_contact or m_contact

        if hasattr(student, 'contact_number') and contact:
            student.contact_number = contact
        if hasattr(student, 'guardian_contact') and guardian:
            student.guardian_contact = guardian
        if hasattr(student, 'emergency_medical_contact') and guardian:
            student.emergency_medical_contact = guardian

        # অন্যান্য ফিল্ড
        if hasattr(student, 'present_address'):
            student.present_address = clean_dict.get('presentaddress', '')
        if hasattr(student, 'permanent_address'):
            student.permanent_address = clean_dict.get('permanentaddress', '')
        if hasattr(student, 'blood_group'):
            student.blood_group = clean_dict.get('bloodgroup', '')
        if hasattr(student, 'date_of_birth'):
            student.date_of_birth = clean_dict.get('dateofbirth', '')
        if hasattr(student, 'nid_or_birth_cert'):
            student.nid_or_birth_cert = clean_dict.get('nidorbirthcert') or clean_dict.get('nidbirthregno') or clean_dict.get('nid', '')

        # ফটো
        photo_val = clean_dict.get('photo') or clean_dict.get('photourl') or ''
        if photo_val and hasattr(student, 'photo'):
            student.photo = photo_val

        updated += 1

    db.session.commit()
    print(f"🚀 Successfully synced {updated} students with Database!")

    # ভেরিফিকেশন আউটপুট (রোল ০৫)
    s5 = Student.query.filter(Student.roll_no.in_(['05', '5'])).first()
    if s5:
        print("\n--- Verified Record for Roll 05 ---")
        print("Name:", s5.name_english)
        print("Father Name:", s5.father_name)
        print("Mother Name:", s5.mother_name)
        print("Income/Occupation:", getattr(s5, 'income_source_details', 'N/A'))
        print("Guardian Contact:", getattr(s5, 'guardian_contact', 'N/A'))