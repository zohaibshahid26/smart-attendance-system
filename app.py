from flask import Flask, render_template, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import timedelta
import os

# Load environment variables
load_dotenv(override=True)

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY")
app.permanent_session_lifetime = timedelta(days=1)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["attendance_db"]

# Import Blueprints
from routes.auth_routes import auth_bp
from routes.user_routes import user_bp
from routes.attendance_routes import attendance_bp
from routes.student_routes import student_bp
from utils import login_required

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(student_bp)


from flask import render_template, jsonify
from pymongo import MongoClient
from datetime import datetime
from utils import login_required
import os

# Connect to MongoDB (assuming this is already in your app.py or imported)
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["attendance_db"]
users_collection = db["users"]
attendance_collection = db["attendance"]

@app.route("/")
@login_required
def home():

    return render_template(
            "dashboard.html",
            registered_users=150,
            todays_absentees=5,
            attendance_rate=95.0
        )
if __name__ == "__main__":
    app.run(debug=True)