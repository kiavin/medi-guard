from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_active_user
from app.models.consultation import Consultation, Prediction
from app.models.patient import Patient
from app.models.user import User
from app.schemas.consultation import PredictionResponse
from app.schemas.base_response import APIResponse, send_success
from app.services.ai_service import generate_clinical_prediction
from typing import List
router = APIRouter(prefix="/ai", tags=["AI Diagnostics"])

@router.post("/predict/{consultation_id}", response_model=APIResponse[PredictionResponse], status_code=status.HTTP_201_CREATED)
def run_ai_diagnostics(
    consultation_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Run the AI CDSS engine on a specific consultation and save the prediction.
    """
    # 1. Fetch the consultation and its relationships
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found.")
        
    # Check if a prediction already exists to save API tokens
    # if consultation.prediction:
    #     raise HTTPException(status_code=400, detail="A prediction has already been generated for this consultation.")

    patient = consultation.patient
    symptoms = consultation.symptoms

    # 2. Call our AI Service
    try:
        ai_result = generate_clinical_prediction(consultation, patient, symptoms)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Engine Error: {str(e)}")

    # 3. Save the result to the predictions table
    new_prediction = Prediction(
        consultation_id=consultation.id,
        primary_disease=ai_result.get("primary_disease", "Unknown"),
        primary_confidence=ai_result.get("primary_confidence", 0.0),
        differentials=ai_result.get("differentials", []),
        recommended_tests=ai_result.get("recommended_tests", []),
        model_used="gemini-2.5-flash", 
        raw_response=ai_result # Save the raw dictionary directly to the JSONB column
    )
    
    db.add(new_prediction)
    db.commit()
    db.refresh(new_prediction)
    
    # Send normalized response to trigger the frontend global alerts system
    return send_success(
        data=new_prediction,
        message="AI diagnostics completed successfully.",
        theme="success",
        alert_type="alert"
    )

@router.get("/patient/{patient_id}", response_model=APIResponse[List[PredictionResponse]])
def get_patient_predictions(
    patient_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Fetch all AI predictions generated for a specific patient's past consultations."""
    predictions = db.query(Prediction)\
        .join(Consultation)\
        .filter(Consultation.patient_id == patient_id)\
        .all()
        
    return send_success(data=predictions)

@router.get("/consultation/{consultation_id}", response_model=APIResponse[PredictionResponse])
def get_prediction_by_consultation(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Fetch the specific AI diagnostic prediction generated for a single consultation.
    """
    prediction = db.query(Prediction).filter(Prediction.consultation_id == consultation_id).first()
    
    if not prediction:
        # We return a 404 here so the frontend knows to show a "Run AI" button 
        # instead of displaying past results.
        raise HTTPException(status_code=404, detail="No AI prediction found for this consultation.")
        
    return send_success(data=prediction)