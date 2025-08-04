from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import firebase_admin
from firebase_admin import credentials, firestore, storage
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from werkzeug.utils import secure_filename
import tempfile

app = Flask(__name__)
CORS(app)

# Firebase Initialization
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.getenv("FIREBASE_STORAGE_BUCKET")
    })

db = firestore.client()
bucket = storage.bucket()

# Brevo Initialization
configuration = sib_api_v3_sdk.Configuration()
configuration.api_key['api-key'] = os.getenv("BREVO_API_KEY")
api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
sender_email = os.getenv("EMAIL_SENDER")

def send_email(subject, html_content, to_email, to_name):
    email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email, "name": to_name}],
        sender={"email": sender_email, "name": "LifeWood HR"},
        subject=subject,
        html_content=html_content
    )
    try:
        api_instance.send_transac_email(email)
        return True
    except ApiException as e:
        print(f"Error sending email: {e}")
        return False

@app.route("/")
def home():
    return jsonify({"message": "Backend is working!"})

# 📧 Send Registration Email
@app.route("/send-registration-email", methods=["POST"])
def registration_email():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")

    html = f"""
    <h2>Welcome to LifeWood, {name}!</h2>
    <p>Thank you for registering. We will review your application and reach out soon.</p>
    """
    if send_email("Registration Received", html, email, name):
        return jsonify({"message": "Registration email sent successfully"})
    return jsonify({"error": "Failed to send registration email"}), 500

# 📅 Send Interview Email
@app.route("/send-interview-email", methods=["POST"])
def interview_email():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    datetime = data.get("datetime")

    html = f"""
    <h2>Interview Scheduled</h2>
    <p>Hi {name},</p>
    <p>Your interview is scheduled for <strong>{datetime}</strong>.</p>
    <p>Please prepare and check your email for Zoom details.</p>
    """
    if send_email("Your Interview at LifeWood", html, email, name):
        return jsonify({"message": "Interview email sent successfully"})
    return jsonify({"error": "Failed to send interview email"}), 500

# ❌ Send Rejection Email
@app.route("/send-rejection-email", methods=["POST"])
def rejection_email():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    reason = data.get("reason", "We have decided not to proceed with your application.")

    html = f"""
    <h2>Application Update</h2>
    <p>Dear {name},</p>
    <p>{reason}</p>
    <p>We appreciate your interest in LifeWood and wish you the best in your career.</p>
    """
    if send_email("Application Update from LifeWood", html, email, name):
        return jsonify({"message": "Rejection email sent successfully"})
    return jsonify({"error": "Failed to send rejection email"}), 500

# 📤 Upload Applicant Data + File
@app.route("/submit-application", methods=["POST"])
def submit_application():
    name = request.form.get("name")
    email = request.form.get("email")
    position = request.form.get("position")
    file = request.files.get("resume")

    if not all([name, email, position, file]):
        return jsonify({"error": "Missing required fields"}), 400

    # Upload to Firebase Storage
    filename = secure_filename(file.filename)
    temp = tempfile.NamedTemporaryFile(delete=False)
    file.save(temp.name)

    blob = bucket.blob(f"resumes/{filename}")
    blob.upload_from_filename(temp.name)
    blob.make_public()
    file_url = blob.public_url

    # Save to Firestore
    db.collection("applicants").add({
        "name": name,
        "email": email,
        "position": position,
        "resume_url": file_url
    })

    return jsonify({"message": "Application submitted successfully", "resume_url": file_url})
