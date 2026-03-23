from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy import or_, and_

from app.api.dependencies import get_db, get_current_active_user, RoleChecker
from app.models.medication import Medication, MedicationInteraction
from app.models.user import User
from app.schemas.medication import MedicationCreate, MedicationResponse, InteractionCreate, InteractionResponse
from app.schemas.base_response import APIResponse, send_success

router = APIRouter(prefix="/medications", tags=["Medications"])

@router.post("/prescribe", response_model=APIResponse[MedicationResponse], status_code=status.HTTP_201_CREATED)
def prescribe_medication(
    med_in: MedicationCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Prescribe a medication to a patient under a specific consultation."""
    
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

@router.post("/interactions", response_model=APIResponse[InteractionResponse], status_code=status.HTTP_201_CREATED)
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