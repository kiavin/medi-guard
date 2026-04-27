from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    BackgroundTasks,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import desc, and_
from typing import List
import uuid
import hashlib
import asyncio
from datetime import datetime, timedelta
import re

from app.api.dependencies import (
    get_db,
    get_current_active_user,
    RoleChecker,
    QueryParams,
    apply_filters_and_paginate,
)
from app.models.consultation import Consultation, Symptom, Prediction
from app.models.patient import Patient
from app.models.user import User
from app.models.laboratory import LabRequest
from app.models.medication import Medication

# Schemas
from app.schemas.consultation import (
    ConsultationCreate,
    ConsultationResponse,
    ConsultationUpdate,
    ConsultationFinalize,
    ConsultationDiagnosisUpdate,
    ConsultationSummaryResponse,
)
from app.schemas.base_response import APIResponse, send_success
from app.schemas.closing import (
    CloseContextResponse,
    DifferentialContext,
    PatientContext,
    AIPredictionContext,
    LabContext,
    PriorLab,
    RecurrenceFlag,
    ConsultationCloseRequest,
    ConsultationCloseResponse,
    ConsultationCloseSummary,
)

# New Imports for AI and WebSockets
from app.services.ai_service import (
    generate_clinical_prediction,
    generate_lab_interpretation,
)
from app.websockets.manager import ws_manager
from app.core.database import SessionLocal  # Needed for background DB tasks
from app.models.patient import Patient
router = APIRouter(
    prefix="/consultations",
    tags=["Consultations"],
    dependencies=[Depends(get_current_active_user)],
)


# ==========================================
# HELPER: SYMPTOM HASHING
# ==========================================
def generate_symptom_hash(consultation: Consultation, symptoms: list) -> str:
    """Generates a unique SHA-256 hash based on vitals and current symptoms."""
    raw = f"v:{consultation.bp_systolic}/{consultation.bp_diastolic}-{consultation.heart_rate}-{consultation.temperature}|s:"
    symptom_strings = [f"{s.name}-{s.severity}-{s.duration}" for s in symptoms]
    raw += "|".join(sorted(symptom_strings))
    return hashlib.sha256(raw.encode()).hexdigest()


# ==========================================
# 1. WEBSOCKET ROUTE (The Nervous System)
# ==========================================
@router.websocket("/{consultation_id}/ws")
async def consultation_websocket(websocket: WebSocket, consultation_id: str):
    await ws_manager.connect(websocket, consultation_id)
    try:
        while True:
            # Keep the connection alive silently
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, consultation_id)


