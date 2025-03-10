from pymongo import MongoClient
from datetime import datetime, timedelta
import numpy as np
import random
import base64
import os
from bcrypt import hashpw, gensalt

# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["attendance_db"]
users_collection = db["users"]
attendance_collection = db["attendance"]

# Helper function to generate random face embeddings
def generate_random_embedding():
    return np.random.rand(128).tolist()

# Helper function to generate random base64 image data
def generate_random_image_data():
    return base64.b64encode(np.random.bytes(1024)).decode('utf-8')

# List of real names
real_names = [
    "Alice Johnson", "Bob Smith", "Charlie Brown", "David Wilson", "Eva Davis",
    "Frank Miller", "Grace Lee", "Hannah White", "Ian Harris", "Jack Martin",
    "Karen Thompson", "Leo Garcia", "Mia Martinez", "Nina Robinson", "Oscar Clark",
    "Paul Lewis", "Quinn Walker", "Rachel Hall", "Sam Young", "Tina Allen",
    "Uma King", "Victor Wright", "Wendy Scott", "Xander Green", "Yara Adams",
    "Zane Baker", "Amy Carter", "Brian Collins", "Chloe Edwards", "Dylan Evans",
    "Ella Foster", "Finn Gray", "Gina Howard", "Henry Hughes", "Isla Jenkins",
    "Jake Kelly", "Kara Long", "Liam Morgan", "Maya Murphy", "Noah Patterson",
    "Olivia Perry", "Piper Reed", "Quincy Ross", "Riley Sanders", "Sophie Stewart",
    "Tyler Turner", "Ursula Ward", "Violet Watson", "Wyatt Wood", "Xena Wright",
    "Yvonne Young", "Zachary Brooks", "Ava Cook", "Ben Cooper", "Cora Cox",
    "Dean Diaz", "Elena Fisher", "Felix Gonzales", "Gabby Graham", "Hugo Griffin",
    "Ivy Hayes", "Jasper Hill", "Kylie James", "Logan Jenkins", "Mila Jordan",
    "Nate Kim", "Owen Lee", "Paige Lopez", "Quinn Mitchell", "Ryder Moore",
    "Sara Morris", "Theo Nelson", "Uma Parker", "Vince Phillips", "Will Price",
    "Xander Ramirez", "Yasmin Richardson", "Zoe Rogers", "Aaron Russell", "Bella Simmons",
    "Caleb Spencer", "Daisy Sullivan", "Ethan Taylor", "Fiona Torres", "Gavin Turner",
    "Hazel Walker", "Isaac Ward", "Jade Watson", "Kai White", "Lila Williams",
    "Mason Wilson", "Nora Wright", "Omar Young", "Peyton Adams", "Quinn Allen",
    "Riley Anderson", "Samantha Bailey", "Thomas Bell", "Ulysses Bennett", "Vera Brooks",
    "Wesley Bryant", "Xavier Butler", "Yara Campbell", "Zane Carter", "Aiden Clark",
    "Brooke Collins", "Cameron Cooper", "Delilah Cox", "Eli Diaz", "Faith Edwards",
    "George Evans", "Harper Fisher", "Ian Foster", "Jasmine Garcia", "Kaden Gonzales",
    "Luna Graham", "Miles Griffin", "Nina Hayes", "Owen Hill", "Piper Howard",
    "Quinn Hughes", "Ruby Jenkins", "Sawyer Kelly", "Tessa King", "Uriah Lee",
    "Violet Long", "Wade Martin", "Xander Martinez", "Yasmin Miller", "Zoe Murphy"
]

# Helper function to generate random user data
def generate_random_user(index):
    name = real_names[index % len(real_names)]
    email = f"user{index}@example.com"
    phone = f"12345678{index:02d}"
    password = hashpw(f"password{index}".encode('utf-8'), gensalt()).decode('utf-8')
    face_embedding = generate_random_embedding()
    return {
        "name": name,
        "email": email,
        "phone": phone,
        "password": password,
        "face_embedding": face_embedding,
        "role": "student",
        "created_at": datetime.now()
    }

# Helper function to generate random attendance data
def generate_random_attendance(user_id, name, start_date, end_date):
    attendance_data = []
    class_names = [
        "Cloud Computing", "Database Management", "Object Oriented Programming",
        "Data Structures & Algorithms", "Machine Learning", "Web Development",
        "Mobile App Development", "Computer Networks", "Artificial Intelligence", "Cybersecurity"
    ]
    current_date = start_date
    while current_date <= end_date:
        status = random.choice(["Present", "Absent"])
        class_name = random.choice(class_names)
        attendance_data.append({
            "student_id": user_id,
            "name": name,
            "timestamp": current_date,
            "status": status,
            "class_name": class_name
        })
        current_date += timedelta(days=1)
    return attendance_data

# Populate users collection
users = [generate_random_user(i) for i in range(1, 151)]
users_collection.insert_many(users)

# Populate attendance collection
start_date_feb = datetime(2025, 2, 1)
end_date_feb = datetime(2025, 2, 28)
start_date_mar = datetime(2025, 3, 1)
end_date_mar = datetime(2025, 3, 11)

for user in users:
    user_id = user["_id"]
    name = user["name"]
    attendance_feb = generate_random_attendance(user_id, name, start_date_feb, end_date_feb)
    attendance_mar = generate_random_attendance(user_id, name, start_date_mar, end_date_mar)
    attendance_collection.insert_many(attendance_feb + attendance_mar)

print("Data population complete.")
