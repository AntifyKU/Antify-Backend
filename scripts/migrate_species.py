#!/usr/bin/env python3
"""
Species Data Migration Script

Migrates ant species data from the frontend AntData.ts format
to Firestore database.

Usage:
    python scripts/migrate_species.py

Requires:
    - Firebase credentials configured in .env
    - FIREBASE_CREDENTIALS environment variable set
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase if not already done
if not firebase_admin._apps:
    cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS"))
    firebase_admin.initialize_app(cred)

db = firestore.client()
SPECIES_COLLECTION = "species"

# Species data from AntifyFrontend/constants/AntData.ts
SPECIES_DATA = [
    {
        "id": "1",
        "name": "Yellow Crazy Ant",
        "scientific_name": "Anoplolepis gracilipes",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Formicinae",
            "genus": "Anoplolepis",
        },
        "tags": ["Invasive", "Aggressive", "Tropical"],
        "about": "The Yellow Crazy Ant is one of the world's most invasive ant species. Named for their erratic, rapid movements when disturbed, these ants form supercolonies that can devastate local ecosystems by preying on native insects and small animals.",
        "characteristics": "Workers are 4-5mm long with a slender yellowish-brown body. They have extremely long legs and antennae relative to body size. Their movements are characteristically erratic and 'crazy' when disturbed.",
        "colors": ["Yellow", "Brown"],
        "habitat": ["Tropical Forests", "Coastal Areas", "Urban Gardens"],
        "distribution": ["Central", "South", "East"],
        "behavior": "Forms massive supercolonies with multiple queens. They spray formic acid when threatened and can blind or kill small animals. Highly aggressive towards native ant species.",
        "ecological_role": "Considered a major pest species. They disrupt ecosystems by displacing native ants and preying on invertebrates, bird chicks, and small reptiles.",
        "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Anoplolepis_gracilipes_casent0103300_head_1.jpg/800px-Anoplolepis_gracilipes_casent0103300_head_1.jpg",
    },
    {
        "id": "2",
        "name": "Weaver Ant",
        "scientific_name": "Oecophylla smaragdina",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Formicinae",
            "genus": "Oecophylla",
        },
        "tags": ["Tree-dwelling", "Beneficial", "Edible"],
        "about": "Weaver ants are remarkable architects that construct elaborate nests by weaving leaves together using silk produced by their larvae. They are highly territorial and used in biological pest control for fruit orchards across Southeast Asia.",
        "characteristics": "Workers range from 5-10mm. Major workers have large mandibles and are orange-brown. They have strong legs for gripping leaves and excellent vision for hunting prey.",
        "colors": ["Orange", "Red-brown"],
        "habitat": ["Tropical Trees", "Orchards", "Mangroves"],
        "distribution": ["Central", "East", "South"],
        "behavior": "Highly social with complex division of labor. Workers form living chains to bridge gaps between leaves. They are aggressive defenders and will bite intruders while spraying formic acid.",
        "ecological_role": "Important biological pest control agents. Used in Thailand and Southeast Asia to protect mango, citrus, and cashew orchards from harmful insects.",
        "image": "https://upload.wikimedia.org/wikipedia/commons/5/55/Red_Weaver_Ant%2C_Oecophylla_smaragdina.jpg",
    },
    {
        "id": "3",
        "name": "Red Imported Fire Ant",
        "scientific_name": "Solenopsis invicta",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Myrmicinae",
            "genus": "Solenopsis",
        },
        "tags": ["Venomous", "Invasive", "Dangerous"],
        "about": "Red Imported Fire Ants are highly aggressive invasive ants known for their painful, burning stings. Originally from South America, they have spread worldwide and cause significant agricultural damage and public health concerns.",
        "characteristics": "Workers vary from 2-6mm with a reddish-brown head and thorax. The darker abdomen has a prominent stinger. They are polymorphic with different worker sizes.",
        "colors": ["Red", "Black"],
        "habitat": ["Grasslands", "Urban Areas", "Agricultural Fields"],
        "distribution": ["Central", "South"],
        "behavior": "Extremely aggressive when their mound is disturbed. Workers swarm and sting repeatedly, injecting venom that causes burning pain. Can be fatal to people with allergies.",
        "ecological_role": "Considered a major agricultural and ecological pest. They damage crops, kill small wildlife, and outcompete native ant species.",
        "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/Fire_ants02.jpg/1200px-Fire_ants02.jpg",
    },
    {
        "id": "4",
        "name": "Carpenter Ant",
        "scientific_name": "Camponotus pennsylvanicus",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Formicinae",
            "genus": "Camponotus",
        },
        "tags": ["Wood-dwelling", "Large", "Nocturnal"],
        "about": "Carpenter ants are among the largest ants found in Thailand. Unlike termites, they don't eat wood but excavate it to create their nests. They prefer damaged or moist wood and can cause structural damage to buildings.",
        "characteristics": "Large ants measuring 6-13mm. They have a smooth, rounded thorax and powerful mandibles. Color ranges from black to reddish-brown depending on species.",
        "colors": ["Black", "Dark Brown"],
        "habitat": ["Dead Wood", "Tree Hollows", "Buildings"],
        "distribution": ["North", "Central", "East"],
        "behavior": "Primarily nocturnal, they forage for food at night. They create satellite colonies and can travel long distances from the main nest. They don't sting but can bite powerfully.",
        "ecological_role": "Important decomposers that help break down dead wood in forest ecosystems. They contribute to nutrient cycling and create habitat for other organisms.",
        "image": "https://upload.wikimedia.org/wikipedia/commons/f/fb/Carpenter_ant_Tanzania_crop.jpg",
    },
    {
        "id": "5",
        "name": "Black Garden Ant",
        "scientific_name": "Lasius niger",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Formicinae",
            "genus": "Lasius",
        },
        "tags": ["Common", "Household", "Harmless"],
        "about": "The Black Garden Ant is one of the most common ant species found in Thai gardens and homes. They are attracted to sweet foods and often form trails into kitchens. Despite being a nuisance, they are harmless to humans.",
        "characteristics": "Small ants measuring 3-5mm. Workers are uniformly dark brown to black. Queens are much larger at 8-9mm and have wings during mating flights.",
        "colors": ["Black", "Dark Brown"],
        "habitat": ["Gardens", "Lawns", "Under Stones"],
        "distribution": ["North", "Central", "South", "East", "West"],
        "behavior": "Form well-organized colonies with a single queen. They farm aphids for honeydew and are active foragers during warm weather. Flying ants emerge in summer for mating.",
        "ecological_role": "Important soil aerators and seed dispersers. They control pest populations by preying on small insects and contribute to soil health.",
        "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3b/Lasius_niger_01.jpg/1200px-Lasius_niger_01.jpg",
    },
    {
        "id": "6",
        "name": "Pharaoh Ant",
        "scientific_name": "Monomorium pharaonis",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Myrmicinae",
            "genus": "Monomorium",
        },
        "tags": ["Tiny", "Indoor Pest", "Medical Concern"],
        "about": "Pharaoh ants are tiny tropical ants that have become a major pest in heated buildings worldwide. They are particularly problematic in hospitals where they can spread pathogens and contaminate sterile equipment.",
        "characteristics": "Very small at only 1.5-2mm. They have a yellowish to light brown body with a darker abdomen. Almost invisible to the naked eye when moving.",
        "colors": ["Yellow", "Light Brown"],
        "habitat": ["Buildings", "Hospitals", "Food Storage"],
        "distribution": ["Central", "South"],
        "behavior": "Form multiple colonies through budding rather than swarming. They prefer warm, humid environments and are attracted to proteins and sweets. Colonies can split when disturbed.",
        "ecological_role": "Considered a pest species with no beneficial role. They can contaminate food supplies and medical equipment, spreading bacteria between locations.",
        "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Monomorium_pharaonis_casent0173986_head_1.jpg/800px-Monomorium_pharaonis_casent0173986_head_1.jpg",
    },
    {
        "id": "7",
        "name": "Bullet Ant",
        "scientific_name": "Paraponera clavata",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Paraponerinae",
            "genus": "Paraponera",
        },
        "tags": ["Extremely Painful", "Large", "Rainforest"],
        "about": "The Bullet Ant has the most painful sting of any insect, described as feeling like being shot. Indigenous tribes in South America use them in warrior initiation rituals. The pain can last up to 24 hours.",
        "characteristics": "One of the largest ants at 18-25mm. They are entirely black with a robust body and large mandibles. The large stinger can inject powerful venom.",
        "colors": ["Black"],
        "habitat": ["Tropical Rainforests", "Tree Bases"],
        "distribution": ["South"],
        "behavior": "Primarily arboreal, living in tree bases. They are solitary foragers and not aggressive unless the nest is threatened. The warning behavior includes stridulation sounds.",
        "ecological_role": "Predators of various arthropods. They help control insect populations in rainforest ecosystems and serve as prey for larger animals.",
        "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/Paraponera_clavata.jpg/1200px-Paraponera_clavata.jpg",
    },
    {
        "id": "8",
        "name": "Leafcutter Ant",
        "scientific_name": "Atta cephalotes",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Myrmicinae",
            "genus": "Atta",
        },
        "tags": ["Farmer Ant", "Social", "Tropical"],
        "about": "Leafcutter ants are remarkable farmers that cut and carry leaf fragments to underground fungus gardens. They cultivate a specific fungus species that they've domesticated over millions of years of evolution.",
        "characteristics": "Highly polymorphic with workers ranging from 2-14mm. Soldiers have massive heads with powerful cutting mandibles. Reddish-brown coloration with spines on the thorax.",
        "colors": ["Red-brown", "Orange"],
        "habitat": ["Tropical Forests", "Plantations"],
        "distribution": ["South"],
        "behavior": "Form massive colonies with millions of workers and complex caste systems. They create well-defined foraging trails and can defoliate entire trees. The fungus they cultivate is their sole food source.",
        "ecological_role": "Major ecosystem engineers that affect plant community composition. Their underground nests improve soil aeration and nutrient cycling over large areas.",
        "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1e/Leaf_cutter_ants.jpg/1200px-Leaf_cutter_ants.jpg",
    },
]


def migrate_species():
    """Migrate all species data to Firestore"""
    print(f"Starting migration of {len(SPECIES_DATA)} species...")
    
    batch = db.batch()
    now = datetime.utcnow()
    
    for species in SPECIES_DATA:
        species_id = species["id"]
        doc_ref = db.collection(SPECIES_COLLECTION).document(species_id)
        
        # Add timestamps
        species_data = species.copy()
        species_data["created_at"] = now
        species_data["updated_at"] = None
        
        # Remove id from data (it's the document ID)
        del species_data["id"]
        
        batch.set(doc_ref, species_data)
        print(f"  Added: {species['name']} ({species['scientific_name']})")
    
    # Commit the batch
    batch.commit()
    print(f"\nMigration complete! {len(SPECIES_DATA)} species added to Firestore.")


def check_existing():
    """Check if species data already exists"""
    docs = db.collection(SPECIES_COLLECTION).limit(1).stream()
    return len(list(docs)) > 0


def clear_species():
    """Clear all species data (use with caution)"""
    print("Clearing existing species data...")
    docs = db.collection(SPECIES_COLLECTION).stream()
    batch = db.batch()
    count = 0
    for doc in docs:
        batch.delete(doc.reference)
        count += 1
    batch.commit()
    print(f"Deleted {count} species documents.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate species data to Firestore")
    parser.add_argument("--force", action="store_true", help="Force migration even if data exists")
    parser.add_argument("--clear", action="store_true", help="Clear existing data before migration")
    args = parser.parse_args()
    
    if args.clear:
        clear_species()
    
    if check_existing() and not args.force:
        print("Species data already exists in Firestore.")
        print("Use --force to overwrite or --clear to remove existing data first.")
        sys.exit(1)
    
    migrate_species()
