import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# সরাসরি Supabase ক্লাউড ডেটাবেস কানেকশন নিশ্চিত করা
os.environ["DATABASE_URL"] = "postgresql://postgres.jtrcktauvuotbnrsrnhz:Supabase_Secret_2026_GUAMC@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"

from app import app, db
try:
    from models import Student
except ImportError:
    from app import Student

# জিমেইল ও অ্যাপ পাসওয়ার্ড কনফিগারেশন
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "guamc.aims@gmail.com"
SENDER_PASSWORD = "kfrzcxchnzijxveo"

PORTAL_URL = "https://guamc-portal.onrender.com"

def send_welcome_email(recipient_email, student_name, student_roll):
    subject = "Welcome to GUAMC Student Portal - Your Login Access"
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #1e293b; line-height: 1.6; background-color: #f1f5f9; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background-color: #ffffff; padding: 30px; border-radius: 16px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
            <div style="text-align: center; margin-bottom: 25px;">
                <h2 style="color: #0f766e; margin: 0; font-size: 24px;">GUAMC Student Portal</h2>
                <p style="color: #64748b; margin: 4px 0 0 0; font-size: 14px;">Government Unani & Ayurvedic Medical College & Hospital</p>
            </div>
            
            <p>Dear <strong>{student_name}</strong>,</p>
            <p>Your student profile has been integrated into the official GUAMC Student Portal. You can now log in to monitor your academic dossier, exam records, attendance, and discussions.</p>
            
            <div style="background-color: #f8fafc; padding: 20px; border-radius: 12px; margin: 25px 0; border: 1px solid #cbd5e1;">
                <h4 style="margin-top: 0; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">Portal Login Details:</h4>
                <p style="margin: 8px 0;"><strong>Portal URL:</strong> <a href="{PORTAL_URL}" style="color: #0284c7; text-decoration: none; font-weight: bold;">{PORTAL_URL}</a></p>
                <p style="margin: 8px 0;"><strong>Login Email:</strong> <code style="background: #e2e8f0; padding: 3px 8px; border-radius: 6px; color: #0f172a; font-weight: bold;">{recipient_email}</code></p>
                <p style="margin: 8px 0;"><strong>Class Roll:</strong> {student_roll}</p>
                <p style="margin: 8px 0;"><strong>Default Password:</strong> <code style="background: #e2e8f0; padding: 3px 8px; border-radius: 6px; color: #0f172a; font-weight: bold;">guamc123</code> <span style="font-size: 12px; color: #64748b;">(if not changed)</span></p>
            </div>

            <p style="color: #e11d48; font-size: 13px; margin-bottom: 20px;"><em>* For security reasons, please change your password immediately after your first login via the dashboard.</em></p>
            
            <p style="margin-bottom: 0;">Best regards,</p>
            <p style="margin-top: 2px;"><strong>GUAMC Administration</strong></p>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"GUAMC Portal Admin <{SENDER_EMAIL}>"
    msg["To"] = recipient_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        print(f"✅ Sent: {student_name} -> {recipient_email}")
        return True
    except Exception as e:
        print(f"❌ Failed: {recipient_email} - {e}")
        return False

def broadcast():
    with app.app_context():
        students = Student.query.all()
        print(f"\n--- Supabase Database Connected: Found {len(students)} total students ---")
        
        valid_students = []
        for s in students:
            # আসল ব্যক্তিগত ইমেইল অগ্রাধিকার
            email = getattr(s, 'personal_email', None) or getattr(s, 'email', None)
            name = getattr(s, 'name_english', None) or getattr(s, 'name_bangla', None) or getattr(s, 'name', 'Student')
            roll = getattr(s, 'roll', 'N/A')
            
            # ডামি ইমেইল ফিল্টার আউট করা
            if email and '@' in email and not email.endswith('@guamc.edu.bd'):
                valid_students.append({'email': email.strip(), 'name': name, 'roll': roll})
            elif email and '@' in email:
                valid_students.append({'email': email.strip(), 'name': name, 'roll': roll})

        print(f"--- Dispatching to {len(valid_students)} students ---\n")
        
        success = 0
        for info in valid_students:
            if send_welcome_email(info['email'], info['name'], info['roll']):
                success += 1

        print(f"\n🎉 Completed! {success}/{len(valid_students)} emails dispatched.\n")

if __name__ == "__main__":
    broadcast()