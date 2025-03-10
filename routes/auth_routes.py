from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, make_response
from pymongo import MongoClient
from datetime import datetime, timedelta
import dateutil.parser
from bcrypt import checkpw, hashpw, gensalt
import random
import os
import smtplib
from email.mime.text import MIMEText
from utils import login_required, student_login_required


auth_bp = Blueprint('auth', __name__, template_folder="templates")

# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["attendance_db"]
admin_collection = db["admin"]
users_collection = db["users"]

# Helper function to send OTP
def send_otp(email, otp):
    try:
        msg = MIMEText(f"Your OTP for password reset is: {otp}")
        msg['Subject'] = 'Password Reset OTP'
        msg['From'] = os.getenv("EMAIL")
        msg['To'] = email

        with smtplib.SMTP(os.getenv("SMTP_SERVER"), os.getenv("SMTP_PORT")) as server:
            server.starttls()
            server.login(os.getenv("EMAIL"), os.getenv("EMAIL_PASSWORD"))
            server.sendmail(os.getenv("EMAIL"), email, msg.as_string())
    except Exception as e:
        print("Error in send_otp:", e)

# Route to render login page
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Clear any existing conflicting sessions
    if 'student' in session:
        session.pop('student', None)
        
    if 'admin' in session:
        return redirect(url_for('home'))
        
    if request.method == "POST":
        data = request.json
        username = data.get("username")
        password = data.get("password")
        admin = admin_collection.find_one({"username": username})
        
        if admin and checkpw(password.encode('utf-8'), admin["password"].encode('utf-8')):
            # Set session with explicit max age
            session.permanent = True
            session['admin'] = username
            
            # Return the same response format as before
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Invalid credentials"})
            
    return render_template("login.html")

# Route to render forget password page
@auth_bp.route("/forget_password", methods=["GET", "POST"])
def forget_password():
    if request.method == "POST":
        data = request.json
        username = data.get("username")
        admin = admin_collection.find_one({"username": username})
        
        if admin:
            # Generate a new OTP
            otp = random.randint(100000, 999999)
            
            # Set dedicated reset session data
            session['reset_data'] = {
                'otp': otp,
                'username': username,
                'expiry': (datetime.utcnow() + timedelta(minutes=2)).isoformat()
            }
            
            send_otp(admin["email"], otp)
            return jsonify({"success": True, "email": admin["email"]})
        else:
            return jsonify({"success": False, "message": "Invalid username"})
            
    return render_template("forget_password.html")

# Route to resend OTP
@auth_bp.route("/resend_otp", methods=["POST"])
def resend_otp():
    # Get reset data from session
    reset_data = session.get('reset_data', {})
    username = reset_data.get('username')
    
    if username:
        admin = admin_collection.find_one({"username": username})
        if admin:
            otp = random.randint(100000, 999999)
            
            # Update session with new OTP and expiry
            reset_data['otp'] = otp
            reset_data['expiry'] = (datetime.utcnow() + timedelta(minutes=2)).isoformat()
            session['reset_data'] = reset_data
            
            send_otp(admin["email"], otp)
            return jsonify({"success": True})
            
    return jsonify({"success": False, "message": "Failed to resend OTP"})

# Route to verify OTP
@auth_bp.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        data = request.json
        otp = data.get("otp")
        
        # Get reset data from session
        reset_data = session.get('reset_data', {})
        session_otp = reset_data.get('otp')
        expiry_str = reset_data.get('expiry')
        
        if session_otp and session_otp == int(otp) and expiry_str:
            try:
                expiry_time = dateutil.parser.isoparse(expiry_str)
                if datetime.utcnow() < expiry_time:
                    # Mark OTP as verified but keep all data
                    reset_data['verified'] = True
                    session['reset_data'] = reset_data
                    
                    return jsonify({"success": True})
                else:
                    return jsonify({"success": False, "message": "OTP expired"})
            except (ValueError, TypeError):
                return jsonify({"success": False, "message": "Session error, please try again"})
        else:
            return jsonify({"success": False, "message": "Invalid OTP"})
            
    return render_template("verify_otp.html")

# Route to reset password
@auth_bp.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        data = request.json
        new_password = data.get("new_password")
        
        # Get reset data from session
        reset_data = session.get('reset_data', {})
        username = reset_data.get('username')
        verified = reset_data.get('verified', False)
        
        if username and verified:
            hashed_password = hashpw(new_password.encode('utf-8'), gensalt())
            admin_collection.update_one({"username": username}, 
                                       {"$set": {"password": hashed_password.decode('utf-8')}})
            
            # Clean up session
            if 'reset_data' in session:
                session.pop('reset_data')
                
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Session expired or OTP not verified"})
            
    return render_template("reset_password.html")

@auth_bp.route("/student/login", methods=["GET", "POST"])
def student_login():
    # Clear any existing admin session to prevent conflicts
    if 'admin' in session:
        session.pop('admin', None)
        
    if 'student' in session:
        return redirect(url_for('student.dashboard'))
        
    if request.method == "POST":
        data = request.json
        email = data.get("email")
        password = data.get("password")
        student = users_collection.find_one({"email": email})
        
        if student and checkpw(password.encode('utf-8'), student["password"].encode('utf-8')):
            # Set session with explicit max age
            session.permanent = True
            
            # Keep the same session structure
            session['student'] = {
                'id': str(student["_id"]),
                "email": student["email"],
                "name": student["name"]
            }
            
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Invalid credentials"})
            
    return render_template("student/login.html")

@auth_bp.route("/student/logout")
@student_login_required
def student_logout():
    # Remove only student data but maintain the same signature
    session.pop('student', None)
    
    # Ensure cookie headers are set properly
    response = redirect(url_for('auth.student_login'))
    return response

@auth_bp.route("/logout")
@login_required
def logout():
    # Remove only admin data but maintain the same signature
    session.pop('admin', None)
    
    # Ensure cookie headers are set properly
    response = redirect(url_for('auth.login'))
    return response