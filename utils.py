from flask import session, redirect, url_for
from functools import wraps
import face_recognition

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

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
