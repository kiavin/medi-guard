from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import date, datetime

# ==========================================
# MEDICATION SCHEMAS
# ==========================================
class MedicationBase(BaseModel):
    drug_name: str = Field(..., min_length=2, max_length=200)
    dosage: str = Field(..., min_length=1, max_length=100)
    frequency: str = Field(..., min_length=1, max_length=100)
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