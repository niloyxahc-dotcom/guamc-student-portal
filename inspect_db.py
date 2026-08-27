from app import app, db, Student

with app.app_context():
    # রোল ০৫ এর ডাটা চেক
    s = Student.query.filter(Student.roll_no.in_(['05', '5'])).first()
    if not s:
        print("❌ Student not found!")
    else:
        print("=== Database Record for Roll 05 ===")
        print("Name:", s.name_english)
        print("Father Name in DB:", getattr(s, 'father_name', 'N/A'))
        print("Father Occ in DB:", getattr(s, 'father_occupation', 'N/A'))
        print("Mother Name in DB:", getattr(s, 'mother_name', 'N/A'))
        print("Mother Occ in DB:", getattr(s, 'mother_occupation', 'N/A'))
        print("Guardian Contact:", getattr(s, 'guardian_contact', 'N/A'))