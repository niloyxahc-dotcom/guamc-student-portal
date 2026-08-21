import re
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Student, Notice, Article, ClubMembership, ExamClearance, ExamResult, StudentRepresentative, VideoVlog, ForumTopic, ForumReply

app = Flask(__name__)
app.config['SECRET_KEY'] = 'guamc-secret-portal-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///portal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Student, int(user_id))

def extract_youtube_id(url):
    match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
    return match.group(1) if match else url.strip()

@app.before_request
def setup_defaults():
    db.create_all()
    if not Notice.query.first():
        sample_notice = Notice(
            title="1st Year BUMS & BAMS Professional Exam & Term-2 Schedule",
            content="Students are instructed to complete card sign-offs and verify minimum 75% attendance for examination eligibility.",
            author="Academic Council"
        )
        db.session.add(sample_notice)
    if not Article.query.first():
        sample_article = Article(
            title="Phytochemical Screening & Evidence-Based Formulations",
            author="Academic Research Cell",
            summary="A comprehensive overview of standardized phytomedicine extraction and modern clinical applications.",
            link="https://pubmed.ncbi.nlm.nih.gov/"
        )
        db.session.add(sample_article)
    db.session.commit()

@app.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_panel'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_panel'))
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        student = Student.query.filter_by(email=email).first()

        if student and check_password_hash(student.password, password):
            login_user(student)
            if student.is_admin:
                return redirect(url_for('admin_panel'))
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid Email or Password. Please try again.', 'error')

    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    notices = Notice.query.order_by(Notice.created_at.desc()).all()
    my_clubs = [c.club_name for c in current_user.clubs]
    clearance = ExamClearance.query.filter_by(student_id=current_user.id).first()
    return render_template('dashboard.html', notices=notices, my_clubs=my_clubs, clearance=clearance)

@app.route('/id-card')
@login_required
def id_card():
    clearance = ExamClearance.query.filter_by(student_id=current_user.id).first()
    return render_template('id_card.html', clearance=clearance)

@app.route('/results')
@login_required
def results():
    student_results = ExamResult.query.filter_by(student_id=current_user.id).order_by(ExamResult.published_at.desc()).all()
    clearance = ExamClearance.query.filter_by(student_id=current_user.id).first()
    total_obtained = sum(r.total_marks for r in student_results)
    avg_score = round(total_obtained / len(student_results), 1) if student_results else 0.0
    return render_template('results.html', results=student_results, clearance=clearance, avg_score=avg_score)

@app.route('/representatives')
@login_required
def representatives():
    bums_reps = StudentRepresentative.query.filter_by(course="BUMS").all()
    bams_reps = StudentRepresentative.query.filter_by(course="BAMS").all()
    return render_template('representatives.html', bums_reps=bums_reps, bams_reps=bams_reps)

@app.route('/academic')
@login_required
def academic():
    resources = {
        "ebooks": [
            {"title": "BD Chaurasia's Human Anatomy (Vol 1-3)", "category": "Anatomy", "link": "#"},
            {"title": "Guyton and Hall Textbook of Medical Physiology", "category": "Physiology", "link": "#"},
            {"title": "Trease and Evans Pharmacognosy", "category": "Pharmacognosy", "link": "#"},
            {"title": "Al-Qanoon Fi Al-Tibb (The Canon of Medicine)", "category": "Unani Principles", "link": "#"}
        ],
        "sheets": [
            {"title": "Autonomic Nervous System Drug Classifications", "author": "Dept. of Pharmacology", "link": "#"},
            {"title": "Cranial Nerves Clinical Examination Notes", "author": "Dept. of Anatomy", "link": "#"},
            {"title": "Cardiovascular Physiology & ECG Interpretation", "author": "Dept. of Physiology", "link": "#"}
        ],
        "questions": [
            {"title": "1st Professional Examination Question Bank (DU)", "type": "Comprehensive Archive", "link": "#"},
            {"title": "2nd Professional Examination Past Papers", "type": "Subject-wise", "link": "#"},
            {"title": "OSPE & Practical Viva Sample Question Cards", "type": "Practical/Viva", "link": "#"}
        ]
    }
    return render_template('academic.html', resources=resources)

