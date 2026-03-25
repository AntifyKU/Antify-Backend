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
    print(f"DEBUG: Current Working Directory: {os.getcwd()}")
    print(f"DEBUG: Files in current directory: {os.listdir('.')}")
    
    cred_path = os.getenv("FIREBASE_CREDENTIALS")
    print(f"DEBUG: FIREBASE_CREDENTIALS env var: {cred_path}")
    
    if cred_path and os.path.exists(cred_path):
        print(f"DEBUG: Found credentials file at {cred_path}")
        cred = credentials.Certificate(cred_path)
    else:
        if cred_path:
            print(f"DEBUG: Credentials file NOT FOUND at {cred_path}")
        # Fallback to Application Default Credentials for Cloud Run
        cred = credentials.ApplicationDefault()
        
    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()
    project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    
    config = {'storageBucket': bucket_name}
    if project_id:
        config['projectId'] = project_id
        
    print(f"DEBUG: Initializing Firebase Admin with Project ID: {project_id or 'default'}")
    print(f"DEBUG: Storage Bucket: {bucket_name}")
    print(f"DEBUG: Using Credentials: {'Service Account Key' if cred_path and os.path.exists(cred_path) else 'Application Default'}")
    
    app = firebase_admin.initialize_app(cred, config)
    print(f"DEBUG: Firebase app initialized: {app.name} (Project: {app.project_id})")

firebase = pyrebase.initialize_app(firebaseConfig)

# Firebase Storage bucket (handle empty name gracefully)
bucket = storage.bucket(bucket_name) if bucket_name else None

# Centralized Firestore client
from firebase_admin import firestore
db = firestore.client()
