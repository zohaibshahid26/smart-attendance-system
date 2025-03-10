from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from pymongo import MongoClient
from datetime import datetime, timedelta
import dateutil.parser  # Add this import
from bcrypt import checkpw, hashpw, gensalt
import random
import os
import smtplib
from email.mime.text import MIMEText
from utils import login_required

auth_bp = Blueprint('auth', __name__, template_folder="templates")

# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["attendance_db"]
admin_collection = db["admin"]

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
    if 'admin' in session:
        return redirect(url_for('home'))
    if request.method == "POST":
        data = request.json
        username = data.get("username")
        password = data.get("password")
        admin = admin_collection.find_one({"username": username})
        if admin and checkpw(password.encode('utf-8'), admin["password"].encode('utf-8')):
            session['admin'] = username
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
            otp = random.randint(100000, 999999)
            session['otp'] = otp
            # Store expiry as ISO format string
            session['otp_expiry'] = (datetime.utcnow() + timedelta(minutes=2)).isoformat()
            session['username'] = username
            send_otp(admin["email"], otp)
            return jsonify({"success": True, "email": admin["email"]})
        else:
            return jsonify({"success": False, "message": "Invalid username"})
    return render_template("forget_password.html")

# Route to resend OTP
@auth_bp.route("/resend_otp", methods=["POST"])
def resend_otp():
    username = session.get('username')
    if username:
        admin = admin_collection.find_one({"username": username})
        if admin:
            otp = random.randint(100000, 999999)
            session['otp'] = otp
            # Store expiry as ISO format string
            session['otp_expiry'] = (datetime.utcnow() + timedelta(minutes=2)).isoformat()
            send_otp(admin["email"], otp)
            return jsonify({"success": True})
    return jsonify({"success": False, "message": "Failed to resend OTP"})

# Route to verify OTP
@auth_bp.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        data = request.json
        otp = data.get("otp")
        if 'otp' in session and session['otp'] == int(otp):
            # Parse the stored datetime string back to datetime object
            try:
                expiry_time = dateutil.parser.isoparse(session['otp_expiry'])
                if datetime.utcnow() < expiry_time:
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
        username = session.get('username')
        if username:
            hashed_password = hashpw(new_password.encode('utf-8'), gensalt())
            admin_collection.update_one({"username": username}, {"$set": {"password": hashed_password.decode('utf-8')}})
            session.pop('otp', None)
            session.pop('username', None)
            session.pop('otp_expiry', None)
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Session expired"})
    return render_template("reset_password.html")

# Route to logout
@auth_bp.route("/logout")
@login_required
def logout():
    session.pop('admin', None)
    return redirect(url_for('auth.login'))