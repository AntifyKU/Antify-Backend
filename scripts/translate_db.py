import os
import firebase_admin
from firebase_admin import credentials, firestore
from deep_translator import GoogleTranslator
import time
from datetime import datetime

# Initialize Firebase 
# Use absolute path based on the file location
current_dir = os.path.dirname(os.path.abspath(__file__))
cred_path = os.path.join(current_dir, "..", "firebase-service-account.json")
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

translator = GoogleTranslator(source='auto', target='th')

def translate_field(text: str) -> str:
    if not text:
        return ""
    try:
        translated = translator.translate(text)
        return translated
    except Exception as e:
        print(f"Error translating '{text[:30]}...': {e}")
        time.sleep(1) # wait if rate limited
        return text # return original if translation fails

def translate_species():
    species_ref = db.collection("species")
    # Fetch all documents into a list first to avoid DeadlineExceeded timeout
    docs = list(species_ref.stream())

    updated_count = 0
    total_docs = 0

    print(f"Starting database translation at {datetime.now()}")

    for doc in docs:
        total_docs += 1
        data = doc.to_dict()
        doc_id = doc.id
        
        # Check if already translated to avoid duplicate work
        # We check both to see if we need updates
        needs_update = False
        updates = {}

        fields_to_translate = {
            "about": "about_th",
            "characteristics": "characteristics_th",
            "behavior": "behavior_th",
            "ecological_role": "ecological_role_th"
        }

        print(f"[{total_docs}] Processing species: {data.get('scientific_name', doc_id)}")

        for eng_field, th_field in fields_to_translate.items():
            original_text = data.get(eng_field, "")
            
            # Translate if original exists and translated doesn't exist or is empty
            if original_text and not data.get(th_field):
                translated_text = translate_field(original_text)
                if translated_text and translated_text != original_text:
                    updates[th_field] = translated_text
                    needs_update = True
        
        # Handle complex nested fields like venom details and allergy risk
        risk_data = data.get("risk", {})
        
        # Venom details
        venom_data = risk_data.get("venom", {})
        venom_details = venom_data.get("details", "")
        if venom_details and not venom_data.get("details_th"):
            translated_details = translate_field(venom_details)
            if translated_details and translated_details != venom_details:
                if "risk" not in updates:
                    updates["risk"] = risk_data
                updates["risk"]["venom"]["details_th"] = translated_details
                needs_update = True
        
        # Allergy risk
        allergy_note = risk_data.get("allergy_risk_note", "")
        if allergy_note and not risk_data.get("allergy_risk_note_th"):
            translated_allergy = translate_field(allergy_note)
            if translated_allergy and translated_allergy != allergy_note:
                if "risk" not in updates:
                    updates["risk"] = risk_data
                updates["risk"]["allergy_risk_note_th"] = translated_allergy
                needs_update = True
        
        if needs_update:
            try:
                # Update document
                species_ref.document(doc_id).update(updates)
                updated_count += 1
                print(f"  -> Added {list(updates.keys())} translated fields for {doc_id}")
            except Exception as e:
                print(f"  -> Failed to update {doc_id}: {e}")
            
            time.sleep(0.5) 
            
    print(f"\nFinished translating {updated_count} out of {total_docs} species.")

if __name__ == "__main__":
    translate_species()
