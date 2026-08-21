import os
import csv
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'guamc-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///portal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models import db, Student
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(int(user_id))

# লগইন রাউট
@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard' if current_user.is_admin else 'dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        # অ্যাডমিন লগইন চেক
        if email == 'admin@guamc.edu.bd' and password == 'admin123':
            admin_user = Student.query.filter_by(email=email).first()
            if not admin_user:
                admin_user = Student(
                    roll_no='ADMIN01',
                    name='System Administrator',
                    email='admin@guamc.edu.bd',
                    batch='Admin',
                    course_type='Admin',
                    password_hash=generate_password_hash('admin123')
                )
                db.session.add(admin_user)
                db.session.commit()
            login_user(admin_user)
            return redirect(url_for('admin_dashboard'))

        student = Student.query.filter_by(email=email).first()
        if student and check_password_hash(student.password_hash, password):
            login_user(student)
            return redirect(url_for('admin_dashboard' if student.is_admin else 'dashboard'))
        else:
            flash('Invalid email or password!', 'danger')
            
    return render_template('login.html')

# স্টুডেন্ট ড্যাশবোর্ড রাউট (BAMS ও BUMS সাবজেক্ট ফিল্টারিং সহ)
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    if current_user.course_type == 'BAMS':
        subjects = [
            {"name": "1. Rachana Sharir (Anatomy)", "items": "8/10 Completed", "att": "87%"},
            {"name": "2. Kriya Sharir (Physiology)", "items": "9/10 Completed", "att": "86%"},
            {"name": "3. Padartha Vigyan", "items": "7/10 Completed", "att": "81%"},
            {"name": "4. Ashtanga Hridaya", "items": "10/10 Completed", "att": "89%"}
        ]
    else: # BUMS (Default)
        subjects = [
            {"name": "1. Tashrih (Anatomy)", "items": "8/10 Completed", "att": "88%"},
            {"name": "2. Munafeul Aza (Physiology)", "items": "9/10 Completed", "att": "85%"},
            {"name": "3. Kulliyat-e-Uloom-e-Paya", "items": "7/10 Completed", "att": "82%"},
            {"name": "4. Advia Mufreda (Materia Medica)", "items": "10/10 Completed", "att": "90%"}
        ]
        
    return render_template('dashboard.html', subjects=subjects)

# একাডেমিক রাউট (যদি নেভিগেশন বার থেকে কেউ এক্সেস করে, সরাসরি ড্যাশবোর্ডেই রিডাইরেক্ট হবে)
@app.route('/academic')
@login_required
def academic():
    return redirect(url_for('dashboard'))

# অ্যাডমিন ড্যাশবোর্ড রাউট
@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied!', 'danger')
        return redirect(url_for('dashboard'))
    students = Student.query.filter(Student.email != 'admin@guamc.edu.bd').all()
    return render_template('admin.html', students=students)

# লগআউট রাউট
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)