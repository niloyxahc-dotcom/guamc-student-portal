import csv
import os
import re
from app import app, db, Student

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# সোর্স CSV শনাক্তকরণ
csv_candidates = ['students_cleaned_master.csv', 'clean_master_students.csv', 'master_students.csv', 'students.csv']
src_file = None
for name in csv_candidates:
    p = os.path.join(BASE_DIR, name)
    if os.path.exists(p):
        src_file = p
        break

print("=" * 50)
print(f"📂 SELECTED CSV FILE: {src_file}")

if not src_file:
    print("❌ Error: No CSV file found in project!")
    exit(1)

with open(src_file, mode='r', encoding='utf-8-sig', errors='ignore') as f:
    raw_lines = [l for l in f.read().splitlines() if l.strip()]

reader = list(csv.DictReader(raw_lines))
print(f"📊 Total rows in CSV: {len(reader)}")
print(f"📋 Raw Headers: {list(reader[0].keys()) if reader else 'Empty'}")
print("=" * 50)

OCCUPATION_WORDS = ['farmer', 'farming', 'agriculture', 'housewife', 'house wife', 'homemaker', 'business', 'businessman', 'service', 'job', 'govt', 'doctor', 'teacher', 'driver', 'worker', 'ব্যবসায়ী', 'কৃষি', 'গৃহিনী', 'গৃহিণী', 'চাকুরীজীবী']

def is_occ(val):
    if not val: return False
    v = str(val).lower().strip()
    return any(w in v for w in OCCUPATION_WORDS)

with app.app_context():
    success_count = 0
    for row in reader:
        # সব কলাম থেকে স্পেস ও চিহ্ন সরিয়ে সহজ কি তৈরি
        clean = {re.sub(r'[^a-zA-Z0-9]', '', k).lower(): str(v).strip() for k, v in row.items() if k and v}

        roll_val = clean.get('classroll') or clean.get('rollno') or clean.get('roll') or ''
        roll_digits = re.sub(r'\D', '', roll_val).zfill(2) if roll_val else ""
        
        email_val = (clean.get('email') or clean.get('emailaddress') or '').lower()

        if not roll_digits and not email_val:
            continue

        # স্টুডেন্ট খোঁজা
        st = None
        if roll_digits:
            st = Student.query.filter(Student.roll_no.in_([roll_digits, str(int(roll_digits))])).first()
        if not st and email_val:
            st = Student.query.filter(db.func.lower(Student.email) == email_val).first()

        if not st:
            st = Student(email=email_val or f"student_{roll_digits}@portal.local")
            db.session.add(st)

        st.is_approved = True
        if roll_digits:
            st.roll_no = roll_digits
            st.class_roll = roll_digits

        # নাম
        st.name_english = clean.get('nameenglish') or clean.get('nameinenglish') or clean.get('name') or st.name_english or 'Student'
        st.name_bangla = clean.get('namebangla') or clean.get('নামবাংলায়') or clean.get('নামবাংলা') or getattr(st, 'name_bangla', '')

        # পিতা-মাতার নাম ও পেশা
        f_name = clean.get('fathername') or clean.get('fathersname') or ''
        f_occ = clean.get('fatheroccupation') or clean.get('fathersoccupation') or ''
        m_name = clean.get('mothername') or clean.get('mothersname') or ''
        m_occ = clean.get('motheroccupation') or clean.get('mothersoccupation') or ''

        # সোয়াপ ফিক্স (পিতার নামের ঘরে পেশা থাকলে)
        if is_occ(f_name) and not is_occ(f_occ):
            f_name, f_occ = f_occ, f_name
        elif is_occ(f_name):
            f_occ, f_name = f_name, ""

        if is_occ(m_name) and not is_occ(m_occ):
            m_name, m_occ = m_occ, m_name
        elif is_occ(m_name):
            m_occ, m_name = m_name, ""

        st.father_name = f_name
        st.mother_name = m_name

        combined_occ = f"Father: {f_occ} | Mother: {m_occ}".strip(" |")
        if hasattr(st, 'income_source_details'):
            st.income_source_details = combined_occ or f_occ or m_occ

        # যোগাযোগ
        phone = clean.get('contactnumber') or clean.get('yourcontactnumber') or ''
        g_phone = clean.get('guardiancontact') or clean.get('fathercontact') or clean.get('fatherscontactnumber') or ''
        if hasattr(st, 'contact_number') and phone: st.contact_number = phone
        if hasattr(st, 'guardian_contact') and g_phone: st.guardian_contact = g_phone
        if hasattr(st, 'emergency_medical_contact') and g_phone: st.emergency_medical_contact = g_phone

        # ঠিকানা ও অন্যান্য
        if hasattr(st, 'present_address'): st.present_address = clean.get('presentaddress', '')
        if hasattr(st, 'permanent_address'): st.permanent_address = clean.get('permanentaddress', '')
        if hasattr(st, 'blood_group'): st.blood_group = clean.get('bloodgroup', '')
        if hasattr(st, 'date_of_birth'): st.date_of_birth = clean.get('dateofbirth', '')
        if hasattr(st, 'nid_or_birth_cert'): st.nid_or_birth_cert = clean.get('nidorbirthcert') or clean.get('nidbirthregno') or clean.get('nid', '')

        success_count += 1

    db.session.commit()
    print(f"✅ Successfully updated {success_count} students in Database!")
    print("=" * 50)

    # ভেরিফিকেশন চেক
    s5 = Student.query.filter(Student.roll_no.in_(['05', '5'])).first()
    if s5:
        print("🎯 [FINAL VERIFICATION FOR ROLL 05]")
        print(f"🔹 Name: {s5.name_english}")
        print(f"🔹 Father Name: {s5.father_name}")
        print(f"🔹 Mother Name: {s5.mother_name}")
        print(f"🔹 Income/Occupation: {getattr(s5, 'income_source_details', 'N/A')}")
        print(f"🔹 Guardian Contact: {getattr(s5, 'guardian_contact', 'N/A')}")
    else:
        print("❌ Roll 05 not found in database!")