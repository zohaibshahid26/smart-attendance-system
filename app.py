from flask import Flask, request, jsonify, render_template, Response
from pymongo import MongoClient
import numpy as np
import cv2
import face_recognition
import base64
from datetime import datetime
import os
import threading
from scipy.spatial.distance import euclidean
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder="templates")

# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["attendance_db"]
users_collection = db["users"]
attendance_collection = db["attendance"]

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

# Route to render frontend dashboard
@app.route("/")
def home():
    try:
        return render_template("dashboard.html")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to register a user
@app.route("/register", methods=["POST"])
def register_user():
    try:
        data = request.json
        name = data["name"]
        image_data = base64.b64decode(data["image"])
        
        # Convert to numpy array
        np_arr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        # Get face encoding
        face_embedding = get_face_embedding(image)
        if face_embedding is None:
            return jsonify({"error": "No face detected"}), 400
        
        # Save user to MongoDB
        user_data = {"name": name, "face_embedding": np.array(face_embedding, dtype=np.float16).tolist()}
        users_collection.insert_one(user_data)
        return jsonify({"message": "User registered successfully"})
    except Exception as e:
        print("Error in register_user:", e)
        return jsonify({"error": str(e)}), 500

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
            else:
                self.frame = None

    def get_frame(self):
        return self.frame

    def stop(self):
        if self.running:
            self.running = False
            self.thread.join()
            self.cap.release()
            self.cap = None

video_stream = VideoStream()

@app.route("/video_feed")
def video_feed():
    video_stream.start()  # Start the camera when the route is accessed
    try:
        def generate_frames():
            while video_stream.running:
                frame = video_stream.get_frame()
                if frame is None:
                    continue
                
                face_locations = face_recognition.face_locations(frame)
                for (top, right, bottom, left) in face_locations:
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                
                _, buffer = cv2.imencode(".jpg", frame)
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")
    except Exception as e:
        print("Error in video_feed:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/mark_attendance", methods=["GET"])
def mark_attendance_page():
    video_stream.start()  # Ensure camera starts before rendering the page
    return render_template("live_feed.html")

@app.route("/stop_camera", methods=["POST"])
def stop_camera():
    video_stream.stop()
    return jsonify({"message": "Camera stopped"})

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    try:
        frame = video_stream.get_frame()
        if frame is None:
            return jsonify({"error": "No frame captured"}), 400
        
        # Get face embedding
        input_embedding = get_face_embedding(frame)
        if input_embedding is None:
            return jsonify({"error": "No face detected"}), 400
        
        # Compare embeddings with registered users using Euclidean Distance
        users = list(users_collection.find({}, {"_id": 0, "name": 1, "face_embedding": 1}))
        
        best_match = None
        min_distance = float("inf")
        
        for user in users:
            stored_embedding = np.array(user["face_embedding"], dtype=np.float16)
            distance = euclidean(stored_embedding, input_embedding)
            if distance < 0.5:  # Adjust threshold as needed
                if distance < min_distance:
                    min_distance = distance
                    best_match = user["name"]
        
        if best_match:
            attendance_collection.insert_one({"name": best_match, "timestamp": datetime.utcnow()})
            return jsonify({"message": "Attendance marked", "name": best_match})
        
        return jsonify({"error": "Face not recognized"}), 400
    except Exception as e:
        print("Error in mark_attendance:", e)
        return jsonify({"error": str(e)}), 500
    
if __name__ == "__main__":
    app.run(debug=True)