@app.route('/exam-guidance')
@login_required
def exam_guidance():
    prof_structure = [
        {
            "prof": "1st Professional Examination (1.5 Years)",
            "terms": "Term-1 & Term-2",
            "subjects": ["Anatomy & Histology (Tashreeh)", "Physiology & Biochemistry (Munafeul Aza)", "Kulliyat / Basic Principles", "Language (Arabic/Sanskrit)"],
            "criteria": "Minimum 75% attendance + All Card items and 2 Terms clearance."
        },
        {
            "prof": "2nd Professional Examination (1 Year)",
            "terms": "Annual Assessment",
            "subjects": ["Pharmacognosy & Materia Medica (Ilmul Advia / Dravyaguna)", "Pathology & Microbiology (Mahiyatul Amraz)", "Community Medicine (Tahaffuzi wa Samaji Tib)"],
            "criteria": "Minimum 75% attendance + Practical Lab & Herbarium sheet submission."
        },
        {
            "prof": "3rd Professional Examination (1 Year)",
            "terms": "Annual Assessment",
            "subjects": ["Clinical Bedside Methods (Sareeriyat / Roga Nidan)", "Forensic Medicine & Toxicology (Tibbe Qanooni)", "Pharmacy & Formulation (Ilmul Saidla)", "Regimenal Therapy (Ilaj bit Tadbeer / Panchakarma)"],
            "criteria": "Minimum 75% attendance + Hospital Ward logbook & Case presentation clearance."
        },
        {
            "prof": "4th / Final Professional Examination (1 Year)",
            "terms": "Annual Assessment",
            "subjects": ["Internal Medicine (Moalajat / Kayachikitsa)", "General Surgery (Ilmul Jarahat / Shalya Tantra)", "Gynae & Obstetrics (Amraze Niswan wa Qabalat)", "Eye & ENT (Ain-Uzn-Anaf-Halaq)", "Paediatrics (Amraze Atfal)"],
            "criteria": "Clearing all 4 Professional exams is mandatory for 1-year clinical internship."
        }
    ]
    clearance = ExamClearance.query.filter_by(student_id=current_user.id).first()
    return render_template('exam_guidance.html', prof_structure=prof_structure, clearance=clearance)

@app.route('/clubs', methods=['GET', 'POST'])
@login_required
def clubs():
    available_clubs = [
        {"name": "Debating Club", "desc": "National and inter-medical college debate competitions, public speaking, and argumentation workshops."},
        {"name": "Photographic Society", "desc": "Campus photography, documentary making, visual arts, and event coverage."},
        {"name": "Cultural Club", "desc": "Music, drama, literary events, stage performances, and national day celebrations."},
        {"name": "Career & Skill development Club", "desc": "Medical research methodology, computer skills, higher study preparation, and leadership development."}
    ]
    
    if request.method == 'POST':
        selected_clubs = request.form.getlist('clubs')
        ClubMembership.query.filter_by(student_id=current_user.id).delete()
        
        if "Not interested" not in selected_clubs:
            for club_name in selected_clubs:
                membership = ClubMembership(student_id=current_user.id, club_name=club_name)
                db.session.add(membership)
        
        db.session.commit()
        flash('Club preferences updated successfully!', 'success')
        return redirect(url_for('clubs'))
        
    my_clubs = [c.club_name for c in current_user.clubs]
    return render_template('clubs.html', clubs=available_clubs, my_clubs=my_clubs)

@app.route('/vlogs')
@login_required
def vlogs():
    vlogs_list = VideoVlog.query.order_by(VideoVlog.created_at.desc()).all()
    return render_template('vlogs.html', vlogs=vlogs_list)

@app.route('/articles')
@login_required
def articles():
    articles_list = Article.query.order_by(Article.created_at.desc()).all()
    return render_template('articles.html', articles=articles_list)

