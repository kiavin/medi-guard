import requests
import time

# Adjust this to match your local FastAPI server URL
BASE_URL = "http://localhost:9673/api"

# If your local environment requires a test token, add it here
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwZjkzNjFjMC04MmZlLTQxNmMtYTc5OS1iNTMxZTZkOTExMmYiLCJyb2xlIjoiY2xpbmljaWFuIiwiZXhwIjoxNzc2NzgwODQ0fQ.zKPAQjZDyFzoL6hfNY4SFfiaSjzKbLXST4mO5pjMVoU"
}

def create_patient(data):
    print(f"Creating patient: {data['first_name']} {data['last_name']}...")
    res = requests.post(f"{BASE_URL}/patients", json=data, headers=HEADERS)
    if res.status_code == 201:
        return res.json()["dataPayload"]["data"]["id"]
    print(f"Error creating patient: {res.text}")
    return None

def open_consultation(data):
    print(f"  -> Opening consultation for {data['chief_complaint']}...")
    res = requests.post(f"{BASE_URL}/consultations/create", json=data, headers=HEADERS)
    if res.status_code == 201:
        return res.json()["dataPayload"]["data"]["id"]
    print(f"Error opening consultation: {res.text}")
    return None

def close_consultation(consult_id, data):
    print(f"  -> Closing historical consultation...")
    res = requests.post(f"{BASE_URL}/consultations/{consult_id}/close", json=data, headers=HEADERS)
    if res.status_code != 200:
        print(f"Error closing consultation: {res.text}")

# ==========================================
# SCENARIO 1: THE CHRONIC ASTHMATIC
# ==========================================
def seed_chronic_asthmatic():
    patient_id = create_patient({
        "first_name": "David", "last_name": "Mutua", "date_of_birth": "1985-04-12",
        "gender": "male", "national_id": "11223344", "phone_number": "0722000001"
    })
    
    if not patient_id: return

    # Historical: Initial Asthma Diagnosis (Closed)
    cons_1 = open_consultation({
        "patient_id": patient_id, "chief_complaint": "Shortness of breath after exercise",
        "clinical_notes": "Wheezing on auscultation.", "bp_systolic": 125, "bp_diastolic": 82,
        "heart_rate": 88, "temperature": 36.8, "symptoms": [{"name": "Wheezing", "severity": "Moderate"}]
    })
    close_consultation(cons_1, {
        "final_diagnosis": {"disease": "Bronchial Asthma", "icd10": "J45.9"},
        "prescription": [{"name": "Salbutamol Inhaler", "dose": "100mcg", "route": "Inhaled", "frequency": "PRN", "duration": "Ongoing", "notes": "Use during attacks"}],
        "updated_labs": [],
        "outcome": {"status": "closed", "specialist_referral_flagged": False, "closing_notes": "Diagnosed with chronic asthma. Educated on trigger avoidance.", "follow_up_interval": "6 months", "patient_instructions": "Keep inhaler at all times."}
    })

    # Active: Acute Exacerbation (Left Open for Dashboard)
    open_consultation({
        "patient_id": patient_id, "chief_complaint": "Severe chest tightness and wheezing for 2 hours",
        "clinical_notes": "Patient struggling to speak in full sentences. Known asthmatic.", 
        "bp_systolic": 135, "bp_diastolic": 88, "heart_rate": 112, "temperature": 37.0, 
        "symptoms": [{"name": "Dyspnea", "severity": "Severe"}]
    })

# ==========================================
# SCENARIO 2: THE SEVERE ALLERGY
# ==========================================
def seed_allergy_patient():
    patient_id = create_patient({
        "first_name": "Sarah", "last_name": "Wanjiku", "date_of_birth": "1992-11-05",
        "gender": "female", "national_id": "55667788", "phone_number": "0733000002"
    })
    
    if not patient_id: return

    # Historical: Penicillin Reaction (Closed)
    cons_1 = open_consultation({
        "patient_id": patient_id, "chief_complaint": "Full body rash and swelling after taking antibiotics",
        "clinical_notes": "Patient took Amoxicillin yesterday for a dental issue. Severe hives.", 
        "bp_systolic": 110, "bp_diastolic": 70, "heart_rate": 105, "temperature": 37.2, 
        "symptoms": [{"name": "Urticaria", "severity": "Severe"}]
    })
    close_consultation(cons_1, {
        "final_diagnosis": {"disease": "Penicillin Allergy / Anaphylaxis", "icd10": "Z88.0"},
        "prescription": [{"name": "Loratadine", "dose": "10mg", "route": "Oral", "frequency": "OD", "duration": "5 days", "notes": "Antihistamine"}],
        "updated_labs": [],
        "outcome": {"status": "closed", "specialist_referral_flagged": True, "closing_notes": "SEVERE PENICILLIN ALLERGY NOTED. Flagged in system.", "follow_up_interval": "None", "patient_instructions": "Never take Penicillin or Amoxicillin."}
    })

    # Active: UTI Presentation (Left Open for Dashboard to flag allergy warning)
    open_consultation({
        "patient_id": patient_id, "chief_complaint": "Painful urination and lower back pain",
        "clinical_notes": "Suspected UTI. MUST AVOID PENICILLINS due to history.", 
        "bp_systolic": 118, "bp_diastolic": 75, "heart_rate": 80, "temperature": 37.8, 
        "symptoms": [{"name": "Dysuria", "severity": "Moderate"}]
    })

# ==========================================
# SCENARIO 3: MOMBASA RAINY SEASON
# ==========================================
def seed_mombasa_seasonal():
    patient_id = create_patient({
        "first_name": "Fatima", "last_name": "Abubakar", "date_of_birth": "1990-08-14",
        "gender": "female", "national_id": "99001122", "phone_number": "0711000003"
    })
    
    if not patient_id: return

    # Historical: Malaria 3 months ago (Closed)
    cons_1 = open_consultation({
        "patient_id": patient_id, "chief_complaint": "Fever and chills",
        "clinical_notes": "Routine malaria presentation.", 
        "bp_systolic": 120, "bp_diastolic": 80, "heart_rate": 90, "temperature": 38.5, 
        "symptoms": [{"name": "Fever", "severity": "High"}]
    })
    close_consultation(cons_1, {
        "final_diagnosis": {"disease": "Uncomplicated Malaria", "icd10": "B50.9"},
        "prescription": [{"name": "Artemether-Lumefantrine", "dose": "20/120mg", "route": "Oral", "frequency": "BID", "duration": "3 days", "notes": "Standard regimen"}],
        "updated_labs": [],
        "outcome": {"status": "closed", "specialist_referral_flagged": False, "closing_notes": "Malaria treated.", "follow_up_interval": "PRN", "patient_instructions": "Use treated nets."}
    })

    # Active: Typhoid/Dengue Suspect (Left Open for Dashboard)
    open_consultation({
        "patient_id": patient_id, "chief_complaint": "Step-ladder fever and abdominal pain",
        "clinical_notes": "Patient returning with high fever during heavy rains.", 
        "bp_systolic": 110, "bp_diastolic": 70, "heart_rate": 98, "temperature": 39.1, 
        "symptoms": [{"name": "Fever", "severity": "Severe"}]
    })

if __name__ == "__main__":
    print("🚀 Starting Clinical Database Seed...")
    
    seed_chronic_asthmatic()
    time.sleep(1) # Slight pause to ensure DB timestamps sequence correctly
    
    seed_allergy_patient()
    time.sleep(1)
    
    seed_mombasa_seasonal()
    
    print("✅ Seeding Complete! Check your Vue Dashboards.")
