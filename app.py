import os
import csv
import io
import re
import urllib.request
import ssl
import traceback
from datetime import datetime, date
from flask import Flask, render_template, redirect, url_for, request, flash, Response, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
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

# ==================== GMAIL SMTP CONFIGURATION ====================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'moderndoctorsguamc@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'qhofbkllykglrzrj')
app.config['MAIL_DEFAULT_SENDER'] = ('GUAMC Academic Cell', app.config['MAIL_USERNAME'])

mail = Mail(app)

from models import (
    db, 
    Student, 
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
        return Student.query.get(int(user_id))
    except Exception:
        return None

@app.context_processor
def inject_global_template_vars():
    try:
        nav_links = NavigationLink.query.order_by(NavigationLink.order.asc()).all()
        return dict(custom_nav_links=nav_links)
    except Exception:
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
        init_default_departments()
        init_default_nav()
        db.session.commit()
    except Exception as ex:
        print("Startup Error:", ex)

# ==================== সম্পূর্ণ CSV ডেটাসেট ====================
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

# ==================== AUTHENTICATION ====================

@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.email and current_user.email.lower().strip() in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
            return redirect(url_for('admin_panel'))
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        try:
            raw_email = request.form.get('email', '')
            email = raw_email.strip().lower()
            password = request.form.get('password', '').strip()

            if not email:
                flash('Please enter your registered email address!', 'warning')
                return render_template('login.html')

            ADMIN_EMAILS = ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']

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
                        password_hash=generate_password_hash('6456994')
                    )
                    db.session.add(admin_user)
                    db.session.commit()

                if password == '6456994' or check_password_hash(admin_user.password_hash, password):
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

            if check_password_hash(student.password_hash, password) or password == 'guamc123':
                login_user(student)
                return redirect(url_for('dashboard'))
            else:
                flash('Incorrect password! Default password is: guamc123', 'danger')
        except Exception:
            db.session.rollback()
            flash('An error occurred during authentication.', 'danger')
            
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
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
                is_approved=False
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

# ==================== STUDENT DASHBOARD ====================

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        if current_user.email and current_user.email.lower().strip() in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
            return redirect(url_for('admin_panel'))

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

        return render_template('dashboard.html', departments=dept_data)
    except Exception as e:
        return f"Error loading dashboard: {str(e)}", 500

# ==================== ACADEMIC HUB ====================

@app.route('/academic-hub')
@login_required
def resources():
    course = (current_user.course or 'BUMS').upper()
    folders = FileFolder.query.filter((FileFolder.course == course) | (FileFolder.course == 'ALL')).all()
    files = AcademicFile.query.filter((AcademicFile.course == course) | (AcademicFile.course == 'ALL')).order_by(AcademicFile.id.desc()).all()
    return render_template('resources.html', folders=folders, files=files)

