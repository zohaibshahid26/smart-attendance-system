from flask import session, redirect, url_for
from functools import wraps
import face_recognition
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv(override=True)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper function to convert image to face embedding
def get_face_embedding(image):
    try:
        face_locations = face_recognition.face_locations(image)
        if len(face_locations) == 0:
            return None
        face_encodings = face_recognition.face_encodings(image, face_locations)
        return face_encodings[0] if face_encodings else None
    except Exception as e:
        print("Error in get_face_embedding:", e)
        return None

def send_email(subject, recipient, body):
    sender_email = os.getenv("EMAIL")
    sender_password = os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, recipient, text)
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")

def send_attendance_email(name, timestamp, recipient):
    subject = "Attendance Confirmation - Smart Attendance System"
    body = (
        f"Dear {name},\n\n"
        f"This is to inform you that your attendance has been successfully recorded in the Smart Attendance System.\n"
        f"Date and Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"Thank you for your prompt attendance.\n\n"
        f"Best regards,\n"
        f"Smart Attendance System Team"
    )
    send_email(subject, recipient, body)
