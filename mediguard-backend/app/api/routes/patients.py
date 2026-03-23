import os
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session,selectinload

from app.api.dependencies import get_db, get_current_active_user
from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientResponse, PatientUpdate
from app.schemas.base_response import APIResponse, send_success
from app.core.database import SessionLocal
from app.models.consultation import Consultation
from app.schemas.patient import PatientProfileResponse, PatientConsultationSummaryResponse, ClinicalSummary, ActiveAlert

# Create the router (Groups all /patients URLs together)
router = APIRouter(
    prefix="/patients",
    tags=["Patients"]
)

@router.post("/register", response_model=APIResponse[PatientResponse], status_code=status.HTTP_201_CREATED)
def register_patient(
    patient: PatientCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Register a new patient into the MediGuard system.
    """
    existing_patient = db.query(Patient).filter(Patient.national_id == patient.national_id).first()
    if existing_patient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="A patient with this National ID already exists."
        )
    
    new_patient = Patient(**patient.model_dump())
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)
    
    return send_success(
        data=new_patient,
        message="Patient successfully registered.",
        theme="success",
        alert_type="alert"
    )

# You can easily add a GET route here later to list patients!
@router.get("/", response_model=APIResponse[list[PatientResponse]])
def get_patients(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve a list of all patients.
    """
    patients = db.query(Patient).offset(skip).limit(limit).all()
    return send_success(data=patients)


@router.put("/{patient_id}", response_model=APIResponse[PatientResponse])
def update_patient_details(
    patient_id: str, 
    patient_in: PatientUpdate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update patient demographics. Updates in place to preserve medical history relationships."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    
    # Update only the fields provided in the payload
    update_data = patient_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(patient, key, value)
        
    db.commit()
    db.refresh(patient)
    
    return send_success(
        data=patient,
        message="Patient details updated successfully.",
        theme="success",
        alert_type="toast"
    )

# ==========================================
# BACKGROUND TASK LOGIC
# ==========================================
def generate_patient_excel_export(user_email: str):
    """
    Runs in the background. Opens a fresh DB session, fetches data, 
    compiles the Excel file, and saves it.
    """
    db = SessionLocal() # Open a NEW connection
    try:
        patients = db.query(Patient).all()
        
        # Flatten the data for Excel
        export_data = []
        for p in patients:
            export_data.append({
                "ID": p.id,
                "First Name": p.first_name,
                "Last Name": p.last_name,
                "DOB": p.date_of_birth.strftime("%Y-%m-%d"),
                "Gender": p.gender,
                "National ID": p.national_id,
                "Phone": p.phone_number,
                "Status": "Active" if p.is_active else "Disabled",
                "Registered On": p.created_at.strftime("%Y-%m-%d %H:%M")
            })
            
        df = pd.DataFrame(export_data)
        
        # Ensure the exports folder exists
        os.makedirs("exports", exist_ok=True)
        filename = f"exports/patient_roster_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # Write to Excel
        df.to_excel(filename, index=False)
        print(f"SUCCESS: Export completed and saved to {filename}")
        
        # TODO: Integrate with your email service to email the file or download link to user_email
        
    except Exception as e:
        print(f"FAILED: Export crashed with error: {str(e)}")
    finally:
        db.close() # Always close the background connection!



@router.put("/{patient_id}/disable", response_model=APIResponse[PatientResponse])
def disable_patient(
    patient_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Soft-delete a patient. They will no longer appear in active searches, 
    but their historical consultation data remains perfectly intact.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
        
    patient.is_active = False
    db.commit()
    db.refresh(patient)
    
    return send_success(
        data=patient,
        message=f"{patient.first_name} {patient.last_name} has been disabled.",
        theme="warning", # Orange warning toast
        alert_type="toast"
    )

@router.post("/export", response_model=APIResponse[dict])
def request_patient_export(
    background_tasks: BackgroundTasks, # <-- FastAPI injects the task manager
    current_user: User = Depends(get_current_active_user)
):
    """
    Triggers an asynchronous export of all patient data to an Excel file.
    """
    # 1. Add the heavy function to the background queue
    background_tasks.add_task(generate_patient_excel_export, current_user.email)
    
    # 2. Instantly return success to the frontend
    return send_success(
        data={"status": "queued"},
        message="Export queued successfully. You will receive an email when your file is ready.",
        theme="info",
        alert_type="alert" # Persistent alert message
    )

@router.get("/{patient_id}/profile", response_model=APIResponse[PatientProfileResponse])
def get_patient_full_profile(
    patient_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve a comprehensive patient profile, including all historical 
    consultations, AI predictions, symptoms, and prescribed medications.
    """
    # Use selectinload to eagerly fetch all nested relationships in a few optimized queries
    # rather than triggering a new database call for every single item.
    patient = db.query(Patient).options(
        selectinload(Patient.consultations).selectinload(Consultation.symptoms),
        selectinload(Patient.consultations).selectinload(Consultation.predictions),
        selectinload(Patient.medications)
    ).filter(Patient.id == patient_id).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
        
    return send_success(data=patient)

# ==========================================
# SINGLE PATIENT EXPORT TASK
# ==========================================
def generate_single_patient_export(patient_id: str, user_email: str):
    """Generates a multi-sheet Excel workbook for a single patient's complete history."""
    db = SessionLocal()
    try:
        # Fetch the entire nested patient record
        from sqlalchemy.orm import selectinload
        patient = db.query(Patient).options(
            selectinload(Patient.consultations).selectinload(Consultation.predictions),
            selectinload(Patient.medications)
        ).filter(Patient.id == patient_id).first()

        if not patient:
            return

        # 1. Demographics Sheet
        df_demo = pd.DataFrame([{
            "Patient ID": patient.id,
            "Name": f"{patient.first_name} {patient.last_name}",
            "DOB": patient.date_of_birth.strftime("%Y-%m-%d"),
            "Gender": patient.gender,
            "Blood Type": patient.blood_type,
            "Allergies": ", ".join(patient.known_allergies) if patient.known_allergies else "None",
            "Chronic Conditions": ", ".join(patient.chronic_conditions) if patient.chronic_conditions else "None"
        }])

        # 2. Consultations Sheet
        cons_data = []
        for c in patient.consultations:
            cons_data.append({
                "Date": c.consultation_date.strftime("%Y-%m-%d"),
                "Complaint": c.chief_complaint,
                "Status": c.status.upper(),
                "AI Diagnosis": c.prediction.primary_disease if c.prediction else "Not Run",
                "Final Diagnosis": c.final_diagnosis or "Pending"
            })
        df_cons = pd.DataFrame(cons_data)

        # 3. Medications Sheet
        meds_data = []
        for m in patient.medications:
            meds_data.append({
                "Prescribed Date": m.prescribed_date.strftime("%Y-%m-%d"),
                "Drug": m.drug_name,
                "Dosage": m.dosage,
                "Frequency": m.frequency,
                "Duration (Days)": m.duration_days
            })
        df_meds = pd.DataFrame(meds_data)

        # Ensure directory exists and create the multi-sheet Excel file
        os.makedirs("exports", exist_ok=True)
        filename = f"exports/patient_record_{patient.last_name}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        with pd.ExcelWriter(filename) as writer:
            df_demo.to_excel(writer, sheet_name="Demographics", index=False)
            if not df_cons.empty:
                df_cons.to_excel(writer, sheet_name="Consultations", index=False)
            if not df_meds.empty:
                df_meds.to_excel(writer, sheet_name="Medications", index=False)

        print(f"SUCCESS: Single patient record exported to {filename}")
        # TODO: Email the file to user_email
        
    except Exception as e:
        print(f"FAILED: Single patient export crashed: {str(e)}")
    finally:
        db.close()

# ==========================================
# SINGLE PATIENT EXPORT ENDPOINT
# ==========================================
@router.post("/{patient_id}/export", response_model=APIResponse[dict])
def export_single_patient(
    patient_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Triggers an async generation of a comprehensive multi-sheet Excel file for one patient."""
    # Verify patient exists quickly before queuing
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
        
    background_tasks.add_task(generate_single_patient_export, patient_id, current_user.email)
    
    return send_success(
        data={"status": "queued"},
        message="Patient record export queued. You will be notified when it is ready.",
        theme="info",
        alert_type="toast"
    )

@router.put("/{patient_id}/enable", response_model=APIResponse[PatientResponse])
def enable_patient(
    patient_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Restores a soft-deleted patient so they appear in active searches again.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
        
    patient.is_active = True
    db.commit()
    db.refresh(patient)
    
    return send_success(
        data=patient,
        message=f"{patient.first_name} {patient.last_name}'s profile has been restored.",
        theme="success",
        alert_type="toast"
    )

@router.get("/{patient_id}/consultation-summary", response_model=APIResponse[PatientConsultationSummaryResponse])
def get_patient_consultation_summary(
    patient_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns a lightweight, computed snapshot of the patient specifically 
    designed for the 'New Consultation' screen. Includes smart alerts.
    """
    # 1. Fetch patient with relationships eager-loaded
    patient = db.query(Patient).options(
        selectinload(Patient.consultations),
        selectinload(Patient.medications)
    ).filter(Patient.id == patient_id).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")

    # 2. Sort consultations to find the most recent
    sorted_consultations = sorted(patient.consultations, key=lambda x: x.consultation_date, reverse=True)
    last_consultation = sorted_consultations[0] if sorted_consultations else None

    # 3. Calculate metrics
    active_meds = [m for m in patient.medications if getattr(m, 'status', 'active') == 'active']
    chronic_count = len(patient.chronic_conditions) if patient.chronic_conditions else 0

    # 4. Generate Smart CDSS Alerts
    alerts = []
    
    # Alert Rule 1: High frequency of the same diagnosis (e.g., Malaria recurrence)
    if last_consultation and last_consultation.final_diagnosis:
        recent_diagnosis = last_consultation.final_diagnosis
        # Count how many times they had this diagnosis in all past visits
        recurrence_count = sum(1 for c in sorted_consultations if c.final_diagnosis == recent_diagnosis)
        
        if recurrence_count >= 2:
            alerts.append(ActiveAlert(
                type="recurrence",
                severity="warning",
                title="Recurrence Alert",
                message=f"'{recent_diagnosis}' diagnosed {recurrence_count}× recently. Verify symptom overlap with new presentation."
            ))

    # Alert Rule 2: Chronic condition requires attention
    if chronic_count > 0 and "Asthma" in patient.chronic_conditions:
         alerts.append(ActiveAlert(
                type="chronic_care",
                severity="info",
                title="Protocol Reminder",
                message="Patient has Asthma. Check peak flow meter readings during vitals intake."
         ))

    # 5. Build the final payload
    summary = ClinicalSummary(
        last_visit_date=last_consultation.consultation_date if last_consultation else None,
        last_diagnosis=last_consultation.final_diagnosis if last_consultation else "None Recorded",
        active_medications_count=len(active_meds),
        chronic_conditions_count=chronic_count,
        active_alerts=alerts
    )

    response_data = {
        "id": patient.id,
        "patient_number": f"PT-{patient.national_id[-4:]}" if patient.national_id else f"PT-{patient.id[:4].upper()}",
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "date_of_birth": patient.date_of_birth,
        "gender": patient.gender,
        "blood_type": patient.blood_type,
        "ward": "General Medicine", 
        "known_allergies": patient.known_allergies or [],
        "clinical_summary": summary.model_dump()
    }

    # Use send_success. By not passing a message, 'alertify' will be null in the payload.
    return send_success(data=response_data)