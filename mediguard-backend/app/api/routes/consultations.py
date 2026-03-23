from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime
from app.api.dependencies import get_db, get_current_active_user
from app.models.consultation import Consultation, Symptom, Prediction
from app.models.patient import Patient
from app.models.user import User
from app.schemas.consultation import (
    ConsultationCreate,
    ConsultationResponse,
    ConsultationUpdate,
    ConsultationFinalize,
)
from app.schemas.base_response import APIResponse, send_success
from app.schemas.closing import (
    CloseContextResponse,
    DifferentialContext,
    PatientContext,
    AIPredictionContext,
    LabContext,
    ConsultationCloseRequest,
    ConsultationCloseResponse,
    ConsultationCloseSummary,
)

# from app.core.response import send_success

router = APIRouter(prefix="/consultations", tags=["Consultations"])


@router.post(
    "/create",
    response_model=APIResponse[ConsultationResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_consultation(
    consultation_in: ConsultationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Open a new consultation. Usually saved as a draft (status='open') during triage.
    """
    patient = db.query(Patient).filter(Patient.id == consultation_in.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")

    symptoms_data = consultation_in.symptoms

    # Strip out the Pydantic-only fields before dumping to SQLAlchemy
    consultation_dict = consultation_in.model_dump(
        exclude={"symptoms", "save_as_draft"}
    )

    consultation_dict["clinician_id"] = current_user.id

    # Handle the Draft Flag
    consultation_dict["status"] = "open" if consultation_in.save_as_draft else "closed"

    new_consultation = Consultation(**consultation_dict)

    if symptoms_data:
        for symp in symptoms_data:
            new_consultation.symptoms.append(Symptom(**symp.model_dump()))

    db.add(new_consultation)
    db.commit()
    db.refresh(new_consultation)

    msg = (
        "Consultation saved as draft."
        if consultation_in.save_as_draft
        else "Consultation finalized and closed."
    )
    return send_success(
        data=new_consultation, message=msg, theme="success", alert_type="toast"
    )


@router.get("/{consultation_id}", response_model=APIResponse[ConsultationResponse])
def get_consultation(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve a specific consultation along with its recorded symptoms.
    """
    consultation = (
        db.query(Consultation).filter(Consultation.id == consultation_id).first()
    )
    if not consultation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found."
        )

    return send_success(data=consultation)


@router.put(
    "/{consultation_id}/amend", response_model=APIResponse[ConsultationResponse]
)
def amend_consultation(
    consultation_id: str,
    update_in: ConsultationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Immutable update: Marks the old consultation as 'amended' and creates a new,
    updated record to maintain a strict clinical audit trail.
    """
    old_consultation = (
        db.query(Consultation).filter(Consultation.id == consultation_id).first()
    )
    if not old_consultation:
        raise HTTPException(status_code=404, detail="Consultation not found.")

    # 1. Lock the old record
    old_consultation.status = "amended"

    # 2. Build the new record, merging old data with the new changes
    new_data = {
        "patient_id": old_consultation.patient_id,
        "clinician_id": current_user.id,  # Record the specific doctor making the amendment
        "bp_systolic": old_consultation.bp_systolic,
        "bp_diastolic": old_consultation.bp_diastolic,
        "heart_rate": old_consultation.heart_rate,
        "temperature": old_consultation.temperature,
        "chief_complaint": update_in.chief_complaint
        or old_consultation.chief_complaint,
        "clinical_notes": update_in.clinical_notes or old_consultation.clinical_notes,
        "final_diagnosis": update_in.final_diagnosis
        or old_consultation.final_diagnosis,
        "treatment_plan": update_in.treatment_plan or old_consultation.treatment_plan,
        "status": "open",  # The new active record
    }

    new_consultation = Consultation(**new_data)

    # 3. Duplicate the old symptoms over to the new record
    for old_symptom in old_consultation.symptoms:
        # Exclude the ID and consultation_id so SQLAlchemy generates fresh ones
        symp_data = {
            c.name: getattr(old_symptom, c.name)
            for c in old_symptom.__table__.columns
            if c.name not in ["id", "consultation_id", "created_at", "updated_at"]
        }
        new_consultation.symptoms.append(Symptom(**symp_data))

    db.add(new_consultation)
    db.commit()
    db.refresh(new_consultation)

    return send_success(
        data=new_consultation,
        message="Consultation amended securely. Audit trail updated.",
        theme="info",
        alert_type="toast",
    )


@router.get(
    "/patient/{patient_id}", response_model=APIResponse[List[ConsultationResponse]]
)
def get_patient_consultations(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Fetch all consultations for a specific patient, ordered by newest first."""
    consultations = (
        db.query(Consultation)
        .filter(Consultation.patient_id == patient_id)
        .order_by(Consultation.consultation_date.desc())
        .all()
    )

    return send_success(data=consultations)


@router.put(
    "/{consultation_id}/finalize", response_model=APIResponse[ConsultationResponse]
)
def finalize_consultation(
    consultation_id: str,
    finalize_in: ConsultationFinalize,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Called after AI predictions and lab results are in.
    Saves the final diagnosis/treatment and locks the consultation (status='closed').
    """
    consultation = (
        db.query(Consultation).filter(Consultation.id == consultation_id).first()
    )
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found.")

    if consultation.status == "closed":
        raise HTTPException(
            status_code=400,
            detail="This consultation is already closed and cannot be altered.",
        )

    # Update the final fields
    consultation.final_diagnosis = finalize_in.final_diagnosis
    consultation.treatment_plan = finalize_in.treatment_plan

    # If new lab results were sent, append them to existing ones or overwrite
    if finalize_in.lab_results:
        existing_labs = consultation.lab_results or []
        existing_labs.extend(finalize_in.lab_results)
        consultation.lab_results = existing_labs

    consultation.status = "closed"  # Lock it!

    db.commit()
    db.refresh(consultation)

    return send_success(
        data=consultation,
        message="Consultation finalized and locked successfully.",
        theme="success",
        alert_type="toast",
    )


# ==========================================
# 1. The Hydration Endpoint
# ==========================================
@router.get("/{consultation_id}/close-context", response_model=dict)
def get_closing_context(
    consultation_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delivers the state of the world for the Vue frontend to mount the closing screen.
    Perfectly formatted for the UI payload requirements.
    """
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    patient = consultation.patient
    
    # Grab the most recent AI prediction
    latest_prediction = db.query(Prediction).filter(
        Prediction.consultation_id == consultation_id
    ).order_by(Prediction.created_at.desc()).first()

    # Calculate Age
    age = (datetime.utcnow().date() - patient.date_of_birth).days // 365 if patient.date_of_birth else "Unknown"
    
    # --- AI Data Processing ---
    ai_context = None
    if latest_prediction:
        raw_ai = latest_prediction.raw_response or {}
        
        # Process differentials to match UI expectations
        processed_differentials = []
        for diff in (latest_prediction.differentials or []):
            processed_differentials.append(DifferentialContext(
                disease=diff.get("disease", "Unknown"),
                confidence=diff.get("confidence", 0), 
                reasoning=diff.get("reasoning", "")
            ))

        ai_context = AIPredictionContext(
            primary_disease=latest_prediction.primary_disease,
            icd10="A90", # Or map dynamically if you add it to the AI prompt
            confidence=int(latest_prediction.primary_confidence * 100),
            reasoning=raw_ai.get("reasoning", "No clinical reasoning provided by the AI."),
            differentials=processed_differentials
        )
    
    # Map the final response
    context_data = CloseContextResponse(
        consultation_id=consultation.id,
        status=consultation.status, # Captures "open", "amended", or "closed"
        patient=PatientContext(
            id=f"PT-{patient.national_id[-4:]}" if patient.national_id else patient.id[:8],
            name=f"{patient.first_name} {patient.last_name}",
            age=f"{age}",
            sex=f"{patient.gender[0].upper()}",
            blood_type=patient.blood_type or "Unknown",
            allergies=patient.known_allergies or [],
            chronic_conditions=patient.chronic_conditions or [],
            latest_vitals={
                "bp": f"{consultation.bp_systolic}/{consultation.bp_diastolic}",
                "temp": str(consultation.temperature),
                "hr": consultation.heart_rate,
                # Add these if you add them to the consultation model later!
                "weight": "34 kg", 
                "o2": "98%"
            }
        ),
        ai_prediction=ai_context,
        labs=consultation.lab_results or [],
        # If you have a prescription model later, you would map it here for 'amended' statuses
        prescription_draft=[] 
    )

    return send_success(data=context_data.model_dump())


# ==========================================
# 2. The Reference Data Endpoint
# ==========================================
@router.get("/reference/pharmacology", response_model=dict)
def get_pharmacology_matrix(current_user: User = Depends(get_current_active_user)):
    """
    Provides the drug interaction matrix for the frontend safety engine.
    """
    matrix = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "drugs": {
            "Artemether-Lumefantrine": {
                "class": "Antimalarial",
                "interactions": {"Halofantrine": "critical", "Mefloquine": "warning"},
                "contraindications": ["Liver failure", "Renal failure"],
                "allergen_classes": [],
            },
            "Amoxicillin": {
                "class": "Penicillin antibiotic",
                "interactions": {"Warfarin": "warning", "Methotrexate": "critical"},
                "contraindications": [],
                "allergen_classes": ["Penicillin"],
            },
        },
    }
    return send_success(data=matrix)


# ==========================================
# 3. The Commit Endpoint
# ==========================================
@router.post("/{consultation_id}/close", response_model=dict)
def close_consultation(
    consultation_id: str,
    payload: ConsultationCloseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Transactional commit. Locks the consultation and generates the prescription.
    """
    consultation = (
        db.query(Consultation).filter(Consultation.id == consultation_id).first()
    )

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    if consultation.status == "closed":
        raise HTTPException(status_code=400, detail="Consultation is already closed")

    # 1. Validate Signature PIN (Mock logic - replace with actual user hashing check)
    if (
        payload.signature_pin != "123456"
    ):  # Replace with verify_password(payload.signature_pin, current_user.pin_hash)
        raise HTTPException(
            status_code=403, detail={"signature_pin": "Invalid signature PIN"}
        )

    # 2. Update Consultation Record
    consultation.final_diagnosis = payload.final_diagnosis.disease
    consultation.treatment_plan = payload.outcome.closing_notes
    consultation.status = "closed"

    # 3. Update Labs (Merge existing with updated)
    if payload.updated_labs:
        existing_labs = consultation.lab_results or []
        # Logic to merge or overwrite labs based on IDs would go here
        consultation.lab_results = existing_labs

    db.commit()

    # 4. Generate the Response Payload for the UI Overlay
    response_data = ConsultationCloseResponse(
        consultation_id=consultation.id,
        status="closed",
        closed_at=datetime.utcnow(),
        prescription_id=f"RX-{str(uuid.uuid4())[:8].upper()}",
        pharmacy_status="transmitted",
        summary=ConsultationCloseSummary(
            diagnosis_recorded=f"{payload.final_diagnosis.disease} · {payload.final_diagnosis.icd10}",
            drugs_issued_count=len(payload.prescription),
            follow_up=payload.outcome.follow_up_interval,
        ),
    )

    return send_success(
        data=response_data.model_dump(),
        message="Consultation closed and prescription transmitted securely.",
        theme="success",
        alert_type="toast",
    )
