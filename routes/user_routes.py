from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from pymongo import MongoClient
import numpy as np
import base64
import cv2
import os
from datetime import datetime
from utils import get_face_embedding, login_required
from bcrypt import hashpw, gensalt  # Add this import for password hashing

user_bp = Blueprint('user', __name__, template_folder="templates")

# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["attendance_db"]
users_collection = db["users"]

# Route to render register user page
@user_bp.route("/register_user")
@login_required
def register_user_page():
    try:
        return render_template("register_user.html")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to register a user
@user_bp.route("/register", methods=["POST"])
@login_required
def register_user():
    try:
        data = request.json
        name = data["name"]
        email = data["email"]
        phone = data["phone"]
        password = data["password"]  # Get password from request
        image_data = base64.b64decode(data["image"])
        
        existing_user = users_collection.find_one({"$or": [{"email": email}, {"phone": phone}]})
        if existing_user:
            return jsonify({"error": "User with this email or phone number already exists"}), 400
        
        # Convert image to numpy array
        np_arr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        # Get face embedding
        face_embedding = get_face_embedding(image)
        if face_embedding is None:
            return jsonify({"error": "No face detected"}), 400
        
        # Hash the password
        hashed_password = hashpw(password.encode('utf-8'), gensalt()).decode('utf-8')
        
        # Save user to MongoDB
        user_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "password": hashed_password,  # Store hashed password
            "face_embedding": np.array(face_embedding, dtype=np.float16).tolist(),
            "role": "student",  # Adding role for authorization purposes
            "created_at": datetime.now()
        }
        users_collection.insert_one(user_data)
        return jsonify({"message": "User registered successfully"})
    except Exception as e:
        print("Error in register_user:", e)
        return jsonify({"error": str(e)}), 500