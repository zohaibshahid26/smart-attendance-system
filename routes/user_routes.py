from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from pymongo import MongoClient
import numpy as np
import base64
import cv2
import os
from utils import get_face_embedding, login_required

user_bp = Blueprint('user', __name__,template_folder="templates")

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
        image_data = base64.b64decode(data["image"])
        
        # Convert to numpy array
        np_arr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        # Get face encoding
        face_embedding = get_face_embedding(image)
        if face_embedding is None:
            return jsonify({"error": "No face detected"}), 400
        
        # Save user to MongoDB
        user_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "face_embedding": np.array(face_embedding, dtype=np.float16).tolist()
        }
        users_collection.insert_one(user_data)
        return jsonify({"message": "User registered successfully"})
    except Exception as e:
        print("Error in register_user:", e)
        return jsonify({"error": str(e)}), 500
