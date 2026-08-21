import csv
from app import app, db
from models import Student
from werkzeug.security import generate_password_hash

def init_db():
    with app.app_context():
        db.create_all()
        try:
            with open('students.csv', mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    existing_student = Student.query.filter_by(roll_no=row['Roll']).first()
                    if not existing_student:
                        student = Student(
                            roll_no=row['Roll'],
                            reg_no=row.get('Reg_No', ''),
                            session=row.get('Session', ''),
                            batch=row.get('Batch', '37th'),
                            course_type=row.get('Course', 'BUMS'),
                            name=row['Name'],
                            email=row['Email'],
                            phone=row.get('Phone', ''),
                            blood_group=row.get('Blood_Group', ''),
                            password_hash=generate_password_hash('guamc123')
                        )
                        db.session.add(student)
                db.session.commit()
                print("Database initialized and all batches classified successfully!")
        except Exception as e:
            print(f"Error importing data: {e}")

if __name__ == '__main__':
    init_db()