import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

# Import your FastAPI app and database dependencies
from app.main import app 
from app.core.database import Base
from app.api.dependencies import get_db
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from datetime import date
# --- NEW: Tell SQLite how to handle Postgres JSONB ---
@compiles(JSONB, 'sqlite')
def compile_jsonb_sqlite(type_, compiler, **kw):
    return 'JSON'
# -----------------------------------------------------
# ---------------------------------------------------------
# 1. TEST DATABASE SETUP (Use an in-memory SQLite DB for fast testing)
# ---------------------------------------------------------
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_mediguard.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

# ---------------------------------------------------------
# 2. AUTHENTICATION HELPERS
# ---------------------------------------------------------
# In a real test, you'd hit the /login endpoint to get a token. 
# For this example, let's assume you have a helper or we mock the dependency.
# To keep this script focused on the workflow, we will override the auth dependency.

from app.api.dependencies import get_current_active_user
from app.models.user import User

def create_mock_user(role="clinician", user_id="test-doc-id"):
    return User(
        id=user_id,
        username=f"test_{role}",
        email=f"{role}@test.com",
        password_hash="mock_hashed_password_123",
        role=role,
        first_name="Test",
        last_name="User",
        status="active"
    )

# ---------------------------------------------------------
# 3. THE END-TO-END WORKFLOW TEST
# ---------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_database():
    # Create tables before each test and drop them after
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_full_clinical_workflow():
    
    # ==========================================
    # SCENE 1: ADMIN CREATES A PATIENT
    # ==========================================
    app.dependency_overrides[get_current_active_user] = lambda: create_mock_user("admin", "admin-id")
    
    patient_payload = {
        "first_name": "Test",
        "last_name": "Patient",
        "date_of_birth": date(1990, 1, 1), # <-- Changed to a real Python date object
        "gender": "male",
        "national_id": "123456789",
        "phone_number": "0700000000"
    }
    
    # Assuming you have a POST /patients endpoint
    # res = client.post("/api/patients", json=patient_payload)
    # assert res.status_code == 201
    # patient_id = res.json()["data"]["id"]
    
    # For this test, let's mock the patient ID since we are focusing on the new endpoints
    patient_id = "test-patient-uuid" 
    
    # We need to manually insert a patient into the test DB for the foreign keys to work
    db = TestingSessionLocal()
    from app.models.patient import Patient
    db.add(Patient(id=patient_id, **patient_payload))
    db.commit()


    # ==========================================
    # SCENE 2: DOCTOR OPENS CONSULTATION & ORDERS LABS
    # ==========================================
    # ==========================================
        # SCENE 2: DOCTOR OPENS CONSULTATION & ORDERS LABS
        # ==========================================
    doctor_id = "doc-123"
        
        # --- NEW: Save the doctor to the test DB so foreign keys work! ---
    db.add(create_mock_user("clinician", doctor_id))
    db.commit()
        # -----------------------------------------------------------------

    app.dependency_overrides[get_current_active_user] = lambda: create_mock_user("clinician", doctor_id)
    # 2a. Start Consultation
    consultation_payload = {
        "patient_id": patient_id,
        "chief_complaint": "Severe headache and fever",
        "clinical_notes": "Patient looks pale.",
        "bp_systolic": 120,
        "bp_diastolic": 80,
        "heart_rate": 75,
        "temperature": 38.5,
        "symptoms": [
            {"name": "Headache", "severity": "Severe", "duration": "2 days"}
        ]
    }
    res = client.post("/api/consultations/create", json=consultation_payload)
    assert res.status_code == 201, f"Failed to create consultation: {res.text}"
        
        # Print the response to see the structure
    print("\n--- CREATE CONSULTATION RESPONSE ---")
    print(res.json())
    print("------------------------------------\n")
        
        # Try to extract the ID, falling back to other common structures
    response_json = res.json()
    consultation_id = response_json["dataPayload"]["data"]["id"]
    
    # 2b. Order Labs
    lab_payload = {
        "consultation_id": consultation_id,
        "patient_id": patient_id,
        "test_name": "Complete Blood Count"
    }
    res = client.post("/api/laboratory/order", json=lab_payload)
    assert res.status_code == 200
    lab_request_id = res.json()["dataPayload"]["data"]["id"]


    # ==========================================
    # SCENE 3: LAB TECH VIEWS QUEUE & ENTERS RESULTS
    # ==========================================
    app.dependency_overrides[get_current_active_user] = lambda: create_mock_user("lab_tech", "lab-456")
    
    # 3a. Check Active Queue
    # 3a. Check Active Queue
    res = client.get("/api/laboratory/active")
    assert res.status_code == 200
        # The active queue should group by patient and have our pending test
    lab_res_data = res.json()["dataPayload"]["data"]
    grouped_data = lab_res_data.get("items", lab_res_data)
    assert len(grouped_data) == 1
    assert grouped_data[0]["patient_id"] == patient_id
    assert grouped_data[0]["tests"][0]["status"] == "pending"
    
    # 3b. Submit Results
    result_payload = {
        "result_value": "WBC 15.0 (High)",
        "reference_range": "4.5 - 11.0",
        "flag": "High"
    }
    res = client.put(f"/api/laboratory/{lab_request_id}/result", json=result_payload)
    assert res.status_code == 200


    # ==========================================
    # SCENE 4: DOCTOR CLOSES THE CONSULTATION
    # ==========================================
    app.dependency_overrides[get_current_active_user] = lambda: create_mock_user("clinician", doctor_id)
    
    close_payload = {
            "final_diagnosis": {
                "disease": "Bacterial Infection",
                "icd10": "A49.9"
            },
            "prescription": [
                {
                    "name": "Amoxicillin",
                    "dose": "500mg",
                    "route": "Oral",
                    "frequency": "TID",
                    "duration": "7 days",
                    "notes": "Take with food"
                }
            ],
            "updated_labs": [], 
            "outcome": {
                "status": "closed",                      # <-- MOVED THESE TWO HERE
                "specialist_referral_flagged": False,    # <-- MOVED THESE TWO HERE
                "closing_notes": "Prescribed antibiotics, rest advised.",
                "follow_up_interval": "1 week",
                "patient_instructions": "Drink plenty of fluids."
            }
        }
    
    res = client.post(f"/api/consultations/{consultation_id}/close", json=close_payload)
    assert res.status_code == 200, f"Validation Error: {res.json()}"
    assert res.json()["dataPayload"]["data"]["status"] == "closed"


    # ==========================================
    # SCENE 5: ADMIN REVIEWS ALL CONSULTATIONS
    # ==========================================
    # ==========================================
    
    app.dependency_overrides[get_current_active_user] = lambda: create_mock_user("admin", "admin-id")
        
    res = client.get("/api/consultations")
    assert res.status_code == 200
    all_consultations = res.json()["dataPayload"]["data"]["items"]
    assert len(all_consultations) == 1
    
    # Verify the role-based logic appended the attending doctor!
    assert "attending_doctor_name" in all_consultations[0]
    assert "test_clinician" in all_consultations[0]["attending_doctor_name"]

    print("\n✅ End-to-End Workflow Test Passed Successfully!")