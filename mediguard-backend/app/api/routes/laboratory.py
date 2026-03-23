from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.api.dependencies import get_db, get_current_active_user
from app.models.user import User
from app.models.consultation import Consultation
from app.models.laboratory import LabRequest
from app.schemas.laboratory import LabRequestCreate, LabResultUpdate, LabRequestResponse
from app.core.response import send_success

router = APIRouter()

# 1. DOCTOR: Order a new test
@router.post("/order", response_model=dict)
def order_lab_test(
    payload: LabRequestCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    new_request = LabRequest(
        consultation_id=payload.consultation_id,
        patient_id=payload.patient_id,
        ordered_by_id=current_user.id,
        test_name=payload.test_name,
        status="pending"
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    
    return send_success(data={"id": new_request.id, "status": "pending"})

# 2. LAB TECH: View the pending queue (Global or Patient-specific)
@router.get("/queue", response_model=dict)
def get_lab_queue(
    status: str = "pending", 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # This powers the Lab Dashboard. Shows all tests waiting for results.
    requests = db.query(LabRequest).filter(LabRequest.status == status).order_by(LabRequest.ordered_at.asc()).all()
    
    # Convert to Pydantic models for clean serialization
    data = [LabRequestResponse.model_validate(req).model_dump() for req in requests]
    return send_success(data=data)

# 3. LAB TECH: Enter results
@router.put("/{request_id}/result", response_model=dict)
def submit_lab_result(
    request_id: str,
    payload: LabResultUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    lab_request = db.query(LabRequest).filter(LabRequest.id == request_id).first()
    if not lab_request:
        raise HTTPException(status_code=404, detail="Lab request not found")
        
    lab_request.status = "completed"
    lab_request.result_value = payload.result_value
    lab_request.reference_range = payload.reference_range
    lab_request.flag = payload.flag
    lab_request.notes = payload.notes
    lab_request.handled_by_id = current_user.id
    lab_request.completed_at = datetime.utcnow()
    
    db.commit()
    
    return send_success(message="Lab results saved successfully", theme="success", alert_type="toast")