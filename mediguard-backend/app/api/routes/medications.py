from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy import or_, and_

from app.api.dependencies import get_db, get_current_active_user, RoleChecker
from app.models.consultation import Consultation
from app.models.medication import Medication, MedicationInteraction
from app.models.patient import Patient
from app.models.user import User
from app.schemas.medication import MedicationCreate, MedicationResponse, InteractionCreate, InteractionResponse, InteractionCheckRequest
from app.schemas.base_response import APIResponse, send_success

router = APIRouter(
    prefix="/medications",
    tags=["Medications"],
    dependencies=[Depends(get_current_active_user)]
)

@router.post("/prescribe", response_model=APIResponse[MedicationResponse], status_code=status.HTTP_201_CREATED)
def prescribe_medication(
    med_in: MedicationCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Prescribe a medication to a patient under a specific consultation."""
    
    consultation = db.query(Consultation).filter(Consultation.id == med_in.consultation_id).first()
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    if consultation.status == "closed":
        raise HTTPException(status_code=403, detail="Cannot modify a closed, immutable consultation record")
        
    
    # SAFETY CHECK: Check if the patient is already taking a conflicting drug
    active_meds = db.query(Medication).filter(Medication.patient_id == med_in.patient_id).all()
    
    for active_med in active_meds:
        # Check interactions table for drug_a = new drug AND drug_b = active drug (or vice versa)
        interaction = db.query(MedicationInteraction).filter(
            or_(
                and_(MedicationInteraction.drug_a == med_in.drug_name, MedicationInteraction.drug_b == active_med.drug_name),
                and_(MedicationInteraction.drug_a == active_med.drug_name, MedicationInteraction.drug_b == med_in.drug_name)
            )
        ).first()

        if interaction and interaction.severity in ["critical", "high"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"DANGEROUS INTERACTION DETECTED: {med_in.drug_name} interacts with {active_med.drug_name}. Effect: {interaction.effect}. Recommendation: {interaction.recommendation}"
            )

    # If safe, create prescription
    med_dict = med_in.model_dump()
    med_dict["prescribing_clinician_id"] = current_user.id
    
    new_med = Medication(**med_dict)
    db.add(new_med)
    db.commit()
    db.refresh(new_med)
    
    return send_success(
        data=new_med,
        message="Medication successfully prescribed.",
        theme="success",
        alert_type="alert"
    )

@router.get("/patient/{patient_id}", response_model=APIResponse[List[MedicationResponse]])
def get_patient_medications(patient_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Get all medications prescribed to a specific patient."""
    meds = db.query(Medication).filter(Medication.patient_id == patient_id).all()
    return send_success(data=meds)

# --- INTERACTION RULE MANAGEMENT (Admin Only) ---
allow_admin = RoleChecker(["admin"])

@router.post("/interactions/rule", response_model=APIResponse[InteractionResponse], status_code=status.HTTP_201_CREATED)
def add_interaction_rule(
    rule_in: InteractionCreate, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(allow_admin)
):
    """Add a new drug interaction safety rule (Admins only)."""
    new_rule = MedicationInteraction(**rule_in.model_dump())
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    
    return send_success(
        data=new_rule,
        message="Interaction rule added successfully.",
        theme="success",
        alert_type="alert"
    )

# ==========================================
# STEP 3: SAFETY CHECK (DRUGS vs ALLERGIES/CONDITIONS)
# ==========================================
@router.post("/interactions", response_model=dict)
def check_medication_safety(
    payload: InteractionCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Cross-references a list of drugs against:
    1. Each other (Drug-Drug interactions)
    2. Patient's known allergies
    3. Patient's chronic conditions
    """
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    warnings = []
    
    # 1. Drug-Drug Interactions (Internal list)
    for i in range(len(payload.drugs)):
        for j in range(i + 1, len(payload.drugs)):
            drug_a = payload.drugs[i]
            drug_b = payload.drugs[j]
            
            interaction = db.query(MedicationInteraction).filter(
                or_(
                    and_(MedicationInteraction.drug_a == drug_a, MedicationInteraction.drug_b == drug_b),
                    and_(MedicationInteraction.drug_a == drug_b, MedicationInteraction.drug_b == drug_a)
                )
            ).first()
            
            if interaction:
                warnings.append({
                    "type": "drug-drug",
                    "severity": interaction.severity,
                    "title": f"Interaction: {drug_a} & {drug_b}",
                    "message": interaction.effect,
                    "recommendation": interaction.recommendation
                })

    # 2. Drug-Allergy Checks (Simple substring match for now)
    allergies = patient.known_allergies or []
    for drug in payload.drugs:
        for allergy in allergies:
            if allergy.lower() in drug.lower() or drug.lower() in allergy.lower():
                warnings.append({
                    "type": "allergy",
                    "severity": "critical",
                    "title": f"Allergy Alert: {drug}",
                    "message": f"Patient is allergic to '{allergy}', which may conflict with {drug}.",
                    "recommendation": "Do not prescribe. Select alternative class."
                })

    # 3. Drug-Condition Checks (Mock logic - usually needs a mapping table)
    # For now, we'll flag common contraindications
    chronic_conditions = patient.chronic_conditions or []
    contraindications = {
        "Asthma": ["Beta-blockers", "NSAIDs", "Aspirin"],
        "Diabetes": ["Corticosteroids"],
        "Renal Failure": ["Metformin", "NSAIDs"],
        "Hypertension": ["Decongestants"]
    }
    
    for condition in chronic_conditions:
        if condition in contraindications:
            for drug in payload.drugs:
                for bad_drug in contraindications[condition]:
                    if bad_drug.lower() in drug.lower():
                        warnings.append({
                            "type": "condition",
                            "severity": "high",
                            "title": f"Condition Conflict: {condition}",
                            "message": f"{drug} is often contraindicated for patients with {condition}.",
                            "recommendation": "Verify patient stability and consider alternative."
                        })

    return send_success(
        data={
            "warnings": warnings,
            "is_safe": len([w for w in warnings if w['severity'] in ['critical', 'high']]) == 0
        }
    )
