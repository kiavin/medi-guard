from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class LabRequestCreate(BaseModel):
    consultation_id: str
    patient_id: str
    test_name: str

class LabResultUpdate(BaseModel):
    result_value: str
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
    
    ordered_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)