# ==========================================
# 2. CREATE CONSULTATION
# ==========================================
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
    patient = db.query(Patient).filter(Patient.id == consultation_in.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")

    # Concurrency Lock: Prevent double-charting
    active_consultation = (
        db.query(Consultation)
        .filter(
            Consultation.patient_id == consultation_in.patient_id,
            Consultation.status == "ongoing",
        )
        .first()
    )

    if active_consultation:
        raise HTTPException(
            status_code=400,
            detail="Patient already has an active ongoing consultation.",
        )

    consultation_dict = consultation_in.model_dump(
        exclude={"symptoms", "save_as_draft"}
    )
    consultation_dict["clinician_id"] = current_user.id
    consultation_dict["status"] = "ongoing"

    new_consultation = Consultation(**consultation_dict)

    if consultation_in.symptoms:
        for symp in consultation_in.symptoms:
            new_consultation.symptoms.append(Symptom(**symp.model_dump()))

    db.add(new_consultation)
    db.commit()
    db.refresh(new_consultation)

    return send_success(
        data=new_consultation,
        message="Consultation started successfully.",
        theme="success",
        alert_type="toast",
    )


# ==========================================
# 3. AI PREDICTION (With Caching Guardrail)
# ==========================================
@router.post("/{consultation_id}/predict", response_model=dict)
def run_ai_prediction(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    consultation = (
        db.query(Consultation)
        .options(
            selectinload(Consultation.symptoms), selectinload(Consultation.patient)
        )
        .filter(Consultation.id == consultation_id)
        .first()
    )

    if not consultation or consultation.status == "closed":
        raise HTTPException(status_code=400, detail="Invalid consultation state.")

    # 1. Calculate current hash
    current_hash = generate_symptom_hash(consultation, consultation.symptoms)

    # 2. Check if we already ran this exact scenario
    if consultation.last_symptoms_hash == current_hash:
        latest_prediction = (
            db.query(Prediction)
            .filter(Prediction.consultation_id == consultation_id)
            .order_by(Prediction.created_at.desc())
            .first()
        )
        return send_success(
            data=latest_prediction.raw_response,
            message="Loaded from cache. No changes detected.",
            theme="info",
        )

    # 3. Mismatch! Run the local Llama Model (Takes ~10-15s on your 8-core CPU)
    ai_result_dict = generate_clinical_prediction(
        consultation, consultation.patient, consultation.symptoms
    )

    # 4. Save the new prediction (FIXED TYPO HERE: using ai_result_dict instead of prediction_result)
    new_prediction = Prediction(
        consultation_id=consultation.id,
        primary_disease=ai_result_dict.get("primary_disease", "Unknown"),
        primary_confidence=ai_result_dict.get("primary_confidence", 0.0),
        differentials=ai_result_dict.get("differentials", []),
        recommended_tests=ai_result_dict.get("recommended_tests", []),
        model_used="Local Llama 3", 
        raw_response=ai_result_dict,
    )

    # 5. Update the hash lock
    consultation.last_symptoms_hash = current_hash

    db.add(new_prediction)
    db.commit()

    return send_success(
        data=ai_result_dict, message="AI Analysis complete.", theme="success"
    )


# ==========================================
# 4. LAB TECH RESULT ENTRY (Triggers Background AI)
# ==========================================
async def background_lab_ai_analysis(consultation_id: str, lab_request_id: str):
    """Runs outside the HTTP request cycle to prevent UI freezing."""
    # Create a fresh DB session for the background thread
    db = SessionLocal()
    try:
        lab_req = db.query(LabRequest).filter(LabRequest.id == lab_request_id).first()
        consultation = (
            db.query(Consultation).filter(Consultation.id == consultation_id).first()
        )
        patient = consultation.patient

        # Run Local LLM Inference
        ai_interpretation = generate_lab_interpretation(patient, lab_req)

        # Save to DB
        lab_req.ai_interpretation = ai_interpretation
        db.commit()

        # Broadcast the result to the Doctor's Vue UI
        payload = {
            "event": "AI_LAB_SUMMARY_READY",
            "lab_id": lab_request_id,
            "data": ai_interpretation,
        }
        await ws_manager.broadcast(consultation_id, payload)
    finally:
        db.close()


@router.put("/{consultation_id}/labs/{lab_request_id}/results")
def update_lab_result(
    consultation_id: str,
    lab_request_id: str,
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["lab_tech"])),
):
    lab_req = db.query(LabRequest).filter(LabRequest.id == lab_request_id).first()
    if not lab_req:
        raise HTTPException(status_code=404, detail="Lab request not found")

    # Update lab data
    lab_req.result_value = payload.get("result_value")
    lab_req.reference_range = payload.get("reference_range")
    lab_req.flag = payload.get("flag")
    lab_req.status = "ready"
    lab_req.completed_at = datetime.utcnow()
    lab_req.handled_by_id = current_user.id

    db.commit()

    # Fire and Forget: Kick off the AI model in the background
    background_tasks.add_task(
        background_lab_ai_analysis, consultation_id, lab_request_id
    )

    return send_success(
        message="Lab results saved. AI analysis initiated.", theme="success"
    )


# ==========================================
# 5. PRESCRIBING SAFETY CHECK
# ==========================================
@router.post("/{consultation_id}/safety-check", response_model=dict)
def check_prescription_safety(
    consultation_id: str,
    payload: dict,  # List of proposed drugs
    db: Session = Depends(get_db),
):
    """
    Evaluates proposed drugs against patient allergies and chronic conditions
    before allowing the doctor to finalize the consultation.
    """
    consultation = (
        db.query(Consultation).filter(Consultation.id == consultation_id).first()
    )
    patient = consultation.patient
    proposed_drugs = payload.get("drugs", [])

    warnings = []

    # Very basic example check - this would tie into your pharmacology matrix
    patient_allergies = [a.lower() for a in (patient.known_allergies or [])]
    for drug in proposed_drugs:
        # Example: if drug class matches an allergy
        if (
            drug.lower() in patient_allergies
            or "penicillin" in patient_allergies
            and drug.lower() == "amoxicillin"
        ):
            warnings.append(f"CRITICAL ALLERGY: Patient is allergic to {drug}.")

    is_safe = len(warnings) == 0

    return send_success(
        data={"safe": is_safe, "warnings": warnings},
        message="Safety check complete." if is_safe else "Clinical warnings found!",
        theme="success" if is_safe else "danger",
    )


