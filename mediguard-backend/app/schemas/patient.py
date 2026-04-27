from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List, Optional
from datetime import date, datetime
from app.schemas.consultation import ConsultationResponse
from app.schemas.medication import MedicationResponse

class PatientBase(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    date_of_birth: date
    gender: str = Field(..., pattern="^(Male|Female|Other|male|female|other)$")
    national_id: str = Field(..., min_length=5, max_length=50)
    phone_number: str = Field(..., min_length=9, max_length=20)
    blood_type: Optional[str] = None
    known_allergies: List[str] = []
    chronic_conditions: List[str] = []

    @field_validator("gender")
    @classmethod
    def normalize_gender(cls, v: str) -> str:
        return v.capitalize()

class PatientCreate(PatientBase):
    pass

class PatientResponse(PatientBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    blood_type: Optional[str] = None
    known_allergies: Optional[list[str]] = None
    chronic_conditions: Optional[list[str]] = None

class PatientProfileResponse(PatientResponse):
    """
    A comprehensive schema for the Patient Dashboard.
    Includes the base patient demographics PLUS all their medical history.
    """
    consultations: List[ConsultationResponse] = []
    medications: List[MedicationResponse] = []

class ActiveAlert(BaseModel):
    type: str
    severity: str
    title: str
    message: str

class ClinicalSummary(BaseModel):
    last_visit_date: Optional[datetime] = None
    last_diagnosis: Optional[str] = None
    active_medications_count: int = 0
    chronic_conditions_count: int = 0
    active_alerts: List[ActiveAlert] = []

class PatientConsultationSummaryResponse(BaseModel):
    id: str
    patient_number: str 
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str
    blood_type: Optional[str] = None
    ward: str = "Outpatient" # Default value for the UI
    known_allergies: List[str] = []
    clinical_summary: ClinicalSummary

class MedicationHistoryItem(BaseModel):
    id: str
    drug_name: str
    dosage: Optional[str]=""
    route: Optional[str]=""
    frequency: Optional[str] = ""
    duration_days: int
    notes: Optional[str] = ""
    prescribed_date: date
    consultation_id: str
    prescribing_clinician_id: str

    class Config:
        from_attributes = True