# ==================== ADMIN CONTROL PANEL ====================

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_panel():
    ADMIN_EMAILS = ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']
    if not current_user.email or current_user.email.lower().strip() not in ADMIN_EMAILS:
        flash('Access denied! Administrator privileges required.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
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

    try:
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
        
        return render_template('admin.html',
                               students=approved_students,
                               pending_students=pending_students,
                               departments=departments,
                               folders=folders,
                               files=files,
                               nav_links=nav_links,
                               notices=notices,
                               posts=posts,
                               search_q=search_q,
                               course_filter=course_filter)
    except Exception as e:
        err_details = traceback.format_exc()
        return f"<pre style='color:red; background:#fff; padding:20px; font-size:14px;'>Admin Panel Error:\n{err_details}</pre>", 500

# ==================== BROADCAST EMAIL NOTICES (FIXED FOR GET/POST) ====================

@app.route('/admin/send-bulk-email', methods=['GET', 'POST'])
@login_required
def send_bulk_email():
    if request.method == 'GET':
        return redirect(url_for('admin_panel'))

    ADMIN_EMAILS = ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']
    is_admin = current_user.email and current_user.email.lower().strip() in ADMIN_EMAILS
    is_teacher = getattr(current_user, 'role', '') == 'teacher'

    if not (is_admin or is_teacher):
        flash('Unauthorized! Administrator or Faculty privileges required.', 'danger')
        return redirect(url_for('dashboard'))

    target_group = request.form.get('target_group', 'ALL')  # ALL, BUMS, BAMS
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
        flash('নির্বাচিত কোর্সে কোনো বৈধ প্রাপক পাওয়া যায়নি!', 'warning')
        return redirect(url_for('admin_panel'))

    sender_title = f"{current_user.name_english} (GUAMC Faculty)" if is_teacher else "GUAMC Administration"
    full_message_body = (
        f"{email_body}\n\n"
        f"--------------------------------------------------\n"
        f"Official Notice from: {sender_title}\n"
        f"Government Unani and Ayurvedic Medical College (GUAMC)\n"
        f"Web Portal: https://guamc-student-portal.onrender.com\n"
    )

    try:
        msg = Message(
            subject=f"[GUAMC Academic Notice] {subject}",
            sender=(sender_title, app.config['MAIL_USERNAME']),
            recipients=[app.config['MAIL_USERNAME']],
            bcc=recipient_emails,
            body=full_message_body
        )

        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename != '':
                msg.attach(
                    filename=secure_filename(file.filename),
                    content_type=file.content_type,
                    data=file.read()
                )

        mail.send(msg)
        flash(f"✅ সফলভাবে {len(recipient_emails)} জন শিক্ষার্থীর কাছে ইমেইল নোটিশ পাঠানো হয়েছে ({target_group})!", "success")
    except Exception as e:
        print("Mail Sending Error:", traceback.format_exc())
        flash(f"❌ ইমেইল পাঠাতে ব্যর্থ হয়েছে: {str(e)}", "danger")

    return redirect(url_for('admin_panel'))

# ==================== DOSSIER API (EXACT STUDENT ID & COURSE MATCHING) ====================

@app.route('/admin/student-detail_<int:id>')
@app.route('/admin/student-detail/<int:id>')
@app.route('/admin/student_detail/<int:id>')
@app.route('/admin/student_details/<int:id>')
@app.route('/admin/get_student/<int:id>')
@app.route('/admin/student/<int:id>/details-json')
@login_required
def admin_get_student_json(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return jsonify({'error': 'Unauthorized'}), 403

    s = Student.query.get_or_404(id)

    db_uid = str(getattr(s, 'unique_id', '') or '').strip()
    db_roll = re.sub(r'\D', '', str(s.roll_no or '')).zfill(2)
    db_course = str(s.course or '').upper().strip()
    db_email = str(s.email or '').lower().strip()

    target = None
    for row in ALL_CSV_ROWS:
        r_course = str(row.get('Course:', '')).strip().upper()
        r_batch = str(row.get('Batch', '37')).strip()
        r_roll_raw = row.get('Class roll:', '') or row.get('Admission Roll No.', '') or ''
        r_roll = re.sub(r'\D', '', str(r_roll_raw)).zfill(2) if r_roll_raw else ""
        
        c_code = "2" if "BAMS" in r_course else "1"
        computed_uid = f"{r_batch}{c_code}{r_roll}"
        r_email = str(row.get('Email Address', '')).strip().lower()

        if (db_uid and computed_uid == db_uid) or (r_course == db_course and r_roll == db_roll) or (db_email and r_email == db_email):
            target = row
            break

    photo_url = getattr(s, 'photo', '') or ''
    dossier_data = {}

    if target:
        for k, v in target.items():
            if not k or k.strip().lower() == 'timestamp': 
                continue
            val_str = str(v).strip() if v is not None else ""

            if 'Upload Recent Passport Size Photo' in k or 'drive.google.com' in val_str:
                d_id = extract_drive_id(val_str)
                if d_id:
                    photo_url = f"https://drive.google.com/thumbnail?id={d_id}&sz=w600"
                continue

            if val_str != "" and val_str.lower() not in ['null', 'none', 'nan']:
                dossier_data[k.strip()] = val_str

    computed_id = db_uid or generate_diu_id(s.batch, s.course, s.roll_no)

    return jsonify({
        "status": "success",
        "name_english": target.get('Name (In English)') if target else s.name_english,
        "name_bangla": target.get('নাম (বাংলায়)') if target else s.name_bangla,
        "unique_id": computed_id,
        "course": getattr(s, 'course', 'BUMS'),
        "roll_no": getattr(s, 'roll_no', 'N/A'),
        "photo": photo_url,
        "dossier_data": dossier_data
    })

# ==================== LIVE ATTENDANCE & PERFORMANCE ====================

@app.route('/admin/live-attendance', methods=['GET', 'POST'])
@login_required
def admin_live_attendance():
    ADMIN_EMAILS = ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']
    if not current_user.email or current_user.email.lower().strip() not in ADMIN_EMAILS:
        return redirect(url_for('dashboard'))

    selected_course = request.args.get('course', 'BUMS')
    today_date = date.today().strftime('%Y-%m-%d')

    if request.method == 'POST':
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

    students = Student.query.filter_by(course=selected_course, is_approved=True).order_by(Student.roll_no).all()
    return render_template('live_attendance.html', students=students, selected_course=selected_course, today_date=today_date)

@app.route('/admin/student/<int:student_id>/performance', methods=['GET', 'POST'])
@login_required
def admin_student_performance(student_id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    
    student = Student.query.get_or_404(student_id)
    depts = Department.query.filter_by(course=student.course).order_by(Department.order.asc()).all()

    if request.method == 'POST':
        try:
            for d in depts:
                att = request.form.get(f'att_{d.id}', '')
                status = request.form.get(f'status_{d.id}', 'In Progress')

                perf = DepartmentPerformance.query.filter_by(student_id=student.id, department_id=d.id).first()
                if not perf:
                    perf = DepartmentPerformance(student_id=student.id, department_id=d.id)
                    db.session.add(perf)
                
                perf.attendance_rate = float(att) if att != '' else None
                perf.item_card_status = status

            db.session.commit()
            flash(f"Departmental evaluation updated for {student.name_english}!", "success")
            return redirect(url_for('admin_panel'))
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to update performance: {str(e)}", "danger")

    perf_map = {p.department_id: p for p in student.performances}
    return render_template('student_performance.html', student=student, departments=depts, perf_map=perf_map)

# ==================== STUDENT ACTIONS (MOVE, COPY, EDIT, APPROVE, DELETE) ====================

@app.route('/admin/student/approve/<int:id>', methods=['POST'])
@login_required
def admin_approve_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    student.is_approved = True
    db.session.commit()
    flash(f"✅ Approved {student.name_english} (Roll: {student.roll_no})!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/reject/<int:id>', methods=['POST'])
@login_required
def admin_reject_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    db.session.delete(student)
    db.session.commit()
    flash("Registration request rejected & removed.", "warning")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/impersonate/<int:id>')
@login_required
def admin_impersonate_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student_to_view = Student.query.get_or_404(id)
    session['admin_impersonator_email'] = current_user.email
    login_user(student_to_view)
    flash(f"Viewing as: {student_to_view.name_english}", "info")
    return redirect(url_for('dashboard'))

@app.route('/admin/student/exit-impersonate')
@login_required
def admin_exit_impersonate():
    admin_email = session.get('admin_impersonator_email')
    if not admin_email:
        return redirect(url_for('dashboard'))
    admin_user = Student.query.filter(db.func.lower(Student.email) == admin_email.lower().strip()).first()
    if admin_user:
        session.pop('admin_impersonator_email', None)
        login_user(admin_user)
        flash("Returned to Admin Control Panel.", "success")
        return redirect(url_for('admin_panel'))
    return redirect(url_for('login'))

@app.route('/admin/student/edit/<int:id>', methods=['POST'])
@login_required
def admin_edit_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    student.name_english = request.form.get('name_english', student.name_english).strip()
    student.name_bangla = request.form.get('name_bangla', student.name_bangla).strip()
    student.father_name = request.form.get('father_name', student.father_name).strip()
    student.mother_name = request.form.get('mother_name', student.mother_name).strip()
    student.email = request.form.get('email', student.email).strip().lower()
    student.course = request.form.get('course', student.course).strip().upper()
    student.batch = request.form.get('batch', student.batch).strip()
    student.roll_no = request.form.get('roll_no', student.roll_no).strip().zfill(2)
    student.class_roll = student.roll_no
    student.session = request.form.get('session', student.session).strip()
    student.unique_id = generate_diu_id(student.batch, student.course, student.roll_no)
    student.blood_group = request.form.get('blood_group', student.blood_group).strip()
    student.contact_number = request.form.get('contact_number', student.contact_number).strip()
    student.emergency_medical_contact = request.form.get('emergency_medical_contact', student.emergency_medical_contact).strip()
    
    f_occ = request.form.get('father_occupation', '').strip()
    m_occ = request.form.get('mother_occupation', '').strip()
    if hasattr(student, 'income_source_details') and (f_occ or m_occ):
        student.income_source_details = f"Father: {f_occ} | Mother: {m_occ}"
    
    new_custom_pass = request.form.get('custom_password', '').strip()
    if new_custom_pass:
        student.password_hash = generate_password_hash(new_custom_pass)
    
    raw_att = request.form.get('attendance', '')
    student.attendance = float(raw_att) if raw_att != '' else None
    
    db.session.commit()
    flash(f"Updated profile for {student.name_english}!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/move/<int:id>', methods=['POST'])
@login_required
def admin_move_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    target_course = request.form.get('target_course', '').upper()
    if target_course in ['BUMS', 'BAMS']:
        old_course = student.course
        student.course = target_course
        student.unique_id = generate_diu_id(student.batch, target_course, student.roll_no)
        db.session.commit()
        flash(f"Moved {student.name_english} from {old_course} to {target_course}!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/copy/<int:id>', methods=['POST'])
@login_required
def admin_copy_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    src = Student.query.get_or_404(id)
    clone_roll = f"{int(src.roll_no)+50 if src.roll_no.isdigit() else '99'}".zfill(2)
    clone_email = f"copy_{src.id}_{src.email}"
    clone = Student(
        email=clone_email,
        name_english=f"{src.name_english} (Copy)",
        name_bangla=src.name_bangla,
        father_name=src.father_name,
        mother_name=src.mother_name,
        course=src.course,
        batch=src.batch,
        roll_no=clone_roll,
        class_roll=clone_roll,
        session=src.session,
        unique_id=generate_diu_id(src.batch, src.course, clone_roll),
        blood_group=src.blood_group,
        contact_number=src.contact_number,
        emergency_medical_contact=src.emergency_medical_contact,
        guardian_contact=src.guardian_contact,
        present_address=src.present_address,
        permanent_address=src.permanent_address,
        attendance=src.attendance,
        is_approved=True,
        photo=src.photo,
        password_hash=src.password_hash or generate_password_hash('guamc123')
    )
    db.session.add(clone)
    db.session.commit()
    flash(f"Cloned copy created for {src.name_english}!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/reset-password/<int:id>', methods=['POST'])
@app.route('/admin/student/reset_password/<int:id>', methods=['POST'])
@login_required
def admin_reset_password(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    student.password_hash = generate_password_hash('guamc123')
    db.session.commit()
    flash(f"Password reset to default 'guamc123' for {student.name_english}", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/student/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_student(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    student = Student.query.get_or_404(id)
    Post.query.filter_by(student_id=student.id).delete()
    db.session.delete(student)
    db.session.commit()
    flash("Student removed.", "warning")
    return redirect(url_for('admin_panel'))

# ==================== DEPARTMENT, FOLDER & FILE MANAGEMENT ====================

@app.route('/admin/department/save', methods=['POST'])
@login_required
def admin_save_department():
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    dept_id = request.form.get('dept_id')
    name = request.form.get('name', '').strip()
    course = request.form.get('course', 'BAMS').strip().upper()
    order = int(request.form.get('order', 0))

    if dept_id:
        dept = Department.query.get(dept_id)
        if dept:
            dept.name = name
            dept.course = course
            dept.order = order
    else:
        db.session.add(Department(name=name, course=course, order=order))
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/department/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_department(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    dept = Department.query.get_or_404(id)
    db.session.delete(dept)
    db.session.commit()
    flash("Department removed.", "warning")
    return redirect(url_for('admin_panel'))

@app.route('/admin/folder/add', methods=['POST'])
@login_required
def admin_add_folder():
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    name = request.form.get('folder_name', '').strip()
    course = request.form.get('course', 'ALL').strip().upper()
    if name:
        db.session.add(FileFolder(name=name, course=course))
        db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/file/upload', methods=['POST'])
@login_required
def admin_upload_file():
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    title = request.form.get('title', '').strip()
    file_type = request.form.get('file_type', 'Item Card')
    course = request.form.get('course', 'ALL').upper()
    folder_id = request.form.get('folder_id') or None
    
    file_url = ""
    if 'file' in request.files and request.files['file'].filename != '':
        f = request.files['file']
        filename = f"file_{int(os.urandom(3).hex(), 16)}_{secure_filename(f.filename)}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(filepath)
        file_url = url_for('static', filename=f'uploads/{filename}')
    else:
        file_url = request.form.get('file_url', '').strip()

    if title and file_url:
        db.session.add(AcademicFile(title=title, file_type=file_type, course=course, file_url=file_url, folder_id=folder_id))
        db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/file/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_file(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    f = AcademicFile.query.get_or_404(id)
    db.session.delete(f)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/navigation/save', methods=['POST'])
@login_required
def admin_save_nav_link():
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    link_id = request.form.get('link_id')
    title = request.form.get('title', '').strip()
    url_val = request.form.get('endpoint_or_url', '').strip()
    icon = request.form.get('icon', '🔗').strip()
    order = int(request.form.get('order', 0))
    is_ext = True if request.form.get('is_external') == 'on' else False

    if link_id:
        link = NavigationLink.query.get(link_id)
        if link:
            link.title = title
            link.endpoint_or_url = url_val
            link.icon = icon
            link.order = order
            link.is_external = is_ext
            flash(f"Nav item '{title}' updated!", "success")
    else:
        new_link = NavigationLink(title=title, endpoint_or_url=url_val, icon=icon, order=order, is_external=is_ext)
        db.session.add(new_link)
        flash(f"Nav item '{title}' added!", "success")
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/navigation/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete_nav_link(id):
    if current_user.email.lower().strip() not in ['niloyxahc@gmail.com', 'moderndoctorsguamc@gmail.com']:
        return redirect(url_for('dashboard'))
    link = NavigationLink.query.get_or_404(id)
    db.session.delete(link)
    db.session.commit()
    flash("Nav item removed.", "info")
    return redirect(url_for('admin_panel'))

# ==================== GENERAL & USER PROFILE ROUTES ====================

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
        posts = Post.query.order_by(Post.created_at.desc()).all()
    except Exception:
        posts = []
    return render_template('discussions.html', posts=posts)

@app.route('/submit-post', methods=['GET', 'POST'])
@login_required
def submit_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category', 'General')
        if title and content:
            new_post = Post(title=title, content=content, category=category, student_id=current_user.id)
            db.session.add(new_post)
            db.session.commit()
            flash('Post published to Community Discussions!', 'success')
            return redirect(url_for('discussions'))
    return render_template('submit_post.html')

@app.route('/upload-photo', methods=['POST'])
@login_required
def upload_photo():
    if 'photo' not in request.files:
        return redirect(url_for('dashboard'))
    file = request.files['photo']
    if file and allowed_file(file.filename):
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
    else:
        flash('Invalid image format! Only PNG/JPG allowed.', 'danger')
        
    return redirect(url_for('dashboard'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
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
        return redirect(url_for('dashboard'))
    return render_template('change_password.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)