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
    cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS"))
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.getenv("FIREBASE_STORAGE_BUCKET", "")
    })

firebase = pyrebase.initialize_app(firebaseConfig)

# Firebase Storage bucket
bucket = storage.bucket()
