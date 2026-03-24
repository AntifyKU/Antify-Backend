"""Firebase initialization for storage operations"""
import os
import pyrebase
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, storage
from .config import firebaseConfig

load_dotenv()

try:
    firebase_admin.get_app()
except ValueError:
    cred_path = os.getenv("FIREBASE_CREDENTIALS")
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
    else:
        # Fallback to Application Default Credentials for Cloud Run
        cred = credentials.ApplicationDefault()
        
    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()
    firebase_admin.initialize_app(cred, {
        'storageBucket': bucket_name
    })

firebase = pyrebase.initialize_app(firebaseConfig)

# Firebase Storage bucket (handle empty name gracefully)
bucket = storage.bucket(bucket_name) if bucket_name else None

# Centralized Firestore client
from firebase_admin import firestore
db = firestore.client()
