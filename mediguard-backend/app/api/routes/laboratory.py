from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from datetime import datetime

from app.api.dependencies import get_db, get_current_active_user, RoleChecker, QueryParams, apply_filters_and_paginate
from app.models.user import User
from app.models.consultation import Consultation
from app.models.patient import Patient
from app.models.laboratory import LabRequest
from app.schemas.laboratory import LabRequestCreate, LabResultUpdate, LabRequestResponse
from app.schemas.base_response import send_success
from app.services.ai_service import generate_lab_interpretation
from sqlalchemy.orm import Session, joinedload

router = APIRouter(
    prefix="/laboratory",
    tags=["Laboratory"],
    dependencies=[Depends(get_current_active_user)]
)

# 1. DOCTOR: Order a new test
@router.post("/order", response_model=dict)
def order_lab_test(
    payload: LabRequestCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["clinician"]))
):
    # Verify patient exists
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Verify consultation exists
    consultation = db.query(Consultation).filter(Consultation.id == payload.consultation_id).first()
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    if consultation.status == "closed":
        raise HTTPException(status_code=403, detail="Cannot modify a closed, immutable consultation record")

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


# ==========================================
# HELPER: GROUP LABS BY PATIENT
# ==========================================
def group_labs_by_patient(paginated_result: dict) -> dict:
    """Takes a paginated dictionary of LabRequests and groups them by Patient."""
    grouped_data = {}
    
    for item in paginated_result["items"]:
        p_id = item.patient_id
        
        # If we haven't seen this patient yet, create a new group
        if p_id not in grouped_data:
            first = item.patient.first_name if item.patient else "Unknown"
            last = item.patient.last_name if item.patient else "Patient"
            
            grouped_data[p_id] = {
                "patient_id": p_id,
                "patient_name": f"{first} {last}".strip(),
                "tests": []
            }
            
        # Serialize the test and add it to the patient's array
        test_dict = LabRequestResponse.model_validate(item).model_dump()
        grouped_data[p_id]["tests"].append(test_dict)

    # Replace the flat items list with our grouped list
    paginated_result["items"] = list(grouped_data.values())
    return paginated_result


# ==========================================
# 2A. VIEW ACTIVE/PENDING LABS (Grouped)
# ==========================================
@router.get("/active", response_model=dict)
def get_active_labs(
    params: QueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    user_role = getattr(current_user, "role", "")
    # Admins and Lab Techs can see everything. Doctors only see their own orders.
    can_see_all = user_role in ["admin", "lab_tech"]

    # Query for pending tests, eagerly loading the patient
    query = (
        db.query(LabRequest)
        .options(joinedload(LabRequest.patient))
        .filter(LabRequest.status == "pending")
    )
    
    # Role-Based Filter: Doctors only see their own orders
    if not can_see_all:
        query = query.filter(LabRequest.ordered_by_id == current_user.id)
        
    query = query.order_by(desc(LabRequest.ordered_at))

    result = apply_filters_and_paginate(
        query=query,
        model=LabRequest,
        params=params,
        search_columns=["test_name"]
    )
    
    # Apply grouping helper
    grouped_result = group_labs_by_patient(result)
    return send_success(data=grouped_result)


# ==========================================
# 2B. VIEW COMPLETED LABS (Grouped)
# ==========================================
@router.get("/completed", response_model=dict)
def get_completed_labs(
    params: QueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    is_admin = getattr(current_user, "role", "") == "admin"

    # Query for completed tests
    query = (
        db.query(LabRequest)
        .options(joinedload(LabRequest.patient))
        .filter(LabRequest.status == "completed")
    )
    
    # Role-Based Filter
    if not is_admin:
        query = query.filter(LabRequest.ordered_by_id == current_user.id)
        
    query = query.order_by(desc(LabRequest.completed_at))

    result = apply_filters_and_paginate(
        query=query,
        model=LabRequest,
        params=params,
        search_columns=["test_name"]
    )
    
    # Apply grouping helper
    grouped_result = group_labs_by_patient(result)
    return send_success(data=grouped_result)

# 2. LAB TECH: View the pending queue (Global or Patient-specific)
@router.get("/queue", response_model=dict)
def get_lab_queue(
    params: QueryParams = Depends(),
    status: str = "pending", 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Eagerly load the Patient model alongside the LabRequest
    query = (
        db.query(LabRequest)
        .options(joinedload(LabRequest.patient))
        .filter(LabRequest.status == status)
    )
    
    result = apply_filters_and_paginate(
        query=query,
        model=LabRequest,
        params=params,
        search_columns=["test_name"]
    )
    
    # Serialize items and inject the full patient name for the UI
    formatted_items = []
    for item in result["items"]:
        # Dump the Pydantic schema to a standard dictionary
        data_dict = LabRequestResponse.model_validate(item).model_dump()
        
        # Build the full name if the patient record exists
        if item.patient:
            first = item.patient.first_name or ""
            last = item.patient.last_name or ""
            data_dict["patient_name"] = f"{first} {last}".strip()
        else:
            data_dict["patient_name"] = "Unknown Patient"
            
        formatted_items.append(data_dict)
        
    result["items"] = formatted_items
    
    return send_success(data=result)
# 3. LAB TECH: Enter results
@router.put("/{request_id}/result", response_model=dict)
def submit_lab_result(
    request_id: str,
    payload: LabResultUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["lab_tech"]))
):
    lab_request = db.query(LabRequest).filter(LabRequest.id == request_id).first()
    if not lab_request:
        raise HTTPException(status_code=404, detail="Lab request not found")

    consultation = db.query(Consultation).filter(Consultation.id == lab_request.consultation_id).first()
    if consultation and consultation.status == "closed":
        raise HTTPException(status_code=403, detail="Cannot modify a closed, immutable consultation record")
        
    lab_request.status = "completed"
    lab_request.result_value = payload.result_value
    lab_request.reference_range = payload.reference_range
    lab_request.flag = payload.flag
    lab_request.notes = payload.notes
    lab_request.handled_by_id = current_user.id
    lab_request.completed_at = datetime.utcnow()
    
    # STEP 1: Integrate an AI call to generate a brief 'AI Lab Interpretation' string
    patient = db.query(Patient).filter(Patient.id == lab_request.patient_id).first()
    if patient:
        try:
            lab_request.ai_interpretation = generate_lab_interpretation(patient, lab_request)
        except Exception as e:
            # Don't fail the whole request if AI fails
            print(f"AI Lab Interpretation failed: {str(e)}")
    
    db.commit()
    
    return send_success(
        data=LabRequestResponse.model_validate(lab_request).model_dump(),
        message="Lab results saved and interpreted by AI successfully", 
        theme="success", 
        alert_type="toast"
    )

# 4. DOCTOR: Get specific patient lab history
@router.get("/patient/{patient_id}/history", response_model=dict)
def get_patient_lab_history(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns the lab history for a specific patient, 
    grouping by test name and showing the latest results.
    """
    # Fetch all completed lab requests for this patient
    lab_history = db.query(LabRequest).filter(
        LabRequest.patient_id == patient_id,
        LabRequest.status == "completed"
    ).order_by(desc(LabRequest.completed_at)).all()

    # Create a summary of "last known result" for specific test names
    last_known_results = {}
    for lr in lab_history:
        if lr.test_name not in last_known_results:
            last_known_results[lr.test_name] = LabRequestResponse.model_validate(lr).model_dump()

    return send_success(data={
        "history": [LabRequestResponse.model_validate(lr).model_dump() for lr in lab_history],
        "summary": list(last_known_results.values())
    })
