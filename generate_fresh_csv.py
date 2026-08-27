import csv
import os
import re

OCCUPATION_KEYWORDS = [
    'farmer', 'farming', 'agriculture', 'housewife', 'house wife', 'homemaker',
    'business', 'businessman', 'business man', 'service', 'job', 'private', 'govt',
    'doctor', 'teacher', 'engineer', 'driver', 'worker', 'retired', 'deceased', 'late',
    'ব্যবসায়ী', 'কৃষি', 'গৃহিনী', 'গৃহিণী', 'চাকুরীজীবী', 'চাকরি', 'student', 'nil', 'none'
]

def is_occupation(text):
    if not text:
        return False
    t = str(text).strip().lower()
    return any(w in t for w in OCCUPATION_KEYWORDS)

def format_phone(raw_val):
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

def process_and_clean():
    src_file = 'master_students.csv' if os.path.exists('master_students.csv') else 'students.csv'
    if not os.path.exists(src_file):
        print(f"Error: {src_file} not found in workspace!")
        return

    with open(src_file, mode='r', encoding='utf-8-sig', errors='ignore') as f:
        reader = list(csv.reader(f))

    if len(reader) < 2:
        print("CSV is empty!")
        return

    headers = [h.strip() for h in reader[0]]
    cleaned_rows = []

    for row in reader[1:]:
        if not row or not any(row):
            continue

        # কলামের হেডার নরম্যালাইজেশন
        row_dict = {}
        for h, val in zip(headers, row):
            clean_key = re.sub(r'[^a-zA-Z0-9]', '', h).lower()
            row_dict[clean_key] = val.strip()

        # ১. রোল ও ইউনিক আইডি
        roll_raw = row_dict.get('classroll', '') or row_dict.get('roll', '')
        roll = re.sub(r'\D', '', roll_raw).zfill(2) if roll_raw else ""

        course_val = row_dict.get('course', 'BUMS').upper()
        course = 'BAMS' if ('AYURVED' in course_val or 'BAMS' in course_val) else 'BUMS'
        batch = row_dict.get('batch', '37th') or '37th'
        
        c_digit = "2" if course == 'BAMS' else "1"
        b_digit = re.sub(r'\D', '', str(batch)) or "37"
        unique_id = f"{b_digit}{c_digit}{roll or '01'}"

        # ২. নাম
        name_en = row_dict.get('nameinenglish', '') or row_dict.get('name', '')
        name_bn = row_dict.get('নামবাংলায়', '') or row_dict.get('নামবাংলা', '')

        # ৩. পিতা ও মাতার তথ্য (ইন্টেলিজেন্ট সোয়াপ ও ক্লিন)
        f_name = row_dict.get('fathersname', '')
        f_occ = row_dict.get('fathersoccupation', '')
        m_name = row_dict.get('mothersname', '')
        m_occ = row_dict.get('mothersoccupation', '')

        if is_occupation(f_name) and not is_occupation(f_occ):
            f_name, f_occ = f_occ, f_name
        elif is_likely := is_occupation(f_name):
            f_occ = f_name
            f_name = ""

        if is_occupation(m_name) and not is_occupation(m_occ):
            m_name, m_occ = m_occ, m_name
        elif is_likely := is_occupation(m_name):
            m_occ = m_name
            m_name = ""

        # ৪. যোগাযোগ ও ফোন নম্বর
        st_phone = format_phone(row_dict.get('yourcontactnumber', '') or row_dict.get('contactnumber', ''))
        f_phone = format_phone(row_dict.get('fatherscontactnumber', ''))
        m_phone = format_phone(row_dict.get('motherscontactnumber', ''))
        guardian_phone = f_phone or m_phone

        # ৫. অন্যান্য ফিল্ড
        email = row_dict.get('emailaddress', '').lower()
        dob = row_dict.get('dateofbirth', '')
        nid = row_dict.get('nidbirthregno', '') or row_dict.get('nid', '')
        gender = row_dict.get('gender', '')
        marital = row_dict.get('maritalstatus', '')
        present_address = row_dict.get('presentaddress', '')
        permanent_address = row_dict.get('permanentaddress', '')

        # ৬. রক্তের গ্রুপ ও ছবির লিঙ্ক
        blood = ""
        photo = ""
        for cell in row:
            val_clean = str(cell).strip()
            if val_clean.upper() in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
                blood = val_clean.upper()
            if 'drive.google.com' in val_clean or 'http' in val_clean:
                photo = val_clean

        cleaned_rows.append({
            'unique_id': unique_id,
            'class_roll': roll,
            'name_english': name_en,
            'name_bangla': name_bn,
            'course': course,
            'batch': batch,
            'email': email,
            'contact_number': st_phone,
            'father_name': f_name,
            'father_occupation': f_occ,
            'father_contact': f_phone,
            'mother_name': m_name,
            'mother_occupation': m_occ,
            'mother_contact': m_phone,
            'guardian_contact': guardian_phone,
            'blood_group': blood,
            'date_of_birth': dob,
            'nid_or_birth_cert': nid,
            'gender': gender,
            'marital_status': marital,
            'present_address': present_address,
            'permanent_address': permanent_address,
            'photo_url': photo
        })

    # ক্লিন করা ফাইল তৈরি
    output_filename = 'clean_master_students.csv'
    fieldnames = list(cleaned_rows[0].keys())
    with open(output_filename, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    print(f"✅ Success! Created '{output_filename}' with {len(cleaned_rows)} completely clean student records.")

if __name__ == '__main__':
    process_and_clean()