# ==========================================
# 6. UPDATE CONSULTATION
# ==========================================
@router.put("/{consultation_id}", response_model=APIResponse[ConsultationResponse])
def update_consultation_general(
    consultation_id: str,
    payload: ConsultationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    General update for clinical notes, chief complaint, AND Symptoms before closing.
    """
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    # SAFETY CHECK: Prevent edits if the file is closed!
    if consultation.status == "closed":
        raise HTTPException(status_code=403, detail="Cannot modify a closed, immutable consultation record.")

    # 1. Handle Standard Fields (Chief complaint, clinical notes, etc.)
    update_data = payload.model_dump(exclude_unset=True, exclude={"symptoms"})
    for key, value in update_data.items():
        setattr(consultation, key, value)

    # 2. Handle Symptoms Relationship (If the frontend sent an updated array)
    if payload.symptoms is not None:
        # Wipe the old symptoms for this consultation
        db.query(Symptom).filter(Symptom.consultation_id == consultation_id).delete()
        
        # Insert the newly updated symptoms
        for symp_data in payload.symptoms:
            new_symp = Symptom(
                consultation_id=consultation.id,
                name=symp_data.name,
                severity=symp_data.severity,
                duration=symp_data.duration
            )
            db.add(new_symp)

    db.commit()
    db.refresh(consultation)

    return send_success(
        data=consultation, 
        message="Consultation updated successfully."
    )

@router.put("/{consultation_id}/diagnosis", response_model=APIResponse[ConsultationResponse])
def update_consultation_diagnosis(
    consultation_id: str,
    payload: ConsultationDiagnosisUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Specifically updates the final diagnosis when the doctor locks it in.
    """
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
        
    if consultation.status == "closed":
        raise HTTPException(status_code=403, detail="Cannot modify a closed, immutable consultation record.")

    # Update the diagnosis
    consultation.final_diagnosis = payload.final_diagnosis
    
    db.commit()
    db.refresh(consultation)

    return send_success(
        data=consultation,
        message="Diagnosis locked in successfully."
    )


# ==========================================
# 7. FETCH CONSULTATION DATA
# ==========================================
@router.get("/{consultation_id}", response_model=APIResponse[ConsultationResponse])
def get_consultation(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    consultation = (
        db.query(Consultation).filter(Consultation.id == consultation_id).first()
    )
    if not consultation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found."
        )
    return send_success(data=consultation)


# ==========================================
# 8. CLOSING WORKSPACE ENDPOINTS
# ==========================================
@router.get("/{consultation_id}/close-context", response_model=dict)
def get_closing_context(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Delivers the state of the world for the Vue frontend to mount the closing screen.
    """
    consultation = (
        db.query(Consultation)
        .options(
            selectinload(Consultation.patient), selectinload(Consultation.lab_requests)
        )
        .filter(Consultation.id == consultation_id)
        .first()
    )

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    patient = consultation.patient

    # Grab the most recent AI prediction
    latest_prediction = (
        db.query(Prediction)
        .filter(Prediction.consultation_id == consultation_id)
        .order_by(Prediction.created_at.desc())
        .first()
    )

    # Calculate Age
    age = (
        (datetime.utcnow().date() - patient.date_of_birth).days // 365
        if patient.date_of_birth
        else "Unknown"
    )

    # --- AI Data Processing & Recurrence Check ---
    ai_context = None
    recurrence_flag = None
    if latest_prediction:
        raw_ai = latest_prediction.raw_response or {}

        processed_differentials = []
        for diff in latest_prediction.differentials or []:
            processed_differentials.append(
                DifferentialContext(
                    disease=diff.get("disease", "Unknown"),
                    confidence=diff.get("confidence", 0),
                    reasoning=diff.get("reasoning", ""),
                )
            )

        ai_context = AIPredictionContext(
            primary_disease=latest_prediction.primary_disease,
            icd10="A90",
            confidence=int(latest_prediction.primary_confidence * 100),
            reasoning=raw_ai.get(
                "reasoning", "No clinical reasoning provided by the AI."
            ),
            differentials=processed_differentials,
        )

        six_months_ago = datetime.utcnow() - timedelta(days=180)
        past_count = (
            db.query(Consultation)
            .filter(
                Consultation.patient_id == patient.id,
                Consultation.final_diagnosis == latest_prediction.primary_disease,
                Consultation.consultation_date >= six_months_ago,
                Consultation.id != consultation_id,
            )
            .count()
        )

        if past_count >= 3:
            recurrence_flag = RecurrenceFlag(
                title="Frequent Diagnosis Alert",
                message=f"Patient has been diagnosed with '{latest_prediction.primary_disease}' {past_count} times in the last 6 months. Consider underlying chronic issues or treatment failure.",
                severity="warning",
            )

    # --- Lab Results Processing ---
    processed_labs = []
    for lr in consultation.lab_requests:
        processed_labs.append(
            LabContext(
                id=lr.id,
                test_name=lr.test_name,
                status=lr.status,
                result_value=lr.result_value,
                reference_range=lr.reference_range,
                flag=lr.flag,
                ai_interpretation=lr.ai_interpretation,
            )
        )

    prior_labs_query = (
        db.query(LabRequest)
        .filter(
            LabRequest.patient_id == patient.id,
            LabRequest.consultation_id != consultation_id,
            LabRequest.status == "completed",
        )
        .order_by(LabRequest.completed_at.desc())
        .limit(5)
        .all()
    )

    prior_labs = [
        PriorLab(
            test_name=l.test_name,
            result_value=l.result_value,
            completed_at=l.completed_at,
        )
        for l in prior_labs_query
    ]

    context_data = CloseContextResponse(
        consultation_id=consultation.id,
        status=consultation.status,
        patient=PatientContext(
            id=patient.id,
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
                "weight": "34 kg",
                "o2": "98%",
            },
        ),
        ai_prediction=ai_context,
        labs=processed_labs,
        prior_labs=prior_labs,
        recurrence_flag=recurrence_flag,
        prescription_draft=[],
    )

    return send_success(data=context_data.model_dump())

@router.post("/{consultation_id}/close", response_model=dict)
def close_consultation(
    consultation_id: str,
    payload: ConsultationCloseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["clinician"])),
):
    """
    Transactional commit. Locks the consultation and saves final outcome details.
    """
    consultation = (
        db.query(Consultation).filter(Consultation.id == consultation_id).first()
    )

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    if consultation.status == "closed":
        raise HTTPException(status_code=403, detail="Cannot modify a closed, immutable consultation record")

    # 1. Update Lab Results
    if payload.updated_labs:
        for lab_data in payload.updated_labs:
            lab_req = db.query(LabRequest).filter(
                LabRequest.id == lab_data.lab_request_id,
                LabRequest.consultation_id == consultation_id
            ).first()
            if lab_req:
                lab_req.result_value = lab_data.result_value
                lab_req.reference_range = lab_data.reference_range
                lab_req.flag = lab_data.flag
                lab_req.ai_interpretation = lab_data.ai_summary
                
                # Only mark as completed if a result was actually typed in!
                if lab_data.result_value and lab_data.result_value.strip():
                    lab_req.status = "completed"
                    lab_req.completed_at = datetime.utcnow()
                    lab_req.handled_by_id = current_user.id
                else:
                    lab_req.status = "pending"
                    lab_req.flag = "pending"
# ==========================================
    # 🚨 CLINICAL GUARDRAIL: PENDING LABS CHECK 🚨
    # ==========================================
    pending_labs_count = db.query(LabRequest).filter(
        LabRequest.consultation_id == consultation_id,
        LabRequest.status != "completed"
    ).count()

    if pending_labs_count > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                    "msg": "Cannot close consultation: All ordered lab tests must have completed results first.",
                   
                }
        )
    # 2. Save Medications
    if payload.prescription:
        # Clear any existing drafts to prevent duplicates
        db.query(Medication).filter(Medication.consultation_id == consultation_id).delete()
        
        for drug in payload.prescription:
            # Safely extract digits if the doctor typed "7 days" instead of just "7"
            dur_str = str(drug.duration)
            numbers = re.findall(r'\d+', dur_str)
            duration_days = int(numbers[0]) if numbers else 1

            new_med = Medication(
                consultation_id=consultation_id,
                patient_id=consultation.patient_id,
                prescribing_clinician_id=current_user.id,
                drug_name=drug.name,
                dosage=drug.dose,
                route=drug.route,
                frequency=drug.frequency,
                duration_days=duration_days,
                notes=drug.notes,
                prescribed_date=datetime.utcnow().date()
            )
            db.add(new_med)

    # 3. Update Consultation Record
    consultation.final_diagnosis = payload.final_diagnosis.disease
    consultation.treatment_plan = payload.outcome.closing_notes
    consultation.follow_up_interval = payload.outcome.follow_up_interval
    consultation.patient_instructions = payload.outcome.patient_instructions
    consultation.status = "closed"

    db.commit()

    # 4. Generate the Response Payload
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
        message="Consultation closed and records finalized securely."
    )


@router.get("/{id}/summary", response_model=dict) # Changed to dict temporarily to avoid Pydantic errors while you test
def get_consultation_summary(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    consultation = (
        db.query(Consultation)
        .options(
            selectinload(Consultation.symptoms),
            selectinload(Consultation.predictions),
            selectinload(Consultation.lab_requests),
            selectinload(Consultation.medications),
        )
        .filter(Consultation.id == id)
        .first()
    )

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found.")

    # 1. Rich Symptoms (Includes severity and duration)
    presenting_symptoms = [
        {
            "name": s.name,
            "severity": s.severity,
            "duration": s.duration
        }
        for s in consultation.symptoms
    ]

    # 2. Vitals
    vitals = {
        "blood_pressure": f"{consultation.bp_systolic}/{consultation.bp_diastolic}" if consultation.bp_systolic else None,
        "heart_rate": consultation.heart_rate,
        "temperature": float(consultation.temperature) if consultation.temperature else None
    }

    # 3. AI Prediction (Added differentials)
    ai_prediction = None
    if consultation.predictions:
        latest_pred = consultation.predictions[0] 
        ai_prediction = {
            "primary_disease": latest_pred.primary_disease,
            "confidence": int(latest_pred.primary_confidence * 100),
            "differentials": latest_pred.differentials # Let's show alternative AI thoughts
        }

    icd10 = "Unknown" 
    if consultation.predictions:
        raw = consultation.predictions[0].raw_response or {}
        icd10 = raw.get("icd10", "Unknown") 
    
    final_diagnosis = {
        "disease": consultation.final_diagnosis or "Pending",
        "icd10": icd10
    }

    # 4. Rich Labs (Includes AI Interpretation & Ranges)
    labs = [
        {
            "test_name": l.test_name, 
            "status": l.status,
            "result_value": l.result_value, 
            "reference_range": l.reference_range,
            "flag": l.flag,
            "ai_interpretation": l.ai_interpretation, # The AI Tech summary!
            "notes": l.notes
        }
        for l in consultation.lab_requests 
    ]

    # 5. Rich Medications (Includes routing and notes)
    medications = [
        {
            "drug_name": m.drug_name, 
            "dosage": m.dosage, 
            "route": m.route,
            "frequency": m.frequency,
            "duration_days": m.duration_days,
            "notes": m.notes
        }
        for m in consultation.medications
    ]

    # 6. The Ultimate Summary Payload
    summary_data = {
        "consultation_id": consultation.id,
        "status": consultation.status,
        "consultation_date": consultation.created_at, 
        "closed_at": consultation.updated_at if consultation.status == "closed" else None,
        
        # Core Clinical Context
        "chief_complaint": consultation.chief_complaint,
        "clinical_notes": consultation.clinical_notes,
        "vitals": vitals,
        "presenting_symptoms": presenting_symptoms,
        
        # Outcomes & Plans
        "ai_prediction": ai_prediction,
        "final_diagnosis": final_diagnosis,
        "treatment_plan": consultation.treatment_plan,
        "patient_instructions": consultation.patient_instructions,
        "follow_up_interval": consultation.follow_up_interval,
        
        # Attached Records
        "labs": labs,
        "medications": medications,
    }

    return send_success(data=summary_data)

@router.get("/analytics/ai-accuracy", response_model=dict)
def get_ai_prediction_accuracy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Fetches all AI predictions and compares them against the final clinical diagnosis.
    """
    # 1. Query the Prediction table, joining the Consultation and Patient tables
    results = (
        db.query(Prediction, Consultation, Patient)
        .join(Consultation, Prediction.consultation_id == Consultation.id)
        .join(Patient, Consultation.patient_id == Patient.id)
        .order_by(Prediction.created_at.desc())
        .all()
    )

    formatted_history = []

    # 2. Loop through the joined rows and calculate the outcome
    for pred, consult, patient in results:
        
        # Calculate if the AI was correct (only if the file is actually closed)
        is_match = None
        if consult.status == "closed" and consult.final_diagnosis:
            # Simple string comparison (ignoring case)
            is_match = pred.primary_disease.lower().strip() == consult.final_diagnosis.lower().strip()

        formatted_history.append({
            "prediction_id": pred.id,
            "consultation_id": consult.id,
            "patient_name": f"{patient.first_name} {patient.last_name}",
            "ai_predicted_disease": pred.primary_disease,
            "confidence_score": pred.primary_confidence,
            "actual_diagnosis": consult.final_diagnosis or "Pending",
            "consultation_status": consult.status,
            "is_match": is_match,
            "queried_at": pred.created_at
        })

    # Optional: Calculate global accuracy percentage to show on the UI!
    total_closed = sum(1 for item in formatted_history if item["consultation_status"] == "closed")
    total_correct = sum(1 for item in formatted_history if item["is_match"] is True)
    
    global_accuracy = 0
    if total_closed > 0:
        global_accuracy = round((total_correct / total_closed) * 100, 1)

    return send_success(
        data={
            "global_accuracy_percentage": global_accuracy,
            "total_evaluated": total_closed,
            "history": formatted_history
        },
        message="AI Accuracy metrics retrieved successfully."
    )


# ==========================================
# 9. FETCH ALL CONSULTATIONS (Role-Based)
# ==========================================
@router.get("", response_model=dict)
def get_all_consultations(
    params: QueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns a paginated list of consultations.
    - Admins: See all consultations with attending doctor details.
    - Clinicians: See only consultations where they are the attending doctor.
    """
    # 1. Base query: Eagerly load both Patient and Clinician relationships
    query = db.query(Consultation).options(
        joinedload(Consultation.patient),
        joinedload(Consultation.clinician)
    )

    # 2. Role-Based Access Control (Adjust the 'role' check based on your User model)
    # Assuming your user model has a `.role` or `.is_admin` property
    is_admin = getattr(current_user, "role", "") == "admin"

    if not is_admin:
        # Doctors only see their own records
        query = query.filter(Consultation.clinician_id == current_user.id)

    # Order by newest first
    query = query.order_by(desc(Consultation.consultation_date))

    # 3. Apply your global pagination helper
    result = apply_filters_and_paginate(
        query=query,
        model=Consultation,
        params=params,
        search_columns=["chief_complaint", "final_diagnosis"]
    )

    # 4. Serialize and append role-specific data
    formatted_items = []
    for item in result["items"]:
        patient = item.patient
        clinician = item.clinician

        # Base data everyone sees
        data_dict = {
            "id": item.id,
            "status": item.status,
            "attending_doctor": f"Dr. {clinician.username}",
            "attending_doctor_id": item.clinician.id,
            "consultation_date": item.consultation_date,
            "chief_complaint": item.chief_complaint,
            "final_diagnosis": item.final_diagnosis,
            "patient_id": patient.id if patient else None,
            "patient_name": f"{patient.first_name} {patient.last_name}" if patient else "Unknown Patient",
        }

        # Admin-only data
        # Admin-only data
        if is_admin:
            data_dict["attending_doctor_id"] = clinician.id if clinician else None
            # CHANGED: Using username since first_name doesn't exist on the User model
            data_dict["attending_doctor_name"] = f"Dr. {clinician.username}" if clinician else "Unknown Doctor"
        formatted_items.append(data_dict)

    result["items"] = formatted_items

    return send_success(data=result, message="Consultations retrieved successfully.")