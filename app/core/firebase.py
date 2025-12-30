import os
import firebase_admin
from firebase_admin import credentials, auth
from google.cloud import firestore

cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS"))
firebase_admin.initialize_app(cred)

db = firestore.Client()

def verify_token(id_token: str):
    return auth.verify_id_token(id_token)
