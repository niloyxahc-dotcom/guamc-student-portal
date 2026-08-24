import csv
import os
from app import app, db
from models import Student

def import_master_data():
    with app.app_context():
        # ডেটাবেস টেবিল নিশ্চিত করা
        db.create_all()
        
        csv_file_path = 'master_students.csv'
        if not os.path.exists(csv_file_path):
            print(f"Error: {csv_file_path} not found!")
            return

        print("Reading CSV and syncing students...")
        
        with open(csv_file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                # CSV এর ফিল্ড অনুযায়ী ডেটা রিড করা
                roll_val = row.get('roll') or row.get('Roll') or row.get('ROLL')
                if not roll_val:
                    continue
                
                roll_str = str(roll_val).strip()
                
                # রোল দিয়ে খোঁজা, না থাকলে নতুন তৈরি
                student = Student.query.filter_by(roll=roll_str).first()
                if not student:
                    student = Student(roll=roll_str)
                    db.session.add(student)
                
                # অন্যান্য তথ্য আপডেট
                for key, val in row.items():
                    attr = key.strip().lower()
                    if hasattr(student, attr) and val:
                        setattr(student, attr, val.strip())
                
                count += 1

            db.session.commit()
            print(f"Successfully synced {count} students into database!")

if __name__ == '__main__':
    import_master_data()