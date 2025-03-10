from bson import ObjectId
from bcrypt import checkpw, gensalt, hashpw
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from pymongo import MongoClient
import os
from utils import student_login_required

student_bp = Blueprint('student', __name__, template_folder="templates")

# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["attendance_db"]
users_collection = db["users"]
attendance_collection = db["attendance"]

# Student login route
@student_bp.route("/student/login", methods=["GET", "POST"])
def login():
    if 'student' in session:
        return redirect(url_for('student.dashboard'))
    
    if request.method == "POST":
        data = request.json
        email = data.get("email")
        password = data.get("password")
        
        student = users_collection.find_one({"email": email})
        if student and checkpw(password.encode('utf-8'), student["password"].encode('utf-8')):
            # Create session for student
            session['student'] = {
                'id': str(student["_id"]),
                'name': student["name"],
                'email': student["email"]
            }
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Invalid credentials"})
    
    return render_template("student/login.html")

# Student logout route
@student_bp.route("/student/logout")
@student_login_required
def logout():
    session.pop('student', None)
    return redirect(url_for('student.login'))

# Student dashboard route
@student_bp.route("/student/dashboard")
@student_login_required
def dashboard():
    student_id = session['student']['id']
    student = users_collection.find_one({"_id": ObjectId(student_id)})
    
    # Fetch attendance records for the student
    attendance_records = list(attendance_collection.find({"student_id": ObjectId(student_id)}))
    
    # Calculate stats
    total_days = len(attendance_records)
    present_days = sum(1 for record in attendance_records if record["status"] == "Present")
    absent_days = total_days - present_days
    attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
    
    stats = {
        "attendance_percentage": attendance_percentage,
        "present_days": present_days,
        "absent_days": absent_days
    }
    
    # Prepare chart data
    chart_data = {
        "labels": [record["timestamp"].split(" ")[0] for record in attendance_records],
        "data": [1 if record["status"] == "Present" else 0 for record in attendance_records]
    }
    
    # Format attendance records
    for record in attendance_records:
        record["_id"] = str(record["_id"])
        record["timestamp"] = record["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
    
    return render_template("student/dashboard.html", student=student, attendance_records=attendance_records, stats=stats, chart_data=chart_data)

# Student profile route
@student_bp.route("/student/profile")
@student_login_required
def profile():
    student_id = session['student']['id']
    student = users_collection.find_one({"_id": ObjectId(student_id)})
    return render_template("student/profile.html", student=student)

# Update student profile route
@student_bp.route("/student/profile/update", methods=["POST"])
@student_login_required
def update_profile():
    student_id = session['student']['id']
    data = request.json
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    update_data = {"name": name, "email": email}
    if password:
        hashed_password = hashpw(password.encode('utf-8'), gensalt())
        update_data["password"] = hashed_password.decode('utf-8')

    users_collection.update_one({"_id": ObjectId(student_id)}, {"$set": update_data})
    session['student']['name'] = name
    session['student']['email'] = email

    return jsonify({"success": True, "message": "Profile updated successfully"})

# Student attendance history route
@student_bp.route("/student/attendance_history")
@student_login_required
def attendance_history():
    student_id = session['student']['id']
    attendance_records = list(attendance_collection.find({"student_id": ObjectId(student_id)}))
    
    # Format attendance records
    for record in attendance_records:
        record["_id"] = str(record["_id"])
        record["timestamp"] = record["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
    
    return render_template("student/attendance_history.html", attendance_records=attendance_records)