@app.route('/submit-post', methods=['GET', 'POST'])
@login_required
def submit_post():
    if request.method == 'POST':
        post_type = request.form.get('post_type')
        title = request.form.get('title')
        content_url = request.form.get('content_url')
        description = request.form.get('description')
        
        if post_type == 'vlog':
            v_id = extract_youtube_id(content_url)
            new_vlog = VideoVlog(title=title, submitted_by=current_user.name, video_id=v_id)
            db.session.add(new_vlog)
            db.session.commit()
            flash('Campus Vlog submitted and published!', 'success')
            return redirect(url_for('vlogs'))
            
        elif post_type == 'article':
            new_article = Article(title=title, author=current_user.name, summary=description, link=content_url)
            db.session.add(new_article)
            db.session.commit()
            flash('Medical Article published successfully!', 'success')
            return redirect(url_for('articles'))
            
        elif post_type == 'routine':
            new_notice = Notice(title=f"Class/Exam Routine: {title}", content=description, author=f"{current_user.name} ({current_user.course})")
            db.session.add(new_notice)
            db.session.commit()
            flash('Routine / Notice shared on dashboard!', 'success')
            return redirect(url_for('dashboard'))

    return render_template('submit_post.html')

@app.route('/forum')
@login_required
def forum():
    tag = request.args.get('tag', 'All')
    if tag and tag != 'All':
        topics = ForumTopic.query.filter_by(course_tag=tag).order_by(ForumTopic.created_at.desc()).all()
    else:
        topics = ForumTopic.query.order_by(ForumTopic.created_at.desc()).all()
    return render_template('forum.html', topics=topics, selected_tag=tag)

@app.route('/forum/new', methods=['POST'])
@login_required
def new_topic():
    title = request.form.get('title')
    content = request.form.get('content')
    course_tag = request.form.get('course_tag', 'General')
    if title and content:
        topic = ForumTopic(title=title, content=content, author_name=current_user.name, course_tag=course_tag)
        db.session.add(topic)
        db.session.commit()
        flash('Discussion topic started successfully!', 'success')
    return redirect(url_for('forum'))

@app.route('/forum/reply/<int:topic_id>', methods=['POST'])
@login_required
def reply_topic(topic_id):
    content = request.form.get('content')
    if content:
        reply = ForumReply(topic_id=topic_id, author_name=current_user.name, content=content)
        db.session.add(reply)
        db.session.commit()
        flash('Your reply has been posted.', 'success')
    return redirect(url_for('forum'))

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    students = Student.query.filter_by(is_admin=False).all()
    notices = Notice.query.order_by(Notice.created_at.desc()).all()
    articles = Article.query.order_by(Article.created_at.desc()).all()
    return render_template('admin.html', students=students, notices=notices, articles=articles)

@app.route('/admin/add-notice', methods=['POST'])
@login_required
def admin_add_notice():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    title = request.form.get('title')
    content = request.form.get('content')
    if title and content:
        notice = Notice(title=title, content=content, author="Principal's Office")
        db.session.add(notice)
        db.session.commit()
        flash('New Notice published successfully!', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete-notice/<int:id>')
@login_required
def admin_delete_notice(id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    notice = db.session.get(Notice, id)
    if notice:
        db.session.delete(notice)
        db.session.commit()
        flash('Notice removed.', 'info')
    return redirect(url_for('admin_panel'))

@app.route('/admin/add-article', methods=['POST'])
@login_required
def admin_add_article():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    title = request.form.get('title')
    author = request.form.get('author')
    summary = request.form.get('summary')
    link = request.form.get('link')
    if title and summary:
        article = Article(title=title, author=author, summary=summary, link=link)
        db.session.add(article)
        db.session.commit()
        flash('Article added successfully!', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not check_password_hash(current_user.password, current_password):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('change_password'))

        if len(new_password) < 6:
            flash('New password must be at least 6 characters long.', 'error')
            return redirect(url_for('change_password'))

        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('change_password'))

        current_user.password = generate_password_hash(new_password)
        db.session.commit()
        flash('Password updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('change_password.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)