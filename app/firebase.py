"""Firebase initialization for storage operations"""
import os
import pyrebase
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, storage
from .config import FIREBASE_CONFIG

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

    firebase_admin.initialize_app(cred, {
        'storageBucket': os.getenv("FIREBASE_STORAGE_BUCKET", "")
    })

firebase = pyrebase.initialize_app(FIREBASE_CONFIG)

# Firebase Storage bucket
bucket = storage.bucket()
