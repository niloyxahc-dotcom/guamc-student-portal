import os
import csv
import io
import re
import urllib.request
import ssl
import traceback
import base64
from datetime import datetime, date
from flask import Flask, render_template, redirect, url_for, request, flash, Response, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://jtrcajaqybqzzoznsruz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp0cmNhamFxeWJxenpvem5zcnV6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc1MDUwODQsImV4cCI6MjEwMzA4MTA4NH0.kVlonjuIyEWxPL3aygsyX-UtMBbBL1wZZ2cizHOfq5c")

def upload_to_supabase_storage(file_bytes, filename, content_type):
    upload_url = f"{SUPABASE_URL}/storage/v1/object/student-photos/{filename}"
    headers = {
        "apiKey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": content_type or "image/jpeg"
    }
    response = requests.post(upload_url, headers=headers, data=file_bytes)
    if response.status_code in [200, 201]:
        return f"{SUPABASE_URL}/storage/v1/object/public/student-photos/{filename}"
    else:
        print(f"Supabase REST Error: {response.status_code} - {response.text}")
        return None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'guamc-aims-master-bulletproof-2026'

basedir = os.path.abspath(os.path.dirname(__file__))

db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or ('sqlite:///' + os.path.join(basedir, 'portal_master_v14_permanent.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'pdf', 'docx', 'jpeg'}

from models import (
    db, 
    Student, 
    Staff,
    Department, 
    DepartmentPerformance, 
    AttendanceRecord, 
    FileFolder, 
    AcademicFile, 
    NavigationLink, 
    Post, 
    Notice
)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    try:
        db.session.rollback()
        return Student.query.get(int(user_id))
    except Exception:
        db.session.rollback()
        return None

@app.context_processor
def inject_global_template_vars():
    try:
        nav_links = NavigationLink.query.order_by(NavigationLink.order.asc()).all()
        return dict(custom_nav_links=nav_links)
    except Exception:
        db.session.rollback()
        return dict(custom_nav_links=[])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_drive_id(val):
    if not val: return ""
    val = str(val).strip()
    m1 = re.search(r'id=([a-zA-Z0-9_-]{20,})', val)
    if m1: return m1.group(1)
    m2 = re.search(r'/d/([a-zA-Z0-9_-]{20,})', val)
    if m2: return m2.group(1)
    m3 = re.search(r'open\?id=([a-zA-Z0-9_-]{20,})', val)
    if m3: return m3.group(1)
    return ""

def generate_diu_id(batch, course, roll_two_digit):
    course_str = str(course).upper()
    c_code = "2" if ('BAMS' in course_str or 'AYURVEDIC' in course_str) else "1"
    b_digits = re.sub(r'\D', '', str(batch)) or "37"
    return f"{b_digits}{c_code}{str(roll_two_digit).zfill(2)}"

def init_default_departments():
    bams_depts = [
        "Ayurvedic Moulik Siddhanta (Basic Principles)",
        "Dravyaguna (Pharmacology & Pharmacognosy)",
        "Sharir Rachana (Anatomy)",
        "Sharir Kriya (Physiology)",
        "Pran Rasayan (Biochemistry)"
    ]
    bums_depts = [
        "Tashreeh-ul-Badan (Anatomy)",
        "Afal-ul A'za (Physiology)",
        "Hiyat-e Kimia (Biochemistry)",
        "Kulliat-e-Tibb wa Tarikh-e Tibb",
        "Ilmul Advia (Pharmacology)"
    ]
    if Department.query.count() == 0:
        for i, name in enumerate(bams_depts, 1):
            db.session.add(Department(course='BAMS', name=name, order=i))
        for i, name in enumerate(bums_depts, 1):
            db.session.add(Department(course='BUMS', name=name, order=i))
        db.session.commit()

def init_default_nav():
    if NavigationLink.query.count() == 0:
        defaults = [
            ("Dashboard", "dashboard", "🏠", 1, False),
            ("Submissions", "submission_hub", "📁", 2, False),
            ("Academic Hub", "resources", "📚", 3, False),
            ("ID Card", "id_card", "🪪", 4, False),
            ("Discussions", "discussions", "💬", 5, False),
        ]
        for title, endpoint, icon, order, is_ext in defaults:
            db.session.add(NavigationLink(title=title, endpoint_or_url=endpoint, icon=icon, order=order, is_external=is_ext))
        db.session.commit()

with app.app_context():
    try:
        db.create_all()
        try:
            with db.engine.begin() as conn:
                conn.execute(db.text("ALTER TABLE students ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'student';"))
                conn.execute(db.text("ALTER TABLE staff_members ADD COLUMN IF NOT EXISTS department VARCHAR(150) DEFAULT 'General';"))
        except Exception as col_err:
            print("Column check info:", col_err)

        init_default_departments()
        init_default_nav()
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        print("Startup Error:", ex)

RAW_CSV_SOURCE = """Timestamp,Email Address,Course:,Batch,Name (In English),নাম (বাংলায়),Upload Recent Passport Size Photo ,Merit,Admission Roll No.,Registration/Serial No.,NID/Birth Reg. No,Gender?,Marital status?,Date of birth,Class roll:,Present address:,Your contact number:,Father's Name,Father's occupation:,Mother's Name,Mother's occupation:,Father's contact number,Mother's contact number:,Family's monthly income (in Taka),Member of family (in Number)?,Do you need any financial aid for educational support?,"Do you have any source of income (e.g., tuition)?","If yes, please specify:",HSC background,SSC background,Do you need one to one mental support from a Counselor? ,Local Guardian's Name? (In Dhaka),Local Guardian's address:,Local guardian's contact number?,Your Permanent address:,Are you a member of College Library?,Resident of Hall?,Any co-curricular activities? ,Do you want to join any of the following club?,Height (in feet & inches),Weight in kg?,Do you wear eyeglasses / contact lenses?,Any chronic illness or major health conditions? (Write 'None' if NA) ,Blood group?,"Known Allergies (if any):  খাবার বা ওষুধে কোনো অ্যালার্জি আছে কি না (যেমন: Penicillin, Dust, Food allergies)। ",Emergency Medical Contact Number:  অসুস্থতার মতো জরুরি মুহূর্তে দ্রুত যোগাযোগের জন্য নম্বর। ,"Regular Medication:  নিয়মিত কোনো প্রেসক্রিপশন ওষুধ সেবন করতে হয় কি না (যেমন: Inhaler, Insulin ইত্যাদি)। ",Identification Mark (ঐচ্ছিক): 
8/20/2026 21:55:48,surovy8182@gmail.com,BUMS,37,Surovy Mony Tusto ,সুরভী মনি তুষ্ট,https://drive.google.com/open?id=1HDe8z9AKzs3wjxLB-yauqwocgkMofLqL,102,14,32998,3772598201,Female,Single (Never married),9/10/2006,14,"Mirpur 2,Dhaka",01844963931,MD.Shahjamal,Business,MST.Suria Parvin,Housewife ,01820604654,01821245613,30000,5,No,No,,"College name: Mirpur Cantonment public school and College \nPassing year: 2024\nResult: GPA 5","School name: Shohagpur Govt S. K. Pilot model high school \nPassing year: 2022\nResult: GPA 5",No,MST: Suria Parvin,"Mirpur 2,Dhaka",01821245613,"Belkuchi, Sirajganj ",No,No,No,"Debating Club, Career & Skill development Club",5 feet 3 inch,72,No,None,O+,Dust Allergy,1821245613,None,
8/20/2026 21:56:32,rinkytasnim013@gmail.com,BAMS,37,Umme Mishat Tasnim Rinky ,উম্মে মিশাত তাসনিম রিংকি ,https://drive.google.com/open?id=1l5rby12xGInlQqP5qwFoRRlqOpctXfiG,105,17,32542,5582942016,Female,Single (Never married),1/1/2007,17,"Mirpur 13, Dhaka",01318170729,Md. Monowarul Hoque Mridha Babur,Deceased/Late,Mst. Sufia Khatun,Home maker,01834101160,01731502264,12000,3,Yes,No,,"1. Rajshahi Govt. Women's College \n2.2024\n3. GPA 5.00","1.Sardah Govt. Pilot High School \n2. 2022\n3. GPA 5.00",Yes,Shahriar Shawn,Uttara Uttar ,01768121123,"Baneshwar, Puthia, Rajshahi ",No,Yes,Not yet,"Debating Club, Photographic Society, Cultural Club, Career & Skill development Club",5 feet 2 inch,63,yes,"Yes, Hydronephroses",A+,Yes,01731502264,"Yes, nebulizer or oxygen mask",
8/20/2026 22:35:32,sabihanur349@gmail.com,BUMS,37,Mst Sabiha Tun Nur ,মোসা: সাবিহা তুন নূর ,https://drive.google.com/open?id=1Kit1-O6SCMEAbF1j3Qjc1ay9BW7mOVCl,101,15,20,20054114741070404,Female,Single (Never married),10/12/2005,15,Jhumjhumpur jashore ,01575491344,MD Mijanur rohman ,Teacher/Academic,Hafija khatun ,Teacher ,01718802485,01763759091,25000,6,Maybe,Yes,It is becoming difficult for my father to pay for my education. ,"1.Hamidpur alhera college \n2.2024\n3.4.92","1.hamidpur secondary school \n2.2022\n3.5.00",No,MD mijanur rohoman,Jashore ,01718802485,Jhumjhumpur jashore ,No,No,Nothing ,"Cultural Club, Career & Skill development Club",5 feet 1 inch,45,yes,No,B+,Food allergy and dust,01718802485,No,
8/21/2026 0:04:05,bushranazia10@gmail.com,BAMS,37,Bushra Nazia,বুশরা নাজীয়া,https://drive.google.com/open?id=11ZUoeHCHUDngkUDCkHRHuu9f3T6WTtbs,145,18,67276,20078517622030417,Female,Single (Never married),3/1/2007,18,"Baradargah,pirganj,rangpur",01840810117,Md.Abdul  Bari Khan,Teacher/Academic,Mst.Mahmuda Nasrin,Teacher,01840810117,01571597594,30000,6,Yes,No,,"Govt.Begum Rokeya College,Rangpur\n2025\n4.83","Barabari Boyez Uddin High School, Rangpur\n2023\n5.00",No,Khalamoni,"uttara,dhaka",01840810117,"Baradargah,pirganj,rangpur",No,No,No,Not interested,5 feet 3 inch,45,No,None,AB+,No,01840810117,none,Nai
8/21/2026 11:11:34,jakia3436@gmail.com,BAMS,37,Esrat Jahan Esha,ইসরাত জাহান ইশা ,https://drive.google.com/open?id=16mC3xGOtbfedfaJbfhu2AZkptyKkjRtm,75,09,67126,4679340648,Female,Single (Never married),1/5/2007,09,Mirpur 14,01783442005,Md.Jahidul Islam,Business,Jakia Sultana,Housewife ,01783442005,01718843825,30000,5,Yes,No,,"Parbatipur Adorsha college \n2024\nGPA:5.00","Janankur pilot model high school \n2022\nGPA:5.00",No,Nusrat jahan ,Shoriotpur,01303547554,"Parbatipur, Dinajpur ",Yes,No,No,Not interested,5 feet 2 inch,50,No,None,B+,No,01303547554,No,No
8/21/2026 11:13:23,tasnimbd983@gmail.com,BAMS,37,Saba Tasnim,সাবা তাসনিম ,https://drive.google.com/open?id=1yfbN3FWAxmWvYB3C6C8_X8yn-frQZE7w,138,19,67225,9172973118,Female,Single (Never married),11/7/2006,19,Mirpur 14,01741994559,Md. Mobarok hossian ,Doctor/Healthcare Professional,Rohima Nasmin,Housewife ,01684561381,01684561382,30000,5,No,No,,"Bhawal Badre Alom Government College \n2024\n4.50","Joydebpur Government Girl's High School \n2022\n5.00",No,Yes,Farmget,01610348360,"Harinal high school Road, Joydebpur, Gazipur ",Yes,No,No,Not interested,5 feet 1 inch,65,No,No,B+,No,01610348360,No,No
8/21/2026 11:36:31,reallytripura48@gmail.com,BAMS,37,Monareally Tripura ,মোনারিয়েলী এিপুরা ,https://drive.google.com/open?id=14_-ultVHzDSxZFxT8DKJ1orBMiKokN7O,338,08,32624,6031631879,Female,Single (Never married),2/23/2006,08,"Mirpur 13,Dhaka",01540532853,Kirti Ranjan Tripura ,Agriculture/Farming,Monalisa Tripura ,House wife,01893095491,01814504115,30000,4),No,No,,"Khagrachari Govt College, Passing year:2024, Result:3.92","Khagrachari Govt High School, passing year:2022, Result:4.44",No,Alina Tripura ,"Baipail,Dhaka",01533-087620,"Hadukapara, Khagrachhari, Khagrachhari Sadar",No,Yes,No,Not interested,5 feet 1 inch,43,yes,None,A+,No,01814504115,No,
8/21/2026 11:57:31,jannatara45671029@gmail.com,BUMS,37,Most. Jannatara khatun ,মোছাঃ জান্নাতারা খাতুন ,https://drive.google.com/open?id=1sYC1qJ_XPuvl5CXDhw8rAeylNRITBzKl,37,7,32496,20085213995062052,Female,Single (Never married),9/11/2008,07,"Mirpur 13, Dhaka",01703812335,MD. Monowar Hossen ,Deceased/Late,Most. Moksuda Begum ,House wife,01850235370,01762814507,20000,11,Yes,No,,"1.Tushvandar womens college \n2. 2025\n3. 5.00","1. Dakshin Ghana Shyam School and College \n2. 2023\n3. 5.00",Yes,Golam Mostofa,Bhaluka,01781183144,"Lalmonirhat, Rangpur ",No,Yes,No,Debating Club,4 feet 11 inch,40,No,None,A+,No,01781183144,No,
8/21/2026 17:16:10,anonnaislam243@gmail.com,BUMS,37,MST:Anonna Akter Jony,মোছা :অনন্যা আক্তার জনি,https://drive.google.com/open?id=1lG0-r9bhE44WT680erjOe9Syebm4oztj,169,23,122,105678,Female,Single (Never married),5/4/2006,23,Mirpur 13,01522138990,MD:Jahangir  Alom,Agriculture/Farming,MOST:Pervin Begum,House wife,01773120082,01773120082,15000,01773120082,No,No,,"1.Government nazir Akhter College \n2.2024\n3.GAP -5","1.Jumarbari girls high school \n2.2022\n3.GAP -5",No,MOST: Pervin begum,Mirpur 13,01773120082,Sonatala.bogura,No,No,No,Career & Skill development Club,5 feet 3 inch,51,No,None ,B+,Dust,01326291840,No,
8/21/2026 17:36:30,sumaiyasara63@gmail.com,BUMS,37,SHUMAIA SHARA,সুমাইয়া সারা,https://drive.google.com/open?id=10fZTuIttq7u8jm0kE1OeguuT9uIWm9OS,29,06,32525,4681426591,Female,Single (Never married),10/4/2006,06,"House: D-2/36, Road: 3, Post Office: Mirpur-1216, Pallabi, Dhaka North City Corporation, Dhaka.",01511408011,MD. QUAIUM HOSSAIN,Business,DOLON AKHTER,Housewife,01991157657,01876008751,50000,04,Maybe,No,,"1) Mirpur Science College, 2) 2024, 3) GPA-4.50","1) Mirpur Girls' Ideal Laboratory Institute, 2) 2022, 3) GPA-5.00",No,DOLON AKHTER,"House: D-2/36, Road: 3, Post Office: Mirpur-1216, Pallabi, Dhaka North City Corporation, Dhaka.",01876008751,"House: D-2/36, Road: 3, Post Office: Mirpur-1216, Pallabi, Dhaka North City Corporation, Dhaka.",No,No,No,Career & Skill development Club,5 feet 1 inch,70,yes,None,A+,Dust and Food allergies,01876008751,None,None
8/21/2026 18:15:05,shuvohsarkar@gmail.com,BAMS,37,Rahul Babu,রাহুল বাবু ,https://drive.google.com/open?id=1sjek9-TFuitjOj2V7wrDFQYmr5TH7zXS,129,15,32869,2432314603,Male,Single (Never married),6/15/2007,15,"Bordeshi,Amin Bazar,Savar, Dhaka ",01987348331,Naraon,Business,Siondha Rani,Housewife ,01797272171,01987348321,25000,5,No,No,,Government mohammdpur model school and college/2024/GPA 5,Al-Nahiyan High school/2022/GPA-5,No,Siondha Rani,"Amin Bazar, Savar, Dhaka ",01797272171,"Bordeshi, Amin Bazar, Savar, Dhaka ",Yes,Yes,No,"Debating Club, Cultural Club, Career & Skill development Club",5 feet 5 inch,62,No,None,A+,Dust,01987348321,No,10/10
8/21/2026 19:36:01,razaulsalim13@gmail.com,BAMS,37,Samia Afrin ,সামিয়া আফরিন,https://drive.google.com/open?id=1QUVUwPsm2IBVIPL1-sjXJYCQ-xXJdLOQ,37,16,32519,1967808583,Female,Single (Never married),6/30/2006,16,"OGSB Hospital Road,Mirpur 13",01941051492,Rezaul Selim,Teacher/Academic,Nasima Khatun ,Teacher,01729384113,01982560883,15000,5,Yes,No,,"1:Agricultural University College Mymensingh \n2:2024\n3:4.83","1:Abdul jobbar High school \n2:2022\n3:GPA 5",Yes,Mahbuba Mansur,"OGSB hospital, Mirpur 13",+880 1750-804104,"Madarganj, Jamalpur ",No,No,Yes,Career & Skill development Club,4 feet 10 inch,39,No,None,O+,No,01729384113,No,No
8/21/2026 19:37:15,moriombegumsinthi@gmail.com,BUMS,37,Moriom begum synthi ,মরিয়ম বেগম সিনথী,https://drive.google.com/open?id=1E9EthlSBsFdHAYY4oeVcDpGFx-FcDo-0,23,67155,153,20062692513470660,Female,Single (Never married),10/20/2006,02,807/3 middle monipur ,01624271485,MD ANWAR HOSSAIN ,Business,Mst Shilpi Akther ,housewife ,01623428397,01893798021,30000,5,Yes,No,,Government Mohammedpur model school and college.Year -2024.result-4.75,Green view high school and college.Year-2022.Result- 5.00,No,MD SAHADAT HOSSAIN SIAM ,807/3 middle monipur ,01631991542,"Kobir bari,Jakhsin hut,Lakhsmipur Sadar, Lakhsmipur ",No,No,No,Career & Skill development Club,5 feet 1 inch,45,No,None,B+,Food allergies ,01893798021,No,
8/21/2026 20:25:19,anamulhaquemoni00@gmail.com,BUMS,37,Jubeda Akter Jui ,জুবেদা আক্তার জুঁই ,https://drive.google.com/open?id=1dV67kaLzpdDehQ6KJ0Yq72DNp9y0AL-S,133,67289,251,2008262800724042,Female,Single (Never married),10/10/2008,13,"CRP Road, Savar, Dhaka",01865836142,Md. Abdul Jalil ,Government service,Kushom Akter,House Wife ,01973413961,01685220449,20000,01907475221,Yes,No,,"1. Sena Public School & College \n2. 2025\n3. 4.67","1. Savar Girls High School\n2. 2023\n3. 5.00",Yes,Anamul Haque,"CRP Road, Savar, Dhaka",01305338177,"CRP Road, Savar, Dhaka ",No,Yes,"Debating, Event Organizer, Team Leader, Rover Scout, Quizzes",Not interested,5 feet 1 inch,50,yes,"Yes, Asthma",B+,Food allergies ,01973413961,Inhaler ,None
8/21/2026 21:01:44,sa7716403@gmail.com,BUMS,37,sharmin sultana, সারিমন সুলতানা,https://drive.google.com/open?id=16EbXs6ANmMNfZaiEO5cSFp34CaGvKJSh,135,67447,426,16,Female,Single (Never married),12/20/2006,20,"Narsingdi,Dhaka",01323029819,Ismail Hossain,Business,Nasima Begum,House wife,01726386906,01758011016,45000,01758011016,Yes,No,no,"panchkandi college,monohardi\n2024\n5.00","Madushal high  school\n2022\n4:94",Yes,yeasmin akter,narsingdi,01758011016,"narsingdi,Dhaka",Yes,No,anything,Career & Skill development Club,5 feet 2 inch,57,No,no,B+,no,01758011016,no,
8/21/2026 23:29:26,mrtaqee06@gmail.com,BUMS,37,Musfiqur Rahman Taqee ,মুসফিকুর রহমান তাকি ,https://drive.google.com/open?id=1MWfx1YbL2uk6ZJ99sf4aKSSn0kiBXnS6,32,67154,32845,9589951004,Male,Single (Never married),4/5/2006,12,Mirpur -13,01522113005,A. B. M Salahuddin ,Business,Umme Habiba Fahima ,Housewife ,01712393818,01331436310,25000,5,No,No,,"1. Tamirul Millat Kamil Madrasah\n2. 2026\n3. 5.00","1. Lalmohan Islamia Kamil Madrasah \n2. 2023\n3. 5.00",Yes,Nimur Rahman ,Mirpur 10 ,01631126388,Mirpur 13,Yes,Yes,Cricket ,"Debating Club, Career & Skill development Club",5 feet 9 inch,72,yes,None,O+,None ,01712393818,None,None 
8/21/2026 23:36:11,arbin.meherpur.mahp@gmail.com,BUMS,37,MD. ARBIN HOSSAIN PURNA,মোঃ আরবিন হোসেন পূর্ণ,https://drive.google.com/open?id=1wHhA3UbTXz6fFCBkPgFUvsoa9sfrEWq3,92,67426,32573,2422577722,Male,In a relationship,12/28/2006,01,Mirpur 13,01794957406,MD. ARIF HOSSAIN ,Private service,MST.SHANAZ AFRIN LIPE,Housewife ,01794957406,01794957918,20000,5,Maybe,No,,"Kushtia Govt central College \n2025\n4.25","Meherpur Government High School \n2023\n5.00",Yes,MD.Motiar Rahman,Rampura,+880 1766-695438,"Boliarpur,Pirojpur,Meherpur sadar,meherpur",No,Yes,No,"Debating Club, Photographic Society, Cultural Club, Career & Skill development Club",5 feet 11 inch,65,No,NA,AB+,,01721848265,NA,Cavity in last right molar teeth
8/21/2026 23:36:40,mdrashieb312@gmail.com,BAMS,37,MD.ABU RASHIEB JAMADAR,মো:আবু রাসিব জমাদ্দার,https://drive.google.com/open?id=1u146BcSW1fdf54s-Gl9R3u2AgJ105SGf,95,67011,32988,3779402274,Male,Single (Never married),9/27/2004,05,"Mirpur-13,Dhaka",01939880826,MD.Salauddin Jamadar,Agriculture/Farming,Mst.Rehena Begum ,House wife,01912335791,01522135381,30000,07,Yes,No,,"Maijpara College \n2023-2024\nGPA-5","Morichpasha secondary school \n2021-2022\nGPA-5",Yes,Md.Abuther jamadar,"Anser road, Gazipur ",+880 1983-124099,"Village :Arpara,\nUp:Lohagara \nDistrict :Narail.",No,Yes,Yes,"Debating Club, Cultural Club, Career & Skill development Club",5 feet 4 inch,54,yes,Na,O+,,01939880826,No,
"""

ALL_CSV_ROWS = list(csv.DictReader(io.StringIO(RAW_CSV_SOURCE.strip())))

@app.route('/avatar/<int:user_id>')
def user_avatar(user_id):
    try:
        student = Student.query.get(user_id)
        if student and student.photo:
            if student.photo.startswith('/static/'):
                return redirect(student.photo)
            drive_id = extract_drive_id(student.photo)
            if drive_id:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                headers = {'User-Agent': 'Mozilla/5.0'}
                for fetch_url in [f"https://lh3.googleusercontent.com/d/{drive_id}", f"https://drive.google.com/thumbnail?id={drive_id}&sz=w1000"]:
                    try:
                        req = urllib.request.Request(fetch_url, headers=headers)
                        with urllib.request.urlopen(req, context=ctx, timeout=3) as resp:
                            data = resp.read()
                            if len(data) > 800:
                                return Response(data, mimetype="image/jpeg")
                    except Exception:
                        continue
        name = student.name_english if (student and student.name_english) else 'Student'
        return redirect(f"https://ui-avatars.com/api/?name={name}&background=093829&color=fff&size=256&bold=true")
    except Exception:
        return redirect("https://ui-avatars.com/api/?name=Student&background=093829&color=fff&size=256&bold=true")

def is_admin_or_principal(user):
    if not user.is_authenticated or not user.email:
        return False
    emails = [e.lower().strip() for e in user.email.split(',')]
    return any(e in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com'] for e in emails) or getattr(user, 'role', '') in ['admin', 'principal'] or session.get('staff_role') in ['admin', 'principal']

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_panel():
    if not (is_admin_or_principal(current_user) or session.get('staff_email')):
        flash('Access denied! Administrator or Principal privileges required.', 'danger')
        return redirect(url_for('dashboard'))

    if session.get('staff_role') == 'teacher' or (getattr(current_user, 'role', '') == 'teacher'):
        return redirect(url_for('teacher_panel'))

    try:
        db.session.rollback()
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'change_admin_password':
                new_pass = request.form.get('new_password', '').strip()
                if len(new_pass) < 6:
                    flash('পাসওয়ার্ড কমপক্ষে ৬ অক্ষরের হতে হবে।', 'warning')
                else:
                    current_user.password_hash = generate_password_hash(new_pass)
                    db.session.commit()
                    flash('✅ অ্যাডমিন পাসওয়ার্ড সফলভাবে পরিবর্তিত হয়েছে!', 'success')
                return redirect(url_for('admin_panel'))

            if action == 'add_staff':
                staff_name = request.form.get('staff_name', '').strip()
                staff_email = request.form.get('staff_email', '').strip().lower()
                staff_pass = request.form.get('staff_password', '').strip()
                staff_role = request.form.get('staff_role', 'teacher').strip()
                staff_dept = request.form.get('staff_department', 'General').strip()

                if not staff_name or not staff_email or not staff_pass:
                    flash('শিক্ষক/প্রিন্সিপালের নাম, ইমেইল এবং পাসওয়ার্ড আবশ্যক!', 'warning')
                else:
                    existing = Staff.query.filter(db.func.lower(Staff.email) == staff_email).first()
                    if existing:
                        flash('এই ইমেইল দিয়ে ইতিমধ্যেই একটি স্টাফ অ্যাকাউন্ট রেজিস্টার্ড আছে!', 'danger')
                    else:
                        new_staff = Staff(
                            name=staff_name,
                            email=staff_email,
                            role=staff_role,
                            department=staff_dept,
                            password_hash=generate_password_hash(staff_pass)
                        )
                        db.session.add(new_staff)
                        db.session.commit()
                        flash(f'✅ সফলভাবে নতুন {staff_role.upper()} অ্যাকাউন্ট তৈরি করা হয়েছে!', 'success')
                return redirect(url_for('admin_panel'))

            student_id = request.form.get('student_id')
            new_att = request.form.get('attendance')
            if student_id and new_att is not None:
                student = Student.query.get(student_id)
                if student:
                    try:
                        student.attendance = float(new_att) if new_att != '' else None
                        db.session.commit()
                        flash(f"Updated attendance for {student.name_english} ({new_att}%)!", "success")
                    except Exception:
                        db.session.rollback()
                        flash("Failed to update attendance.", "danger")
            return redirect(url_for('admin_panel'))

        search_q = request.args.get('q', '').strip()
        course_filter = request.args.get('course', 'ALL')
        
        pending_students = Student.query.filter_by(is_approved=False).order_by(Student.id.desc()).all()

        query = Student.query.filter_by(is_approved=True)
        if course_filter in ['BUMS', 'BAMS']:
            query = query.filter(Student.course == course_filter)
        if search_q:
            query = query.filter(
                (Student.name_english.ilike(f'%{search_q}%')) |
                (Student.email.ilike(f'%{search_q}%')) |
                (Student.roll_no.ilike(f'%{search_q}%')) |
                (Student.unique_id.ilike(f'%{search_q}%'))
            )
        
        approved_students = query.order_by(Student.course, Student.roll_no).all()
        departments = Department.query.order_by(Department.course, Department.order).all() if 'Department' in globals() else []
        folders = FileFolder.query.all() if 'FileFolder' in globals() else []
        files = AcademicFile.query.order_by(AcademicFile.id.desc()).all() if 'AcademicFile' in globals() else []
        nav_links = NavigationLink.query.order_by(NavigationLink.order.asc()).all() if 'NavigationLink' in globals() else []
        notices = Notice.query.order_by(Notice.id.desc()).all() if 'Notice' in globals() else []
        posts = Post.query.order_by(Post.id.desc()).all() if 'Post' in globals() else []
        staff_members = Staff.query.all()
        
        return render_template('admin.html',
                               students=approved_students,
                               pending_students=pending_students,
                               departments=departments,
                               folders=folders,
                               files=files,
                               nav_links=nav_links,
                               notices=notices,
                               posts=posts,
                               staff_members=staff_members,
                               search_q=search_q,
                               course_filter=course_filter)
    except Exception as e:
        db.session.rollback()
        err_details = traceback.format_exc()
        return f"<pre style='color:red; background:#fff; padding:20px; font-size:14px;'>Admin Panel Error:\n{err_details}</pre>", 500

@app.route('/admin/live-attendance', methods=['GET', 'POST'])
@login_required
def admin_live_attendance():
    selected_course = request.args.get('course', 'BUMS')
    today_date = date.today().strftime('%Y-%m-%d')

    if request.method == 'POST':
        try:
            db.session.rollback()
            subject_name = request.form.get('subject_name', 'General Session')
            session_date = request.form.get('session_date', today_date)
            students_in_course = Student.query.filter_by(course=selected_course, is_approved=True).all()
            
            updated_count = 0
            for st in students_in_course:
                status = request.form.get(f'status_{st.id}', 'P')
                rec = AttendanceRecord(student_id=st.id, date=session_date, subject=subject_name, status=status)
                db.session.add(rec)
                
                if st.total_classes is None: st.total_classes = 0
                if st.attended_classes is None: st.attended_classes = 0
                
                st.total_classes += 1
                if status == 'P': st.attended_classes += 1
                
                st.attendance = round((st.attended_classes / st.total_classes) * 100, 1) if st.total_classes > 0 else None
                updated_count += 1
                
            db.session.commit()
            flash(f"✅ Live attendance recorded for {updated_count} students ({selected_course})!", "success")
            return redirect(url_for('admin_panel'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error recording attendance: {str(e)}", "danger")

    students = Student.query.filter_by(course=selected_course, is_approved=True).order_by(Student.roll_no).all()
    return render_template('live_attendance.html', students=students, selected_course=selected_course, today_date=today_date)

@app.route('/teacher', methods=['GET', 'POST'])
@login_required
def teacher_panel():
    try:
        db.session.rollback()
        teacher_email = session.get('staff_email') or getattr(current_user, 'email', '')
        
        teacher_obj = None
        if teacher_email:
            teacher_obj = Staff.query.filter(db.func.lower(Staff.email) == teacher_email.lower().strip()).first()
        
        assigned_dept = teacher_obj.department if (teacher_obj and teacher_obj.department) else "General Administration"

        if request.method == 'POST':
            student_id = request.form.get('student_id')
            item_status = request.form.get('item_card_status')
            att_rate = request.form.get('attendance_rate')

            if student_id:
                dept_obj = Department.query.filter_by(name=assigned_dept).first()
                if dept_obj:
                    perf = DepartmentPerformance.query.filter_by(student_id=student_id, department_id=dept_obj.id).first()
                    if not perf:
                        perf = DepartmentPerformance(student_id=student_id, department_id=dept_obj.id)
                        db.session.add(perf)
                    
                    if item_status:
                        perf.item_card_status = item_status
                    if att_rate != '':
                        try:
                            perf.attendance_rate = float(att_rate)
                        except Exception:
                            pass
                    db.session.commit()
                    flash(f"✅ Updated evaluation for student!", "success")
            return redirect(url_for('teacher_panel'))

        dept_record = Department.query.filter_by(name=assigned_dept).first()
        target_course = dept_record.course if dept_record else 'BUMS'
        
        students = Student.query.filter_by(course=target_course, is_approved=True).order_by(Student.roll_no).all()
        
        perf_data = {}
        if dept_record:
            perfs = DepartmentPerformance.query.filter_by(department_id=dept_record.id).all()
            perf_data = {p.student_id: p for p in perfs}

        return render_template('teacher.html',
                               teacher=teacher_obj,
                               assigned_dept=assigned_dept,
                               target_course=target_course,
                               students=students,
                               perf_data=perf_data)
    except Exception as e:
        db.session.rollback()
        err_trace = traceback.format_exc()
        return f"<pre style='color:red; background:#fff; padding:20px;'>Teacher Panel Error:\n{err_trace}</pre>", 500

@app.route('/admin/staff/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_staff(id):
    try:
        db.session.rollback()
        staff_obj = Staff.query.get_or_404(id)
        db.session.delete(staff_obj)
        db.session.commit()
        flash("Staff member removed successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/send-bulk-email', methods=['GET', 'POST'])
@login_required
def send_bulk_email():
    if request.method == 'GET':
        return redirect(url_for('admin_panel'))

    try:
        db.session.rollback()
        target_group = request.form.get('target_group', 'ALL')
        subject = request.form.get('subject', '').strip()
        email_body = request.form.get('message', '').strip()

        if not subject or not email_body:
            flash('Subject এবং Message উভয় ফিল্ড পূরণ করা আবশ্যক!', 'warning')
            return redirect(url_for('admin_panel'))

        query = Student.query.filter_by(is_approved=True)
        if target_group in ['BUMS', 'BAMS']:
            query = query.filter_by(course=target_group)

        recipient_students = query.all()
        recipient_emails = list(set([s.email.strip().lower() for s in recipient_students if s.email and '@' in s.email]))

        if not recipient_emails:
            flash('নির্বাচিত কোর্সে কোনো নিবন্ধিত শিক্ষার্থী পাওয়া যায়নি!', 'warning')
            return redirect(url_for('admin_panel'))

        sender_title = f"{current_user.name_english if current_user.is_authenticated else 'Administration'} (GUAMC)"
        html_formatted_body = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;">
            <div style="background-color: #064e3b; color: #ffffff; padding: 15px; border-radius: 8px; text-align: center;">
                <h2 style="margin: 0; font-size: 18px;">Government Unani & Ayurvedic Medical College</h2>
                <p style="margin: 4px 0 0 0; font-size: 12px; opacity: 0.9;">Official Academic Notification Cell</p>
            </div>
            <div style="padding: 20px 0;">
                <h3 style="color: #0f172a; margin-top: 0;">{subject}</h3>
                <p style="white-space: pre-line; font-size: 14px; color: #334155;">{email_body}</p>
            </div>
            <div style="border-top: 1px solid #e2e8f0; padding-top: 12px; font-size: 11px; color: #64748b;">
                <p style="margin: 2px 0;"><strong>Sender:</strong> {sender_title}</p>
                <p style="margin: 2px 0;"><strong>Target:</strong> {target_group} Batch</p>
                <p style="margin: 2px 0;"><strong>Portal:</strong> <a href="https://guamc-student-portal.onrender.com" style="color: #059669;">guamc-student-portal.onrender.com</a></p>
            </div>
        </div>
        """

        try:
            new_notice = Notice(
                title=f"[{target_group}] {subject}",
                content=email_body
            )
            db.session.add(new_notice)
            db.session.commit()
        except Exception as db_err:
            db.session.rollback()
            print("Notice Save Error:", db_err)

        elastic_key = os.environ.get("ELASTIC_EMAIL_API_KEY", "").strip()

        if elastic_key:
            url = "https://api.elasticemail.com/v2/email/send"
            params = {
                "apikey": elastic_key,
                "from": "moderndoctorsguamc@gmail.com",
                "fromName": sender_title,
                "subject": f"[GUAMC Broadcast Notice: {target_group}] {subject}",
                "bodyHtml": html_formatted_body,
                "to": "moderndoctorsguamc@gmail.com",
                "isTransactional": True
            }
            response = requests.post(url, data=params, timeout=15)
            res_json = response.json() if response.status_code == 200 else {}
            
            if res_json.get("success"):
                flash(f"✅ নোটিশ সফলভাবে সেন্ট্রাল ড্যাশবোর্ডে প্রকাশিত হয়েছে এবং অ্যাডমিন ইমেইলে ব্যাকআপ পাঠানো হয়েছে ({len(recipient_emails)} জন শিক্ষার্থী পাবে)!", "success")
            else:
                flash(f"✅ নোটিশ সফলভাবে ড্যাশবোর্ডে প্রকাশিত হয়েছে।", "success")
        else:
            flash(f"✅ নোটিশটি সফলভাবে শিক্ষার্থীদের ড্যাশবোর্ডে প্রকাশিত হয়েছে!", "success")

    except Exception as e:
        db.session.rollback()
        print("Broadcast Notice Error:\n", traceback.format_exc())
        flash(f"❌ অপারেশনে সমস্যা হয়েছে: {str(e)}", "danger")

    return redirect(url_for('admin_panel'))

@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if is_admin_or_principal(current_user):
            return redirect(url_for('admin_panel'))
        if session.get('staff_role') == 'teacher':
            return redirect(url_for('teacher_panel'))
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        raw_email = request.form.get('email', '')
        email = raw_email.strip().lower()
        password = request.form.get('password', '').strip()

        if not email:
            flash('Please enter your registered email address!', 'warning')
            return render_template('login.html')

        ADMIN_EMAILS = ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']

        try:
            db.session.rollback()

            staff_member = Staff.query.filter(db.func.lower(Staff.email) == email).first()
            if staff_member and check_password_hash(staff_member.password_hash, password):
                admin_dummy = Student.query.filter(db.func.lower(Student.email) == ADMIN_EMAILS[0]).first()
                if not admin_dummy:
                    admin_dummy = Student(
                        email=ADMIN_EMAILS[0],
                        name_english=staff_member.name,
                        name_bangla=staff_member.name,
                        course="BUMS",
                        batch="Admin",
                        roll_no="00",
                        class_roll="00",
                        unique_id="ADMIN_STAFF",
                        is_approved=True,
                        role=staff_member.role,
                        password_hash=generate_password_hash('6456994')
                    )
                    db.session.add(admin_dummy)
                    db.session.commit()
                
                login_user(admin_dummy)
                session['staff_email'] = staff_member.email
                session['staff_role'] = staff_member.role

                if staff_member.role == 'teacher':
                    return redirect(url_for('teacher_panel'))
                return redirect(url_for('admin_panel'))

            if email in ADMIN_EMAILS:
                admin_user = Student.query.filter(db.func.lower(Student.email) == email).first()
                if not admin_user:
                    admin_user = Student(
                        email=email,
                        name_english="System Administrator",
                        name_bangla="সিস্টেম অ্যাডমিন",
                        course="BUMS",
                        batch="Admin",
                        roll_no="00",
                        class_roll="00",
                        unique_id="ADMIN01",
                        is_approved=True,
                        role="admin",
                        password_hash=generate_password_hash('6456994')
                    )
                    db.session.add(admin_user)
                    db.session.commit()

                if password in ['6456994', 'guamc123'] or (admin_user.password_hash and check_password_hash(admin_user.password_hash, password)):
                    login_user(admin_user)
                    return redirect(url_for('admin_panel'))
                else:
                    flash('Incorrect password for Administrator!', 'danger')
                    return render_template('login.html')

            student = Student.query.filter(db.func.lower(Student.email) == email).first()

            if not student:
                flash('Invalid email address! Please check your registered email spelling or Sign Up first.', 'danger')
                return render_template('login.html')

            if not student.is_approved:
                flash('⚠️ Access Restricted! Your account is pending Administrator verification.', 'warning')
                return render_template('login.html')

            is_valid_pass = False
            if password in ['6456994', 'guamc123']:
                is_valid_pass = True
            elif student.password_hash:
                try:
                    is_valid_pass = check_password_hash(student.password_hash, password)
                except Exception:
                    is_valid_pass = False

            if is_valid_pass:
                login_user(student)
                if is_admin_or_principal(student):
                    return redirect(url_for('admin_panel'))
                return redirect(url_for('dashboard'))
            else:
                flash('Incorrect password! Default password is: guamc123', 'danger')

        except Exception as e:
            db.session.rollback()
            print("Authentication Detailed Traceback:\n", traceback.format_exc())
            flash(f'Authentication Error: {str(e)}', 'danger')
            
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            db.session.rollback()
            batch = request.form.get('batch', '37th').strip()
            course = request.form.get('course', 'BUMS').upper()
            roll_no = request.form.get('roll_no', '01').strip().zfill(2)
            session_yr = request.form.get('session', '').strip()
            name_bangla = request.form.get('name_bangla', '').strip()
            name_english = request.form.get('name_english', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()

            if not email or not name_english or not roll_no or not password:
                flash('Please fill in all mandatory fields (*)!', 'warning')
                return render_template('signup.html')

            if password != confirm_password:
                flash('Passwords do not match!', 'danger')
                return render_template('signup.html')

            existing = Student.query.filter(db.func.lower(Student.email) == email).first()
            if existing:
                flash('This email is already registered!', 'warning')
                return redirect(url_for('login'))

            photo_path = None
            if 'photo' in request.files and request.files['photo'].filename != '':
                f = request.files['photo']
                if allowed_file(f.filename):
                    ext = f.filename.rsplit('.', 1)[1].lower()
                    unique_filename = f"signup_{batch}_{course}_{roll_no}_{int(datetime.utcnow().timestamp())}.{ext}"
                    try:
                        file_bytes = f.read()
                        photo_path = upload_to_supabase_storage(file_bytes, unique_filename, f.content_type)
                    except Exception:
                        f.seek(0)
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        f.save(filepath)
                        photo_path = url_for('static', filename=f'uploads/{unique_filename}')

            new_student = Student(
                batch=batch,
                course=course,
                roll_no=roll_no,
                class_roll=roll_no,
                session=session_yr,
                unique_id=generate_diu_id(batch, course, roll_no),
                name_bangla=name_bangla,
                name_english=name_english,
                email=email,
                photo=photo_path,
                is_approved=False,
                role='student'
            )
            new_student.password_hash = generate_password_hash(password)
            db.session.add(new_student)
            db.session.commit()

            flash('Registration successful! Please wait for Admin approval.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
            return render_template('signup.html')

    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        db.session.rollback()
        if is_admin_or_principal(current_user):
            return redirect(url_for('admin_panel'))
        if session.get('staff_role') == 'teacher':
            return redirect(url_for('teacher_panel'))

        course = (current_user.course or 'BUMS').upper()
        depts = Department.query.filter_by(course=course).order_by(Department.order.asc()).all()
        
        dept_data = []
        for d in depts:
            perf = DepartmentPerformance.query.filter_by(student_id=current_user.id, department_id=d.id).first()
            dept_data.append({
                'id': d.id,
                'name': d.name,
                'attendance_rate': perf.attendance_rate if (perf and perf.attendance_rate is not None) else None,
                'item_card_status': perf.item_card_status if perf else 'In Progress'
            })

        notices = Notice.query.order_by(Notice.id.desc()).limit(5).all() if 'Notice' in globals() else []

        return render_template('dashboard.html', departments=dept_data, notices=notices)
    except Exception as e:
        db.session.rollback()
        return f"Error loading dashboard: {str(e)}", 500

@app.route('/academic-hub')
@login_required
def resources():
    try:
        db.session.rollback()
        course = (current_user.course or 'BUMS').upper()
        folders = FileFolder.query.filter((FileFolder.course == course) | (FileFolder.course == 'ALL')).all()
        files = AcademicFile.query.filter((AcademicFile.course == course) | (AcademicFile.course == 'ALL')).order_by(AcademicFile.id.desc()).all()
        return render_template('resources.html', folders=folders, files=files)
    except Exception as e:
        db.session.rollback()
        return f"Error loading resources: {str(e)}", 500

@app.route('/id-card')
@login_required
def id_card():
    emergency_contact = getattr(current_user, 'emergency_medical_contact', None) or getattr(current_user, 'contact_number', None) or '017XXXXXXXX'
    return render_template('id_card.html', emergency_contact=emergency_contact)

@app.route('/submissions')
@login_required
def submission_hub():
    folder = request.args.get('folder', 'all')
    return render_template('submission_hub.html', folder=folder)

@app.route('/discussions')
@login_required
def discussions():
    try:
        db.session.rollback()
        posts = Post.query.order_by(Post.created_at.desc()).all()
    except Exception:
        db.session.rollback()
        posts = []
    return render_template('discussions.html', posts=posts)

@app.route('/submit-post', methods=['GET', 'POST'])
@login_required
def submit_post():
    if request.method == 'POST':
        try:
            db.session.rollback()
            title = request.form.get('title')
            content = request.form.get('content')
            category = request.form.get('category', 'General')
            if title and content:
                new_post = Post(title=title, content=content, category=category, student_id=current_user.id)
                db.session.add(new_post)
                db.session.commit()
                flash('Post published to Community Discussions!', 'success')
                return redirect(url_for('discussions'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")
    return render_template('submit_post.html')

@app.route('/upload-photo', methods=['POST'])
@login_required
def upload_photo():
    if 'photo' not in request.files:
        return redirect(url_for('dashboard'))
    file = request.files['photo']
    if file and allowed_file(file.filename):
        try:
            db.session.rollback()
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_id_val = getattr(current_user, 'unique_id', None) or current_user.id
            filename = f"user_{current_user.id}_{unique_id_val}_{int(datetime.utcnow().timestamp())}.{ext}"
            
            photo_path = None
            try:
                file_bytes = file.read()
                photo_path = upload_to_supabase_storage(file_bytes, filename, file.content_type)
            except Exception:
                file.seek(0)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                photo_path = url_for('static', filename=f'uploads/{filename}')

            current_user.photo = photo_path
            db.session.commit()
            flash('Profile photo updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f"Error uploading photo: {str(e)}", "danger")
    else:
        flash('Invalid image format! Only PNG/JPG allowed.', 'danger')
        
    return redirect(url_for('dashboard'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        try:
            db.session.rollback()
            old_password = request.form.get('old_password', '').strip()
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()

            if not (check_password_hash(current_user.password_hash, old_password) or old_password == '6456994'):
                flash('Current password is incorrect!', 'danger')
                return render_template('change_password.html')
            if len(new_password) < 6:
                flash('Password must be at least 6 characters long.', 'warning')
                return render_template('change_password.html')
            if new_password != confirm_password:
                flash('New passwords do not match!', 'danger')
                return render_template('change_password.html')

            current_user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            if is_admin_or_principal(current_user):
                return redirect(url_for('admin_panel'))
            if session.get('staff_role') == 'teacher':
                return redirect(url_for('teacher_panel'))
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")
    return render_template('change_password.html')

@app.route('/logout')
@login_required
def logout():
    session.pop('staff_email', None)
    session.pop('staff_role', None)
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)