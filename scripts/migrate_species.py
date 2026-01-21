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

# Species data - Real ant species found in Thailand
# Data sourced from iNaturalist observations and scientific literature
SPECIES_DATA = [
    {
        "id": "1",
        "name": "Asian Weaver Ant",
        "scientific_name": "Oecophylla smaragdina",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Formicinae",
            "genus": "Oecophylla",
        },
        "tags": ["Native", "Edible", "Beneficial", "Tree-dwelling"],
        "about": "The Asian Weaver Ant is Thailand's most commonly observed ant species. These remarkable architects construct elaborate nests by weaving living leaves together using silk produced by their larvae. They are widely used in biological pest control and are considered a delicacy in Thai cuisine.",
        "characteristics": "Workers range from 5-10mm with orange to greenish coloration. Major workers have large mandibles and excellent vision. They have strong legs adapted for gripping leaves and walking on smooth surfaces.",
        "colors": ["Orange", "Green", "Red-brown"],
        "habitat": ["Tropical Forests", "Orchards", "Mangroves", "Gardens"],
        "distribution": ["Thailand"],
        "behavior": "Highly territorial and aggressive defenders. Workers form living chains to bridge gaps between leaves. They communicate through pheromones and tactile signals. Colonies can contain over 500,000 workers.",
        "ecological_role": "Important biological pest control agents used to protect mango, citrus, and cashew orchards. They prey on harmful insects and are keystone species in tropical ecosystems.",
        "image": "https://inaturalist-open-data.s3.amazonaws.com/photos/115048419/medium.jpg",
    },
    {
        "id": "2",
        "name": "Arboreal Bicolored Slender Ant",
        "scientific_name": "Tetraponera rufonigra",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Pseudomyrmecinae",
            "genus": "Tetraponera",
        },
        "tags": ["Native", "Arboreal", "Stinging"],
        "about": "The Arboreal Bicolored Slender Ant is a common tree-dwelling species in Thailand. Known locally for their painful sting, these slender ants nest in hollow twigs and plant stems. They are frequently encountered in gardens and forests throughout the country.",
        "characteristics": "Slender body measuring 6-10mm. Distinctive bicolored pattern with reddish-brown head and thorax contrasting with black abdomen. Long legs and antennae adapted for arboreal life.",
        "colors": ["Red-brown", "Black"],
        "habitat": ["Trees", "Shrubs", "Gardens", "Forest Edges"],
        "distribution": ["Thailand"],
        "behavior": "Aggressive when disturbed and delivers a painful sting. They nest in small colonies inside hollow plant stems and dead twigs. Primarily predatory, hunting small insects on vegetation.",
        "ecological_role": "Natural pest controllers that prey on various small insects. They contribute to plant protection by defending their nesting sites from herbivores.",
        "image": "https://static.inaturalist.org/photos/352717844/medium.jpg",
    },
    {
        "id": "3",
        "name": "Longhorn Crazy Ant",
        "scientific_name": "Paratrechina longicornis",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Formicinae",
            "genus": "Paratrechina",
        },
        "tags": ["Tramp Species", "Urban", "Fast-moving"],
        "about": "The Longhorn Crazy Ant is named for its erratic, rapid movements and exceptionally long antennae. This cosmopolitan species is one of Thailand's most common urban ants, frequently found in homes, restaurants, and buildings throughout the country.",
        "characteristics": "Small workers measuring 2.5-3mm with extremely long antennae and legs. Dark brown to black coloration with a slender body. Characterized by their rapid, erratic running pattern.",
        "colors": ["Dark Brown", "Black"],
        "habitat": ["Urban Areas", "Buildings", "Gardens", "Disturbed Habitats"],
        "distribution": ["Thailand"],
        "behavior": "Highly active foragers that move in erratic patterns. They form trails but individual workers often deviate unpredictably. Attracted to sweet foods and proteins. Colonies have multiple queens.",
        "ecological_role": "Opportunistic scavengers that help decompose organic matter. In urban environments, they can be household pests but also consume other pest insects.",
        "image": "https://inaturalist-open-data.s3.amazonaws.com/photos/466599145/medium.jpg",
    },
    {
        "id": "4",
        "name": "Toothed Ponerine Ant",
        "scientific_name": "Odontoponera denticulata",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Ponerinae",
            "genus": "Odontoponera",
        },
        "tags": ["Native", "Ground-dwelling", "Predatory"],
        "about": "The Toothed Ponerine Ant is a large, ground-dwelling species commonly found throughout Thailand. These powerful predators hunt on the forest floor and are frequently seen foraging alone or in small groups in both natural and urban environments.",
        "characteristics": "Large robust workers measuring 10-12mm. Black coloration with a distinctive tooth-like projection on the petiole. Strong mandibles and a powerful sting for subduing prey.",
        "colors": ["Black", "Dark Brown"],
        "habitat": ["Forest Floor", "Leaf Litter", "Gardens", "Urban Parks"],
        "distribution": ["Thailand"],
        "behavior": "Solitary foragers that hunt various arthropods. They nest in soil and leaf litter with relatively small colonies. Known for their powerful sting used to immobilize prey.",
        "ecological_role": "Important predators that help control populations of soil-dwelling insects and other invertebrates. They contribute to nutrient cycling through their hunting activities.",
        "image": "https://inaturalist-open-data.s3.amazonaws.com/photos/264650371/medium.jpg",
    },
    {
        "id": "5",
        "name": "Yellow Crazy Ant",
        "scientific_name": "Anoplolepis gracilipes",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Formicinae",
            "genus": "Anoplolepis",
        },
        "tags": ["Invasive", "Aggressive", "Supercolony"],
        "about": "The Yellow Crazy Ant is one of the world's most destructive invasive ant species, now established in Thailand. Named for their erratic movements when disturbed, these ants form massive supercolonies that can devastate local ecosystems.",
        "characteristics": "Workers are 4-5mm with a slender yellowish-brown body. Extremely long legs and antennae relative to body size. Movements are characteristically erratic and frantic when disturbed.",
        "colors": ["Yellow", "Light Brown"],
        "habitat": ["Disturbed Forests", "Coastal Areas", "Urban Gardens", "Plantations"],
        "distribution": ["Thailand"],
        "behavior": "Forms massive supercolonies with multiple queens. Sprays formic acid when threatened, which can blind or kill small animals. Highly aggressive towards native ant species and other invertebrates.",
        "ecological_role": "Invasive pest that disrupts ecosystems by displacing native ants and preying on invertebrates, bird chicks, and small reptiles. Requires management in conservation areas.",
        "image": "https://inaturalist-open-data.s3.amazonaws.com/photos/116456619/medium.jpg",
    },
    {
        "id": "6",
        "name": "Armed Spiny Ant",
        "scientific_name": "Polyrhachis armata",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Formicinae",
            "genus": "Polyrhachis",
        },
        "tags": ["Native", "Spiny", "Arboreal"],
        "about": "The Armed Spiny Ant is a distinctive species found throughout Thailand, recognizable by the prominent spines on its thorax. These arboreal ants build silk and plant fiber nests in vegetation and are common in forests and gardens.",
        "characteristics": "Medium-sized workers measuring 6-8mm. Black coloration with distinctive curved spines projecting from the thorax and petiole. Body covered with fine golden hairs.",
        "colors": ["Black", "Golden"],
        "habitat": ["Trees", "Shrubs", "Forest Edges", "Gardens"],
        "distribution": ["Thailand"],
        "behavior": "Build elaborate nests using silk produced by larvae, woven with plant debris. They are active foragers that tend honeydew-producing insects and hunt small prey.",
        "ecological_role": "Contribute to ecosystem health by preying on small insects and tending plant-sucking insects. Their nests provide microhabitats for other small invertebrates.",
        "image": "https://inaturalist-open-data.s3.amazonaws.com/photos/234706325/medium.jpeg",
    },
    {
        "id": "7",
        "name": "Tropical Fire Ant",
        "scientific_name": "Solenopsis geminata",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Myrmicinae",
            "genus": "Solenopsis",
        },
        "tags": ["Invasive", "Stinging", "Agricultural Pest"],
        "about": "The Tropical Fire Ant is an introduced species now widespread throughout Thailand. Known for their painful stings, these ants are common in agricultural areas, gardens, and disturbed habitats where they can become serious pests.",
        "characteristics": "Polymorphic workers ranging from 2-6mm. Reddish-brown to dark brown coloration with a prominent two-segmented waist. Major workers have disproportionately large heads.",
        "colors": ["Red-brown", "Dark Brown"],
        "habitat": ["Agricultural Fields", "Gardens", "Disturbed Areas", "Urban Zones"],
        "distribution": ["Thailand"],
        "behavior": "Aggressive when nests are disturbed, swarming and stinging repeatedly. They are attracted to oily foods and proteins. Colonies can have multiple queens and spread rapidly.",
        "ecological_role": "Considered an agricultural pest that can damage crops and sting farm workers. They compete with and displace native ant species in disturbed habitats.",
        "image": "https://inaturalist-open-data.s3.amazonaws.com/photos/29488829/medium.jpg",
    },
    {
        "id": "8",
        "name": "Cocoa Black Ant",
        "scientific_name": "Dolichoderus thoracicus",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Dolichoderinae",
            "genus": "Dolichoderus",
        },
        "tags": ["Native", "Beneficial", "Tree-dwelling"],
        "about": "The Cocoa Black Ant is widely used as a biological control agent in Southeast Asian agriculture. In Thailand, farmers encourage these ants in cocoa, coconut, and fruit plantations where they protect crops from pest insects.",
        "characteristics": "Medium-sized workers measuring 4-5mm. Uniformly black coloration with a distinctive hump-shaped thorax profile. Smooth, shiny integument with sparse hairs.",
        "colors": ["Black"],
        "habitat": ["Plantations", "Orchards", "Trees", "Agricultural Areas"],
        "distribution": ["Thailand"],
        "behavior": "Build carton nests in trees using chewed plant material. They actively patrol plants and attack pest insects. Known for tending mealybugs and scale insects for honeydew.",
        "ecological_role": "Valuable biological control agent that reduces pest damage in tropical agriculture. Their presence can significantly decrease the need for chemical pesticides.",
        "image": "https://inaturalist-open-data.s3.amazonaws.com/photos/342848506/medium.jpeg",
    },
    {
        "id": "9",
        "name": "Destroyer Ant",
        "scientific_name": "Trichomyrmex destructor",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Myrmicinae",
            "genus": "Trichomyrmex",
        },
        "tags": ["Invasive", "Urban Pest", "Household"],
        "about": "The Destroyer Ant, also known as the Singapore Ant, is a common household pest throughout Thailand. These small ants readily infest buildings and are particularly attracted to sweet and fatty foods in kitchens and food storage areas.",
        "characteristics": "Small workers measuring 2-3mm. Light brown to yellowish coloration with a darker gaster. Two-segmented waist with small spines on the propodeum.",
        "colors": ["Light Brown", "Yellow"],
        "habitat": ["Buildings", "Kitchens", "Food Storage", "Urban Areas"],
        "distribution": ["Thailand"],
        "behavior": "Form extensive foraging trails to food sources. Colonies have multiple queens and can spread through budding. They are persistent invaders of human structures.",
        "ecological_role": "Considered a pest species in urban environments. They can contaminate food supplies and are difficult to control once established in buildings.",
        "image": "https://inaturalist-open-data.s3.amazonaws.com/photos/144091854/medium.jpeg",
    },
    {
        "id": "10",
        "name": "Ghost Ant",
        "scientific_name": "Tapinoma melanocephalum",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Dolichoderinae",
            "genus": "Tapinoma",
        },
        "tags": ["Invasive", "Tiny", "Household Pest"],
        "about": "The Ghost Ant gets its name from its pale, almost translucent legs and abdomen that make it difficult to see. This tiny ant is one of Thailand's most common indoor pests, frequently infesting kitchens, bathrooms, and food preparation areas.",
        "characteristics": "Very small workers measuring only 1.3-1.5mm. Distinctive bicolored appearance with a dark head and thorax but pale, translucent legs and gaster. Almost invisible against light surfaces.",
        "colors": ["Dark Brown", "Translucent White"],
        "habitat": ["Buildings", "Kitchens", "Bathrooms", "Greenhouses"],
        "distribution": ["Thailand"],
        "behavior": "Form multiple interconnected colonies through budding. They prefer warm, humid environments and are strongly attracted to sweets. Emit a coconut-like odor when crushed.",
        "ecological_role": "Urban pest species with limited ecological benefit. They can spread bacteria in food preparation areas and are a significant nuisance in homes and restaurants.",
        "image": "https://inaturalist-open-data.s3.amazonaws.com/photos/174512993/medium.jpeg",
    },
    {
        "id": "11",
        "name": "Asian Tyrant Ant",
        "scientific_name": "Iridomyrmex anceps",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Dolichoderinae",
            "genus": "Iridomyrmex",
        },
        "tags": ["Native", "Ground-dwelling", "Common"],
        "about": "The Asian Tyrant Ant is a common ground-nesting species found throughout Thailand. These fast-moving ants are frequently seen foraging on the ground in gardens, parks, and natural areas, often in large numbers.",
        "characteristics": "Medium-sized workers measuring 3-4mm. Dark brown to black coloration with a slender build. Fast runners with a characteristic rapid, jerky movement pattern.",
        "colors": ["Dark Brown", "Black"],
        "habitat": ["Gardens", "Parks", "Grasslands", "Forest Edges"],
        "distribution": ["Thailand"],
        "behavior": "Highly active foragers that form extensive trail networks. They are territorial and will aggressively defend food sources. Colonies can be very large with multiple nests.",
        "ecological_role": "Important scavengers and predators that help control other insect populations. They contribute to soil health through their nesting activities.",
        "image": "https://static.inaturalist.org/photos/102863538/medium.jpeg",
    },
    {
        "id": "12",
        "name": "Asian Marauder Ant",
        "scientific_name": "Carebara diversa",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Myrmicinae",
            "genus": "Carebara",
        },
        "tags": ["Native", "Polymorphic", "Army Ant-like"],
        "about": "The Asian Marauder Ant is famous for its extreme size variation between castes - one of the greatest of any ant species. These ants conduct impressive group raids on other ant colonies and termite nests, resembling army ant behavior.",
        "characteristics": "Extremely polymorphic with workers ranging from tiny 1.5mm minors to massive 12mm majors. Major workers have enormous heads for their body size. Yellowish-brown to brown coloration.",
        "colors": ["Yellow-brown", "Brown"],
        "habitat": ["Tropical Forests", "Forest Edges", "Plantations"],
        "distribution": ["Thailand"],
        "behavior": "Conduct group raids on other social insect colonies. Major workers serve as living food storage vessels. They form large underground colonies with complex tunnel systems.",
        "ecological_role": "Important predators of termites and other ants. Their raids help regulate populations of social insects in tropical ecosystems.",
        "image": "https://inaturalist-open-data.s3.amazonaws.com/photos/457670012/medium.jpeg",
    },
    {
        "id": "13",
        "name": "Giant Forest Ant",
        "scientific_name": "Dinomyrmex gigas",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Formicinae",
            "genus": "Dinomyrmex",
        },
        "tags": ["Native", "Giant", "Forest-dwelling"],
        "about": "The Giant Forest Ant is one of the largest ant species in the world and a highlight of Thailand's tropical forests. These impressive ants can reach over 28mm in length and are primarily nocturnal hunters.",
        "characteristics": "Among the world's largest ants with workers measuring 20-28mm. Black coloration with a massive head and powerful mandibles. Long legs adapted for climbing trees and running on the forest floor.",
        "colors": ["Black"],
        "habitat": ["Primary Rainforests", "Lowland Forests", "Tree Hollows"],
        "distribution": ["Thailand"],
        "behavior": "Primarily nocturnal, foraging on tree trunks and the forest floor. They nest in tree hollows and dead wood. Despite their size, they are not particularly aggressive unless handled.",
        "ecological_role": "Important predators in forest ecosystems, helping control populations of various arthropods. They also contribute to decomposition by nesting in dead wood.",
        "image": "https://inaturalist-open-data.s3.amazonaws.com/photos/408088316/medium.jpg",
    },
    {
        "id": "14",
        "name": "Queenless Ponerine Ant",
        "scientific_name": "Diacamma rugosum",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Ponerinae",
            "genus": "Diacamma",
        },
        "tags": ["Native", "Queenless", "Ground-dwelling"],
        "about": "The Queenless Ponerine Ant has a unique social structure where colonies lack a true queen. Instead, a single mated worker called a gamergate reproduces while other workers are prevented from mating through social control mechanisms.",
        "characteristics": "Large workers measuring 10-12mm. Black coloration with a robust build and strong mandibles. Distinctive ridged sculpturing on the head and thorax gives them a rough appearance.",
        "colors": ["Black"],
        "habitat": ["Forest Floor", "Leaf Litter", "Gardens", "Disturbed Habitats"],
        "distribution": ["Thailand"],
        "behavior": "Solitary hunters that prey on various arthropods. They have a unique dominance hierarchy where the reproductive female mutilates the gemmae (wing buds) of other workers to prevent them from reproducing.",
        "ecological_role": "Effective predators of ground-dwelling invertebrates. Their unique social system makes them subjects of scientific research on reproductive conflict.",
        "image": "https://inaturalist-open-data.s3.amazonaws.com/photos/64299100/medium.jpg",
    },
    {
        "id": "15",
        "name": "Oriental Trap-jaw Ant",
        "scientific_name": "Odontomachus simillimus",
        "classification": {
            "family": "Formicidae",
            "subfamily": "Ponerinae",
            "genus": "Odontomachus",
        },
        "tags": ["Native", "Trap-jaw", "Predatory"],
        "about": "The Oriental Trap-jaw Ant possesses one of the fastest movements in the animal kingdom - their mandibles can snap shut at speeds exceeding 200 km/h. This remarkable mechanism is used both for capturing prey and as a defensive escape mechanism.",
        "characteristics": "Medium to large workers measuring 8-12mm. Elongated head with distinctive linear mandibles held open at 180 degrees. Reddish-brown to black coloration with long legs.",
        "colors": ["Red-brown", "Black"],
        "habitat": ["Forest Floor", "Leaf Litter", "Rotting Logs", "Gardens"],
        "distribution": ["Thailand"],
        "behavior": "Ambush predators that wait with mandibles cocked open. When trigger hairs are touched, mandibles snap shut in less than a millisecond. They can also use this snap to propel themselves away from threats.",
        "ecological_role": "Specialized predators that help control populations of small invertebrates. Their unique hunting mechanism makes them important subjects for biomechanics research.",
        "image": "https://static.inaturalist.org/photos/225143718/medium.jpeg",
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
