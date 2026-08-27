import os
import re
import csv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# লাইভ Supabase ডাটাবেস ইউআরএল সরাসরি সেট করা
SUPABASE_DB_URL = "postgresql://postgres.jtrcajaqybqzzoznsruz:guamcAdmin2026@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"

app = Flask(__name__)
# Render / Supabase এনভায়রনমেন্ট ইউআরএল চেক
db_url = os.environ.get('DATABASE_URL', SUPABASE_DB_URL)
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models import db, Student
db.init_app(app)

OCC_WORDS = [
    'farmer', 'farming', 'agriculture', 'housewife', 'house wife', 'homemaker',
    'business', 'businessman', 'service', 'job', 'private', 'govt',
    'doctor', 'teacher', 'engineer', 'driver', 'worker', 'retired', 'deceased', 'late',
    'ব্যবসায়ী', 'কৃষি', 'গৃহিনী', 'গৃহিণী', 'চাকুরীজীবী', 'student', 'none', 'nil'
]

def is_occ(text):
    if not text: return False
    return any(w in str(text).lower().strip() for w in OCC_WORDS)

with app.app_context():
    print("🌐 Connecting to Remote Live Database...")
    students = Student.query.all()
    print(f"📊 Total Students Found in DB: {len(students)}")
    
    fixed_count = 0
    for s in students:
        f_name = (s.father_name or '').strip()
        m_name = (s.mother_name or '').strip()
        
        f_occ = ""
        m_occ = ""
        
        # পিতার নামের ঘরে পেশা থাকলে সোয়াপ
        if is_occ(f_name):
            f_occ = f_name
            s.father_name = ""
            
        # মাতার নামের ঘরে পেশা থাকলে সোয়াপ
        if is_occ(m_name):
            m_occ = m_name
            s.mother_name = ""

        # পেশার তথ্য income_source_details এ সেট করা
        occ_list = []
        if f_occ: occ_list.append(f"Father: {f_occ}")
        if m_occ: occ_list.append(f"Mother: {m_occ}")
        
        if occ_list and hasattr(s, 'income_source_details'):
            s.income_source_details = " | ".join(occ_list)
            
        fixed_count += 1

    db.session.commit()
    print(f"✅ Successfully cleaned and updated {fixed_count} students directly in Remote Supabase!")

    # রোল ০৫ ভেরিফিকেশন
    s5 = Student.query.filter(Student.roll_no.in_(['05', '5'])).first()
    if s5:
        print("\n--- Verified Live Record for Roll 05 ---")
        print("Name:", s5.name_english)
        print("Father Name:", s5.father_name or "None")
        print("Mother Name:", s5.mother_name or "None")
        print("Details (Occupation):", getattr(s5, 'income_source_details', 'N/A'))
        print("Guardian Contact:", getattr(s5, 'guardian_contact', 'N/A'))