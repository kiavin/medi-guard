from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime

class LabRequestCreate(BaseModel):
    consultation_id: str = Field(..., min_length=1)
    patient_id: str = Field(..., min_length=1)
    test_name: str = Field(..., min_length=1)

class LabResultUpdate(BaseModel):
    result_value: str = Field(..., min_length=1)
    reference_range: Optional[str] = None
    flag: str = "normal" # Default to normal, UI can provide high/low/critical
    notes: Optional[str] = None

class LabRequestResponse(BaseModel):
    id: str
    consultation_id: str
    patient_id: str
    test_name: str
    status: str
    
    result_value: Optional[str] = None
    reference_range: Optional[str] = None
    flag: Optional[str] = None
    notes: Optional[str] = None
    ai_interpretation: Optional[str] = None
    
    ordered_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# --- NEW SCHEMA FOR GROUPING ---
class PatientLabGroup(BaseModel):
    patient_id: str
    patient_name: str
    tests: List[LabRequestResponse]