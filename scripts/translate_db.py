"""Translate the database to Thai"""
import time
from datetime import datetime
import os
from typing import Dict, Any

import firebase_admin
from firebase_admin import credentials, firestore
from deep_translator import GoogleTranslator
from requests.exceptions import RequestException

current_dir = os.path.dirname(os.path.abspath(__file__))
cred_path = os.path.join(current_dir, "..", "firebase-service-account.json")

cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

translator = GoogleTranslator(source="auto", target="th")


def translate_field(text: str) -> str:
    """Translate a text field to Thai"""
    if not text:
        return ""

    try:
        return translator.translate(text)
    except RequestException as e:
        print(f"Translate error: {e}")
        time.sleep(1)
    except ValueError as e:
        print(f"Invalid input: {e}")

    return text


def should_translate(data: Dict[str, Any], eng: str, th: str) -> bool:
    """Check if the field should be translated"""
    return data.get(eng) and not data.get(th)


def process_basic_fields(data: Dict, updates: Dict) -> bool:
    """Translate the basic fields to Thai"""
    fields = {
        "about": "about_th",
        "characteristics": "characteristics_th",
        "behavior": "behavior_th",
        "ecological_role": "ecological_role_th",
    }

    updated = False

    for eng, th in fields.items():
        if should_translate(data, eng, th):
            translated = translate_field(data[eng])
            if translated != data[eng]:
                updates[th] = translated
                updated = True

    return updated


def process_risk_fields(data: Dict, updates: Dict) -> bool:
    """Translate the risk fields to Thai"""
    risk = data.get("risk", {})
    updated = False

    # venom
    venom = risk.get("venom", {})
    if venom.get("details") and not venom.get("details_th"):
        translated = translate_field(venom["details"])
        if translated != venom["details"]:
            updates.setdefault("risk", risk)
            updates["risk"]["venom"]["details_th"] = translated
            updated = True

    # allergy
    allergy = risk.get("allergy_risk_note")
    if allergy and not risk.get("allergy_risk_note_th"):
        translated = translate_field(allergy)
        if translated != allergy:
            updates.setdefault("risk", risk)
            updates["risk"]["allergy_risk_note_th"] = translated
            updated = True

    return updated


def update_document(species_ref, doc_id: str, updates: Dict) -> bool:
    """Update the document in the database"""
    try:
        species_ref.document(doc_id).update(updates)
        return True
    except RequestException as e:
        print(f"Update error (network): {e}")
    except ValueError as e:
        print(f"Update error (data): {e}")

    return False


def translate_species():
    """Translate the species collection to Thai"""
    species_ref = db.collection("species")
    docs = list(species_ref.stream())

    updated_count = 0

    print(f"Start: {datetime.now()}")

    for idx, doc in enumerate(docs, start=1):
        data = doc.to_dict()
        doc_id = doc.id

        print(f"[{idx}] {data.get('scientific_name', doc_id)}")

        updates = {}

        basic_updated = process_basic_fields(data, updates)
        risk_updated = process_risk_fields(data, updates)

        if basic_updated or risk_updated:
            success = update_document(species_ref, doc_id, updates)
            if success:
                updated_count += 1
                print(f"  -> Updated {doc_id}")

            time.sleep(0.5)

    print(f"\nDone: {updated_count}/{len(docs)} updated")


if __name__ == "__main__":
    translate_species()