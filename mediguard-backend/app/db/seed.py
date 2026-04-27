import sys
import os
from datetime import date

# Add the project root to the python path so we can import 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.core.database import SessionLocal
from app.models.user import User
from app.models.patient import Patient
from app.core.security import get_password_hash

def seed_db():
    db = SessionLocal()
    try:
        # 1. Seed Users (Updated with first_name, last_name, and status)
        users = [
            {
                "first_name": "System",
                "last_name": "Administrator",
                "username": "admin",
                "email": "admin@mediguard.com",
                "password": "password123",
                "role": "admin",
                "status": "active"
            },
            {
                "first_name": "Muktar",
                "last_name": "Hassan",
                "username": "muktar",
                "email": "clinician@mediguard.com",
                "password": "password123",
                "role": "clinician",
                "status": "active"
            },
            {
                "first_name": "Amina",
                "last_name": "Khamis",
                "username": "labtech",
                "email": "lab@mediguard.com",
                "password": "password123",
                "role": "lab_tech",
                "status": "active"
            }
        ]

        print("Seeding users...")
        for u_data in users:
            existing_user = db.query(User).filter(User.email == u_data["email"]).first()
            if not existing_user:
                new_user = User(
                    first_name=u_data["first_name"],
                    last_name=u_data["last_name"],
                    username=u_data["username"],
                    email=u_data["email"],
                    password_hash=get_password_hash(u_data["password"]),
                    role=u_data["role"],
                    status=u_data["status"]
                )
                db.add(new_user)
                print(f"Created user: {u_data['username']}")
            else:
                # Optional: Update existing users with new fields if they are missing
                if not existing_user.first_name:
                    existing_user.first_name = u_data["first_name"]
                    existing_user.last_name = u_data["last_name"]
                    existing_user.status = u_data["status"]
                    print(f"Updated existing user {u_data['username']} with new name/status fields.")
                else:
                    print(f"User {u_data['username']} already exists, skipping.")

        # 2. Seed Patients (Kenyan/Mombasa context)
        patients = [
            {
                "first_name": "Amani",
                "last_name": "Juma",
                "date_of_birth": date(1985, 5, 12),
                "gender": "male",
                "national_id": "24567890",
                "phone_number": "0712345678",
                "blood_type": "O+",
                "known_allergies": ["Penicillin", "Dust"],
                "chronic_conditions": ["Asthma"]
            },
            {
                "first_name": "Fatuma",
                "last_name": "Said",
                "date_of_birth": date(1992, 11, 20),
                "gender": "female",
                "national_id": "30123456",
                "phone_number": "0722334455",
                "blood_type": "A-",
                "known_allergies": ["Sulfa Drugs"],
                "chronic_conditions": ["Hypertension"]
            },
            {
                "first_name": "Bakari",
                "last_name": "Musa",
                "date_of_birth": date(1978, 3, 15),
                "gender": "male",
                "national_id": "12345678",
                "phone_number": "0733112233",
                "blood_type": "B+",
                "known_allergies": [],
                "chronic_conditions": ["Diabetes Type 2"]
            },
            {
                "first_name": "Zuwena",
                "last_name": "Hassan",
                "date_of_birth": date(2000, 8, 5),
                "gender": "female",
                "national_id": "38901234",
                "phone_number": "0799887766",
                "blood_type": "AB+",
                "known_allergies": ["Peanuts", "Seafood"],
                "chronic_conditions": []
            }
        ]

        print("\nSeeding patients...")
        for p_data in patients:
            existing_patient = db.query(Patient).filter(Patient.national_id == p_data["national_id"]).first()
            if not existing_patient:
                new_patient = Patient(**p_data)
                db.add(new_patient)
                print(f"Created patient: {p_data['first_name']} {p_data['last_name']}")
            else:
                print(f"Patient {p_data['first_name']} {p_data['last_name']} already exists, skipping.")

        db.commit()
        print("\nSeeding completed successfully.")

    except Exception as e:
        print(f"Error during seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()