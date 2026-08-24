import csv
import os
import re
from app import app, db, Student

OCCUPATION_KEYWORDS = [
    'farmer', 'farming', 'agriculture', 'housewife', 'house wife', 'homemaker',
    'business', 'businessman', 'business man', 'service', 'job', 'private', 'govt',
    'doctor', 'teacher', 'engineer', 'driver', 'worker', 'retired', 'deceased', 'late',
    'ব্যবসায়ী', 'কৃষি', 'গৃহিনী', 'গৃহিণী', 'চাকুরীজীবী', 'চাকরি'
]

def is_likely_occupation(text):
    if not text:
        return False
    t = str(text).strip().lower()
    return any(word in t for word in OCCUPATION_KEYWORDS)

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

def clean_and_sync():
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
        for row in reader:
            if not row or not any(row.values()):
                continue

            extracted = {
                'email': '', 'roll': '', 'course': 'BUMS', 'batch': '37th', 'session': '',
                'name_en': '', 'name_bn': '', 'gender': '', 'marital_status': '',
                'father_name': '', 'father_occ': '', 'mother_name': '', 'mother_occ': '',
                'dob': '', 'nid': '', 'income': '', 'members': '', 'contact': '',
                'guardian_contact': '', 'emergency_contact': '', 'present_addr': '',
                'permanent_addr': '', 'blood': '', 'photo': ''
            }

            for k, v in row.items():
                if not k or v is None:
                    continue
                k_l = str(k).lower().strip()
                v_s = str(v).strip()
                if not v_s:
                    continue

                if '@' in v_s and '.' in v_s:
                    extracted['email'] = v_s.lower()
                elif any(x in k_l for x in ['class_roll', 'roll_no', 'college_roll', 'রোল', 'roll']) and v_s.isdigit():
                    extracted['roll'] = v_s.zfill(2)
                elif any(x in k_l for x in ['course', 'বিভাগ', 'কোর্স']):
                    extracted['course'] = 'BAMS' if ('ayurved' in v_s.lower() or 'bams' in v_s.lower()) else 'BUMS'
                elif 'batch' in k_l or 'ব্যাচ' in k_l:
                    extracted['batch'] = v_s
                elif 'session' in k_l or 'সেশন' in k_l:
                    extracted['session'] = v_s
                elif any(x in k_l for x in ['gender', 'লিঙ্গ', 'sex']):
                    extracted['gender'] = v_s
                elif any(x in k_l for x in ['marital', 'বৈবাহিক']):
                    extracted['marital_status'] = v_s
                elif any(x in k_l for x in ['father_occupation', 'পিতার পেশা']):
                    extracted['father_occ'] = v_s
                elif any(x in k_l for x in ['father_name', 'পিতার নাম', 'বাবার নাম', 'father', 'পিতা']) and not any(x in k_l for x in ['occup', 'পেশা', 'phone', 'contact', 'number']):
                    extracted['father_name'] = v_s
                elif any(x in k_l for x in ['mother_occupation', 'মাতার পেশা']):
                    extracted['mother_occ'] = v_s
                elif any(x in k_l for x in ['mother_name', 'মাতার নাম', 'মায়ের নাম', 'mother', 'মাতা']) and not any(x in k_l for x in ['occup', 'পেশা', 'phone', 'contact', 'number']):
                    extracted['mother_name'] = v_s
                elif any(x in k_l for x in ['birth', 'dob', 'জন্ম']):
                    extracted['dob'] = v_s
                elif any(x in k_l for x in ['nid', 'birth_cert', 'এনআইডি', 'জন্ম নিবন্ধন']):
                    extracted['nid'] = v_s
                elif any(x in k_l for x in ['income', 'আয়', 'আয়']):
                    extracted['income'] = v_s
                elif any(x in k_l for x in ['member', 'সদস্য']):
                    extracted['members'] = v_s
                elif any(x in k_l for x in ['emergency', 'জরুরি']):
                    extracted['emergency_contact'] = format_bd_phone(v_s)
                elif any(x in k_l for x in ['guardian', 'অভিভাবক']):
                    extracted['guardian_contact'] = format_bd_phone(v_s)
                elif any(x in k_l for x in ['mobile', 'phone', 'contact', 'ফোন', 'মোবাইল', 'যোগাযোগ']):
                    extracted['contact'] = format_bd_phone(v_s)
                elif any(x in k_l for x in ['present_address', 'বর্তমান ঠিকানা', 'present']):
                    extracted['present_addr'] = v_s
                elif any(x in k_l for x in ['permanent_address', 'স্থায়ী ঠিকানা', 'স্থায়ী ঠিকানা', 'permanent']):
                    extracted['permanent_addr'] = v_s
                elif 'blood' in k_l or 'রক্তের গ্রুপ' in k_l or v_s.upper() in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
                    extracted['blood'] = v_s.upper()
                elif 'drive.google.com' in v_s or 'photo' in k_l or 'ছবি' in k_l or 'image' in k_l:
                    extracted['photo'] = v_s
                elif any(x in k_l for x in ['bangla', 'বাংলা']):
                    extracted['name_bn'] = v_s
                elif any(x in k_l for x in ['name', 'নাম']) and not any(x in k_l for x in ['father', 'mother', 'guardian', 'পিতা', 'মাতা', 'অভিভাবক', 'school', 'college', 'bangla', 'বাংলা', 'occupation', 'পেশা']):
                    extracted['name_en'] = v_s

            # Swap Fix: নাম ও পেশার অদলবদল ঠিক করা
            if is_likely_occupation(extracted['father_name']) and not is_likely_occupation(extracted['father_occ']):
                extracted['father_name'], extracted['father_occ'] = extracted['father_occ'], extracted['father_name']
            elif is_likely_occupation(extracted['father_name']):
                extracted['father_occ'] = extracted['father_name']
                extracted['father_name'] = ""

            if is_likely_occupation(extracted['mother_name']) and not is_likely_occupation(extracted['mother_occ']):
                extracted['mother_name'], extracted['mother_occ'] = extracted['mother_occ'], extracted['mother_name']
            elif is_likely_occupation(extracted['mother_name']):
                extracted['mother_occ'] = extracted['mother_name']
                extracted['mother_name'] = ""

            student = None
            if extracted['email']:
                student = Student.query.filter(db.func.lower(Student.email) == extracted['email']).first()
            if not student and extracted['roll']:
                student = Student.query.filter_by(roll_no=extracted['roll']).first()

            if not student:
                student = Student(email=extracted['email'] or f"student_{extracted['roll']}@portal.local")
                db.session.add(student)

            student.is_approved = True
            if extracted['roll']:
                student.roll_no = extracted['roll']
                student.class_roll = extracted['roll']
            if extracted['name_en']: student.name_english = extracted['name_en']
            if extracted['name_bn']: student.name_bangla = extracted['name_bn']
            if extracted['course']: student.course = extracted['course']
            if extracted['batch']: student.batch = extracted['batch']
            if extracted['session']: student.session = extracted['session']
            if extracted['gender'] and hasattr(student, 'gender'): student.gender = extracted['gender']
            if extracted['marital_status'] and hasattr(student, 'marital_status'): student.marital_status = extracted['marital_status']
            if extracted['father_name']: student.father_name = extracted['father_name']
            if extracted['father_occ'] and hasattr(student, 'father_occupation'): student.father_occupation = extracted['father_occ']
            if extracted['mother_name']: student.mother_name = extracted['mother_name']
            if extracted['mother_occ'] and hasattr(student, 'mother_occupation'): student.mother_occupation = extracted['mother_occ']
            if extracted['dob'] and hasattr(student, 'date_of_birth'): student.date_of_birth = extracted['dob']
            if extracted['nid'] and hasattr(student, 'nid_or_birth_cert'): student.nid_or_birth_cert = extracted['nid']
            if extracted['income'] and hasattr(student, 'family_income'): student.family_income = extracted['income']
            if extracted['members'] and hasattr(student, 'family_members'): student.family_members = extracted['members']
            if extracted['contact'] and hasattr(student, 'contact_number'): student.contact_number = extracted['contact']
            if extracted['guardian_contact'] and hasattr(student, 'guardian_contact'): student.guardian_contact = extracted['guardian_contact']
            if extracted['emergency_contact'] and hasattr(student, 'emergency_medical_contact'): student.emergency_medical_contact = extracted['emergency_contact']
            if extracted['present_addr'] and hasattr(student, 'present_address'): student.present_address = extracted['present_addr']
            if extracted['permanent_addr'] and hasattr(student, 'permanent_address'): student.permanent_address = extracted['permanent_addr']
            if extracted['blood']: student.blood_group = extracted['blood']
            if extracted['photo']: student.photo = extracted['photo']

            c_digit = "2" if student.course == 'BAMS' else "1"
            b_digit = re.sub(r'\D', '', str(student.batch)) or "37"
            r_digit = str(student.roll_no or "01").zfill(2)
            student.unique_id = f"{b_digit}{c_digit}{r_digit}"

            if not student.password_hash:
                student.password_hash = "guamc123"

            updated_count += 1

        db.session.commit()
        print(f"✅ Success! All {updated_count} students cleaned and synced to Supabase.")

if __name__ == '__main__':
    clean_and_sync()