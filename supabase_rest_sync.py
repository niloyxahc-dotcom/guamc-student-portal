import csv
import os
import re
import requests

SUPABASE_URL = "https://jtrcajaqybqzzoznsruz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp0cmNhamFxeWJxenpvem5zcnV6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc1MDUwODQsImV4cCI6MjEwMzA4MTA4NH0.kVlonjuIyEWxPL3aygsyX-UtMBbBL1wZZ2cizHOfq5c"

headers = {
    "apiKey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# সোর্স CSV ফাইল নির্বাচন
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

print(f"📂 Syncing all fields from: {csv_file}")

with open(csv_file, mode='r', encoding='utf-8-sig', errors='ignore') as f:
    reader = list(csv.DictReader(f))

OCCUPATION_KEYWORDS = [
    'farmer', 'farming', 'agriculture', 'housewife', 'house wife', 'homemaker',
    'business', 'businessman', 'service', 'job', 'private', 'govt',
    'doctor', 'teacher', 'engineer', 'driver', 'worker', 'ব্যবসায়ী', 'কৃষি', 'গৃহিনী', 'গৃহিণী', 'চাকুরীজীবী'
]

def is_occ(text):
    if not text: return False
    return any(w in str(text).lower().strip() for w in OCCUPATION_KEYWORDS)

def format_bd_phone(raw_val):
    if not raw_val: return ""
    digits = re.sub(r'\D', '', str(raw_val))
    if len(digits) == 10 and digits.startswith('1'): return '0' + digits
    if len(digits) == 11 and digits.startswith('01'): return digits
    if len(digits) == 13 and digits.startswith('8801'): return digits[2:]
    return str(raw_val).strip()

updated_count = 0

for row in reader:
    # বাংলা ও ইংরেজি সব হেডারের বিশেষ চিহ্ন ও স্পেস রিমুভ করে ক্লিন ডিকশনারি
    clean = {re.sub(r'[^a-zA-Z0-9\u0980-\u09FF]', '', k).lower(): str(v).strip() for k, v in row.items() if k and v}
    
    email = (clean.get('email') or clean.get('emailaddress') or '').lower()
    roll_raw = clean.get('classroll') or clean.get('rollno') or clean.get('roll') or clean.get('রোল') or clean.get('ক্লাসরোল') or ''
    roll = re.sub(r'\D', '', roll_raw).zfill(2) if roll_raw else ""

    if not email and not roll:
        continue

    # ১. নাম (বাংলা ও ইংরেজি)
    name_en = clean.get('nameenglish') or clean.get('nameinenglish') or clean.get('name') or clean.get('ইংরেজি নাম') or ''
    name_bn = clean.get('namebangla') or clean.get('nameinbangla') or clean.get('নামবাংলায়') or clean.get('নামবাংলা') or clean.get('বাংলা নাম') or clean.get('নাম') or ''

    # ২. পিতা ও মাতার নাম এবং পেশা
    f_name = clean.get('fathername') or clean.get('fathersname') or clean.get('পিতারনাম') or clean.get('বাবারনাম') or ''
    f_occ = clean.get('fatheroccupation') or clean.get('fathersoccupation') or clean.get('পিতারপেশা') or clean.get('বাবারপেশা') or ''
    m_name = clean.get('mothername') or clean.get('mothersname') or clean.get('মাতারনাম') or clean.get('মায়েরনাম') or ''
    m_occ = clean.get('motheroccupation') or clean.get('mothersoccupation') or clean.get('মাতারপেশা') or clean.get('মায়েরপেশা') or ''

    # সোয়াপ সংশোধন
    if is_occ(f_name) and not is_occ(f_occ): f_name, f_occ = f_occ, f_name
    elif is_occ(f_name): f_occ, f_name = f_name, ""

    if is_occ(m_name) and not is_occ(m_occ): m_name, m_occ = m_occ, m_name
    elif is_occ(m_name): m_occ, m_name = m_name, ""

    # ৩. সেশন ও ব্যাচ
    session_val = clean.get('session') or clean.get('academicsession') or clean.get('শিক্ষাবর্ষ') or '2023-24'
    batch_val = clean.get('batch') or clean.get('ব্যাচ') or '37th'

    # ৪. যোগাযোগ
    contact = format_bd_phone(clean.get('contactnumber') or clean.get('yourcontactnumber') or clean.get('mobilenumber') or clean.get('ফোন') or clean.get('মোবাইল') or '')
    g_contact = format_bd_phone(clean.get('guardiancontact') or clean.get('fathercontact') or clean.get('fatherscontactnumber') or clean.get('guardianphone') or clean.get('অভিভাবকেরমোবাইল') or '')

    # ৫. পারিবারিক আয় ও সদস্য
    family_income = clean.get('familyincome') or clean.get('monthlyincome') or clean.get('পারিবারিকআয়') or clean.get('মাসিকআয়') or ''
    family_members = clean.get('familymembers') or clean.get('totalfamilymembers') or clean.get('পরিবারেরসদস্য') or ''

    # ৬. ঠিকানা
    present_addr = clean.get('presentaddress') or clean.get('বর্তমানঠিকানা') or ''
    permanent_addr = clean.get('permanentaddress') or clean.get('স্থায়ীঠিকানা') or ''

    # ৭. NID / জন্ম নিবন্ধন & জন্ম তারিখ & রক্তের গ্রুপ
    nid_val = clean.get('nidorbirthcert') or clean.get('nidbirthregno') or clean.get('nid') or clean.get('birthcertificate') or clean.get('জাতীয়পরিচয়পত্র') or clean.get('জন্মনিবন্ধন') or ''
    dob_val = clean.get('dateofbirth') or clean.get('dob') or clean.get('জন্মতারিখ') or ''
    blood_val = clean.get('bloodgroup') or clean.get('blood') or clean.get('রক্তেরগ্রুপ') or ''
    gender_val = clean.get('gender') or clean.get('লিঙ্গ') or ''
    marital_val = clean.get('maritalstatus') or clean.get('বৈবাহিকঅবস্থা') or ''

    # কম্বাইন্ড পেশা ব্যাকআপ
    occ_parts = []
    if f_occ: occ_parts.append(f"Father: {f_occ}")
    if m_occ: occ_parts.append(f"Mother: {m_occ}")
    occ_text = " | ".join(occ_parts)

    payload = {
        'name_english': name_en,
        'name_bangla': name_bn,
        'father_name': f_name,
        'father_occupation': f_occ,
        'mother_name': m_name,
        'mother_occupation': m_occ,
        'income_source_details': occ_text,
        'session': session_val,
        'batch': batch_val,
        'contact_number': contact,
        'guardian_contact': g_contact,
        'emergency_medical_contact': g_contact,
        'family_income': family_income,
        'family_members': family_members,
        'present_address': present_addr,
        'permanent_address': permanent_addr,
        'nid_or_birth_cert': nid_val,
        'date_of_birth': dob_val,
        'blood_group': blood_val,
        'gender': gender_val,
        'marital_status': marital_val
    }

    # যে ভ্যালুগুলো খালি নেই শুধু সেগুলো Supabase-এ প্যাচ করা
    final_payload = {k: v for k, v in payload.items() if v != ''}

    patch_url = None
    if roll:
        patch_url = f"{SUPABASE_URL}/rest/v1/students?roll_no=in.({roll},{str(int(roll))})"
    elif email:
        patch_url = f"{SUPABASE_URL}/rest/v1/students?email=eq.{email}"

    if patch_url:
        res = requests.patch(patch_url, headers=headers, json=final_payload)
        if res.status_code in [200, 204]:
            updated_count += 1

print(f"🚀 Successfully updated ALL fields for {updated_count} students in Supabase!")

# রোল ০৫ লাইভ টেস্ট
test_res = requests.get(f"{SUPABASE_URL}/rest/v1/students?roll_no=in.(05,5)&select=*", headers=headers)
if test_res.status_code == 200 and test_res.json():
    s5 = test_res.json()[0]
    print("\n🎯 --- Verified Live Supabase Record for Roll 05 ---")
    for k, v in s5.items():
        if k in ['name_english', 'name_bangla', 'father_name', 'father_occupation', 'mother_name', 'mother_occupation', 'session', 'batch', 'present_address', 'permanent_address', 'family_income', 'family_members', 'nid_or_birth_cert']:
            print(f"🔹 {k}: {v}")