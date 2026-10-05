# ruff: noqa
import subprocess
import google.auth
import google.oauth2.credentials
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-01-be9dafaef3b9"

INITIAL_WORKOUTS = [
    {
        "id": "wod_fran",
        "title": "Fran",
        "category": "CrossFit Benchmark",
        "duration_minutes": 15,
        "equipment_needed": ["barbell", "pull-up bar"],
        "description": "21-15-9 reps of Thrusters (95/65 lbs) and Pull-ups for time.",
        "difficulty": "Advanced",
        "target_muscles": ["legs", "shoulders", "back", "core"],
    },
    {
        "id": "wod_cindy",
        "title": "Cindy",
        "category": "CrossFit Benchmark",
        "duration_minutes": 20,
        "equipment_needed": ["pull-up bar"],
        "description": "20-minute AMRAP (As Many Rounds As Possible): 5 Pull-ups, 10 Push-ups, 15 Air Squats.",
        "difficulty": "Intermediate",
        "target_muscles": ["back", "chest", "legs", "core"],
    },
    {
        "id": "hiit_tabata_core",
        "title": "Tabata Core Blaster",
        "category": "HIIT Interval",
        "duration_minutes": 16,
        "equipment_needed": ["mat"],
        "description": "8 rounds per exercise (20s work / 10s rest): Hollow holds, Bicycle crunches, Mountain climbers, Plank jacks.",
        "difficulty": "Beginner",
        "target_muscles": ["core", "abs"],
    },
    {
        "id": "wod_kettlebell_frenzy",
        "title": "Kettlebell Frenzy",
        "category": "HIIT Interval",
        "duration_minutes": 25,
        "equipment_needed": ["kettlebell"],
        "description": "5 rounds for time: 20 Kettlebell Swings, 15 Goblet Squats, 10 Single-arm Clean & Press per side.",
        "difficulty": "Intermediate",
        "target_muscles": ["glutes", "hamstrings", "shoulders", "legs"],
    },
]

def get_firestore_client() -> firestore.Client:
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
        creds = google.oauth2.credentials.Credentials(token)
        return firestore.Client(project=PROJECT_ID, credentials=creds)
    except Exception:
        return firestore.Client(project=PROJECT_ID)

def seed():
    print(f"Connecting to Firestore for project '{PROJECT_ID}'...")
    db = get_firestore_client()
    collection_ref = db.collection("workouts")

    for item in INITIAL_WORKOUTS:
        doc_id = item["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(item)
        print(f"  ✓ Seeded workout: {item['title']} ({doc_id})")

    print("Firestore seeding complete!")

if __name__ == "__main__":
    seed()
