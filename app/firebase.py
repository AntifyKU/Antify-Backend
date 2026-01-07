import os
import pyrebase
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from .config import firebaseConfig

load_dotenv()

if not firebase_admin._apps: # Check if Firebase app is already initialized
    cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS"))
    firebase_admin.initialize_app(cred)

firebase = pyrebase.initialize_app(firebaseConfig)
