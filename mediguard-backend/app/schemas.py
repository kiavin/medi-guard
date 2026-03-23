from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import date, datetime

# ==========================================
# PATIENT SCHEMAS
# ==========================================

class PatientBase(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    date_of_birth: date
    gender: str = Field(..., pattern="^(Male|Female|Other)$")
    national_id: str = Field(..., min_length=5, max_length=50)
    phone_number: str = Field(..., min_length=9, max_length=20)
    blood_type: Optional[str] = None
    known_allergies: List[str] = []
    chronic_conditions: List[str] = []

# Schema for creating a new patient (POST request)
class PatientCreate(PatientBase):
    pass

# Schema for returning patient data (GET request)
class PatientResponse(PatientBase):
    id: str
    created_at: datetime
    updated_at: datetime

    # This tells Pydantic to safely read data from the SQLAlchemy ORM model
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# SYMPTOM SCHEMAS
# ==========================================

class SymptomBase(BaseModel):
    symptom_name: str
    severity: str = Field(..., pattern="^(mild|moderate|severe)$")
    duration_days: Optional[int] = Field(None, ge=0)
    is_free_text: bool = False

class SymptomCreate(SymptomBase):
    pass

class SymptomResponse(SymptomBase):
    id: str
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# CONSULTATION SCHEMAS
# ==========================================

class ConsultationBase(BaseModel):
    patient_id: str
    clinician_id: str
    chief_complaint: str = Field(..., min_length=5)
    clinical_notes: Optional[str] = None
    bp_systolic: Optional[int] = Field(None, ge=50, le=250)
    bp_diastolic: Optional[int] = Field(None, ge=30, le=150)
    heart_rate: Optional[int] = Field(None, ge=30, le=300)
    temperature: Optional[float] = Field(None, ge=30.0, le=45.0)

class ConsultationCreate(ConsultationBase):
    # When creating a consultation, the clinician might also send symptoms
    symptoms: List[SymptomCreate] = []

class ConsultationResponse(ConsultationBase):
    id: str
    consultation_date: datetime
    status: str
    symptoms: List[SymptomResponse] = []
    
    model_config = ConfigDict(from_attributes=True)