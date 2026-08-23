import csv
from app import app, db
from models import Student
from werkzeug.security import generate_password_hash

def init_db():
    with app.app_context():
        db.create_all()
        try:
            model_columns = {c.name for c in Student.__table__.columns}
            
            with open('master_students.csv', mode='r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                count = 0
                
                for idx, raw_row in enumerate(reader, start=1):
                    # কলামের নামের স্পেস ও ক্যাপিটালাইজেশন ট্রিম করা
                    row = {str(k).strip().lower(): str(v).strip() for k, v in raw_row.items() if k}
                    
                    # রোল নম্বর খোঁজার সম্ভাব্য সব নাম
                    roll = None
                    for key in ['roll', 'roll_no', 'roll no', 'class_roll', 'class roll', 'sl', 'id']:
                        if key in row and row[key]:
                            roll = row[key]
                            break
                    if not roll:
                        roll = str(idx)
                    
                    roll = roll.zfill(2)
                    batch = row.get('batch') or '37th'
                    course = (row.get('course') or 'BUMS').upper()
                    
                    # নাম খোঁজা
                    name = None
                    for key in ['name', 'name_english', 'student_name', 'student name', 'full_name']:
                        if key in row and row[key]:
                            name = row[key]
                            break
                    if not name:
                        name = f"Student {roll}"

                    # ইমেইল খোঁজা
                    email = row.get('email')
                    if not email:
                        email = f"student_{course.lower()}_{batch.lower()}_{roll}@guamc.edu.bd"

                    existing = Student.query.filter(
                        (Student.roll_no == roll) & (Student.batch == batch) & (Student.course == course)
                    ).first()
                    
                    if not existing:
                        hashed_pw = generate_password_hash('guamc123')
                        student_data = {
                            'roll_no': roll,
                            'session': row.get('session', ''),
                            'batch': batch,
                            'course': course,
                            'email': email,
                            'is_approved': True
                        }
                        
                        if 'name_english' in model_columns:
                            student_data['name_english'] = name
                        elif 'name' in model_columns:
                            student_data['name'] = name

                        if 'name_bangla' in model_columns:
                            student_data['name_bangla'] = row.get('name_bangla') or row.get('bangla_name', '')

                        if 'password_hash' in model_columns:
                            student_data['password_hash'] = hashed_pw
                        elif 'password' in model_columns:
                            student_data['password'] = hashed_pw

                        if 'class_roll' in model_columns:
                            student_data['class_roll'] = roll

                        student = Student(**student_data)
                        db.session.add(student)
                        count += 1

                db.session.commit()
                print(f"Successfully imported {count} students into Supabase Database!")
                
        except Exception as e:
            db.session.rollback()
            print(f"Error importing data: {e}")

if __name__ == '__main__':
    init_db()