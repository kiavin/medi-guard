from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

# --- 1. Hydration Schemas (GET /close-context) ---
class PatientContext(BaseModel):
    id: str
    name: str
    age: str
    sex: str
    blood_type: str
    allergies: List[str]
    chronic_conditions: List[str]
    latest_vitals: Dict[str, Any]

class DifferentialContext(BaseModel):
    disease: str
    confidence: int = 0
    reasoning: str = ""

class AIPredictionContext(BaseModel):
    primary_disease: str
    icd10: str
    confidence: int
    reasoning: str 
    differentials: List[DifferentialContext] 

class LabContext(BaseModel):
    id: str
    test_name: str
    status: str
    result_value: Optional[str] = None
    reference_range: Optional[str] = None
    flag: Optional[str] = None
    ai_interpretation: Optional[str] = None

class PriorLab(BaseModel):
    test_name: str
    result_value: Optional[str] = None
    completed_at: Optional[datetime] = None

class RecurrenceFlag(BaseModel):
    title: str
    message: str
    severity: str

class CloseContextResponse(BaseModel):
    consultation_id: str
    status: str
    patient: PatientContext
    ai_prediction: Optional[AIPredictionContext] = None
    labs: List[LabContext] = []
    prior_labs: List[PriorLab] = []
    recurrence_flag: Optional[RecurrenceFlag] = None
    prescription_draft: List[Dict[str, Any]] = []

# --- 2. Commit Schemas (POST /close) ---
class FinalDiagnosisInput(BaseModel):
    disease: str
    icd10: str

class LabResultFinalize(BaseModel):
    lab_request_id: str
    result_value: str
    reference_range: str
    flag: str
    ai_summary: Optional[str] = None

class PrescriptionInput(BaseModel):
    name: str
    dose: str
    route: str
    frequency: str
    duration: str
    notes: Optional[str] = None

class OutcomeInput(BaseModel):
    status: str
    follow_up_interval: str
    closing_notes: str
    patient_instructions: Optional[str] = None
    specialist_referral_flagged: bool

class ConsultationCloseRequest(BaseModel):
    final_diagnosis: FinalDiagnosisInput
    updated_labs: List[LabResultFinalize] = []
    prescription: List[PrescriptionInput] = []
    outcome: OutcomeInput

class ConsultationCloseSummary(BaseModel):
    diagnosis_recorded: str
    drugs_issued_count: int
    follow_up: str

class ConsultationCloseResponse(BaseModel):
    consultation_id: str
    status: str
    closed_at: datetime
    prescription_id: str
    pharmacy_status: str
    summary: ConsultationCloseSummary

# ==========================================
# --- 3. NEW: Workflow Action Schemas ---
# ==========================================

# Used by the Lab Tech when submitting a single test result
class LabResultInput(BaseModel):
    result_value: str
    reference_range: str
    flag: str

# Used by the Doctor to check proposed drugs against allergies
class SafetyCheckRequest(BaseModel):
    drugs: List[str]

# The response returned by the safety engine
class SafetyCheckResponse(BaseModel):
    safe: bool
    warnings: List[str]