from flask import Blueprint, request, jsonify, render_template, Response, session, redirect, url_for
from pymongo import MongoClient
import numpy as np
import cv2
import face_recognition
from datetime import datetime
from scipy.spatial.distance import euclidean
import csv
from io import StringIO
import threading
import os
from utils import get_face_embedding, login_required, send_attendance_email

attendance_bp = Blueprint('attendance', __name__, template_folder="templates")

# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["attendance_db"]
users_collection = db["users"]
attendance_collection = db["attendance"]

# Background thread for video capture
class VideoStream:
    def __init__(self):
        self.cap = None
        self.frame = None
        self.running = False
        self.thread = None

    def start(self):
        if not self.running:
            self.cap = cv2.VideoCapture(0)
            self.running = True
            self.thread = threading.Thread(target=self.update, daemon=True)
            self.thread.start()

    def update(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self.frame = frame

    def get_frame(self):
        return self.frame

    def stop(self):
        if self.running:
            self.running = False
            self.thread.join()
            self.cap.release()
            self.cap = None

video_stream = VideoStream()

# Route to process live camera feed
@attendance_bp.route("/video_feed")
def video_feed():
    video_stream.start()
    try:
        def generate_frames():
            while video_stream.running:
                frame = video_stream.get_frame()
                if frame is None:
                    continue
                
                # Flip the frame horizontally
                frame = cv2.flip(frame, 1)
                
                face_locations = face_recognition.face_locations(frame)
                for (top, right, bottom, left) in face_locations:
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                
                _, buffer = cv2.imencode(".jpg", frame)
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")
    except Exception as e:
        print("Error in video_feed:", e)
        return jsonify({"error": str(e)}), 500

# Route to render the live feed page for marking attendance
@attendance_bp.route("/mark_attendance", methods=["GET"])
@login_required
def mark_attendance_page():
    try:
        video_stream.start()
        return render_template("live_feed.html")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@attendance_bp.route("/stop_camera", methods=["POST"])
@login_required
def stop_camera():
    try:
        video_stream.stop()
        return jsonify({"message": "Camera stopped"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to capture and recognize face for attendance
@attendance_bp.route("/mark_attendance", methods=["POST"])
@login_required
def mark_attendance():
    video_stream.start()
    try:
        frame = video_stream.get_frame()
        if frame is None:
            return jsonify({"error": "No frame captured"}), 400
        
        # Get face embedding
        input_embedding = get_face_embedding(frame)
        if input_embedding is None:
            return jsonify({"error": "No face detected"}), 400
        
        # Compare embeddings with registered users using Euclidean Distance
        users = list(users_collection.find({}, {"_id": 0, "name": 1, "face_embedding": 1, "email": 1}))
        
        best_match = None
        min_distance = float("inf")
        best_match_email = None
        
        for user in users:
            stored_embedding = np.array(user["face_embedding"], dtype=np.float16)
            distance = euclidean(stored_embedding, input_embedding)
            if distance < 0.5:  # Adjust threshold as needed
                if distance < min_distance:
                    min_distance = distance
                    best_match = user["name"]
                    best_match_email = user["email"]
        
        if best_match:
            # Check if attendance already marked for today
            today = datetime.utcnow()
            start_of_day = datetime(today.year, today.month, today.day)
            end_of_day = datetime(today.year, today.month, today.day, 23, 59, 59)
            
            existing_attendance = attendance_collection.find_one({
                "name": best_match,
                "timestamp": {"$gte": start_of_day, "$lte": end_of_day}
            })
            
            if existing_attendance:
                # Attendance already marked
                attendance_time = existing_attendance["timestamp"].strftime("%I:%M %p")
                return jsonify({
                    "message": f"Attendance already marked at {attendance_time}",
                    "name": best_match,
                    "alreadyMarked": True,
                    "time": attendance_time
                })
            
            # Mark new attendance
            timestamp = datetime.utcnow()
            attendance_collection.insert_one({"name": best_match, "timestamp": timestamp})
            send_attendance_email(best_match, timestamp, best_match_email)
            return jsonify({
                "message": "Attendance marked successfully", 
                "name": best_match,
                "alreadyMarked": False,
                "time": timestamp.strftime("%I:%M %p")
            })
        
        return jsonify({"error": "Face not recognized"}), 400
    except Exception as e:
        print("Error in mark_attendance:", e)
        return jsonify({"error": str(e)}), 500

# Route to render the attendance records page
@attendance_bp.route("/get_attendance", methods=["GET"])
@login_required
def get_attendance_page():
    try:
        return render_template("attendance_records.html")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to fetch attendance records
@attendance_bp.route("/fetch_attendance", methods=["GET"])
@login_required
def fetch_attendance():
    try:
        date_str = request.args.get("date")
        date = datetime.strptime(date_str, "%Y-%m-%d")
        start = datetime(date.year, date.month, date.day)
        end = datetime(date.year, date.month, date.day, 23, 59, 59)
        
        records = list(attendance_collection.find({"timestamp": {"$gte": start, "$lt": end}}))
        for record in records:
            user = users_collection.find_one({"name": record["name"]}, {"_id": 0, "email": 1, "phone": 1})
            record["_id"] = str(record["_id"])
            record["timestamp"] = record["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            if user:
                record["email"] = user["email"]
                record["phone"] = user["phone"]
        
        return jsonify(records)
    except Exception as e:
        print("Error in fetch_attendance:", e)
        return jsonify({"error": str(e)}), 500

# Route to export attendance records as CSV
@attendance_bp.route("/export_attendance", methods=["GET"])
@login_required
def export_attendance():
    try:
        date_str = request.args.get("date")
        date = datetime.strptime(date_str, "%Y-%m-%d")
        start = datetime(date.year, date.month, date.day)
        end = datetime(date.year, date.month, date.day, 23, 59, 59)
        
        records = list(attendance_collection.find({"timestamp": {"$gte": start, "$lt": end}}))
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Name", "Email", "Phone", "Timestamp"])
        
        for record in records:
            user = users_collection.find_one({"name": record["name"]}, {"_id": 0, "email": 1, "phone": 1})
            timestamp = record["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([record["name"], user["email"], user["phone"], timestamp])
        
        output.seek(0)
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=attendance.csv"})
    except Exception as e:
        print("Error in export_attendance:", e)
        return jsonify({"error": str(e)}), 500

# Route to render the manual attendance marking page
@attendance_bp.route("/manual_attendance", methods=["GET"])
@login_required
def manual_attendance_page():
    try:
        return render_template("manual_attendance.html")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@attendance_bp.route("/fetch_users_attendance", methods=["GET"])
@login_required
def fetch_users_attendance():
    try:
        date_str = request.args.get("date")
        date = datetime.strptime(date_str, "%Y-%m-%d")

        # Fetch all users
        users = list(users_collection.find({}, {"_id": 0, "name": 1, "email": 1, "phone": 1}))

        # Fetch attendance for the selected date
        attendance_records = list(attendance_collection.find(
            {"timestamp": {"$gte": date, "$lt": datetime(date.year, date.month, date.day, 23, 59, 59)}},
            {"_id": 0, "name": 1}
        ))

        attendance_names = {record["name"] for record in attendance_records}

        # Attach attendance status to users
        for user in users:
            user["attended"] = user["name"] in attendance_names

        return jsonify(users)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Route to save manual attendance
@attendance_bp.route("/save_manual_attendance", methods=["POST"])
@login_required
def save_manual_attendance():
    try:
        data = request.json
        date_str = data.get("date")
        date = datetime.strptime(date_str, "%Y-%m-%d")

        for user in data.get("users", []):
            name = user.get("name")
            attended = user.get("attended")

            # Check if the user already has an attendance record
            existing_record = attendance_collection.find_one(
                {"name": name, "timestamp": {"$gte": date, "$lt": datetime(date.year, date.month, date.day, 23, 59, 59)}}
            )

            if attended and not existing_record:
                # Mark attendance if not already marked
                timestamp = datetime.utcnow()
                attendance_collection.insert_one({"name": name, "timestamp": timestamp})

                # Send email notification if email exists
                user_data = users_collection.find_one({"name": name}, {"_id": 0, "email": 1})
                if user_data and "email" in user_data:
                    send_attendance_email(name, timestamp, user_data["email"])

            elif not attended and existing_record:
                # Remove attendance if it was marked previously
                attendance_collection.delete_one({"name": name, "timestamp": existing_record["timestamp"]})

        return jsonify({"message": "Attendance updated successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to fetch attendance data for graph
@attendance_bp.route("/attendance_data", methods=["GET"])
@login_required
def attendance_data():
    try:
        pipeline = [
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        data = list(attendance_collection.aggregate(pipeline))
        return jsonify(data)
    except Exception as e:
        print("Error in attendance_data:", e)
        return jsonify({"error": str(e)}), 500

# Route to render the attendance trends page
@attendance_bp.route("/attendance_trends", methods=["GET"])
@login_required
def attendance_trends_page():
    try:
        return render_template("attendance_trends.html")
    except Exception as e:
        return jsonify({"error": str(e)}), 500
