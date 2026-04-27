from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import date, datetime

# ==========================================
# MEDICATION SCHEMAS
# ==========================================
class MedicationBase(BaseModel):
    dosage: Optional[str] = ""
    
    # NEW: Added route and notes to match the frontend payload and updated DB model
    route: Optional[str] = None
    notes: Optional[str] = None
    
    frequency: Optional[str] = ""
    duration_days: int = Field(..., gt=0, le=365)
    prescribed_date: date

class MedicationCreate(MedicationBase):
    consultation_id: str
    patient_id: str

class MedicationResponse(MedicationBase):
    id: str
    prescribing_clinician_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# MEDICATION INTERACTION SCHEMAS
# ==========================================
class InteractionBase(BaseModel):
    drug_a: str
    drug_b: str
    severity: str = Field(..., pattern="^(critical|high|moderate|low)$")
    effect: str
    recommendation: str
    source: str

class InteractionCreate(InteractionBase):
    pass

class InteractionResponse(InteractionBase):
    id: str
    model_config = ConfigDict(from_attributes=True)

class InteractionCheckRequest(BaseModel):
    patient_id: str
    drugs: List[str]