from flask import Flask, render_template, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv(override=True)

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY")

# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["attendance_db"]

# Import Blueprints
from routes.auth_routes import auth_bp
from routes.user_routes import user_bp
from routes.attendance_routes import attendance_bp
from utils import login_required

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(attendance_bp)

@app.route("/")
@login_required
def home():
    try:
        return render_template("dashboard.html")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)