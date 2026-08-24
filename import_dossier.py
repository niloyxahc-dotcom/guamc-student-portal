import sqlite3
import os
from app import app, db
from models import Student

def migrate_from_sqlite():
    with app.app_context():
        db.create_all()
        
        sqlite_file = 'portal_master_v14_permanent.db'
        if not os.path.exists(sqlite_file):
            print(f"SQLite file not found: {sqlite_file}")
            return

        print("Connecting to local SQLite database...")
        conn = sqlite3.connect(sqlite_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check existing tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Found tables: {tables}")

        target_table = 'student' if 'student' in tables else ('students' if 'students' in tables else tables[0])
        print(f"Extracting from table: {target_table}")

        cursor.execute(f"SELECT * FROM {target_table}")
        rows = cursor.fetchall()
        print(f"Total records found in SQLite: {len(rows)}")

        if not rows:
            print("No records found in SQLite database.")
            return

        # Clear existing dummy data in Supabase
        print("Clearing dummy data from Supabase...")
        try:
            db.session.query(Student).delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Table clear note: {e}")

        # Insert real students
        count = 0
        for row in rows:
            row_dict = dict(row)
            student = Student()
            
            for key, val in row_dict.items():
                if hasattr(student, key) and val is not None:
                    setattr(student, key, val)
            
            db.session.add(student)
            count += 1

        db.session.commit()
        print(f"=== SUCCESS: Successfully migrated {count} real students to Supabase! ===")
        conn.close()

if __name__ == '__main__':
    migrate_from_sqlite()