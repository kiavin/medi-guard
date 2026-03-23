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

    # --- Sub-Schemas for AI Prediction ---
class DifferentialContext(BaseModel):
    disease: str
    confidence: int = 0 # Defaulting to 0 in case the AI didn't assign a specific number
    reasoning: str = ""

class AIPredictionContext(BaseModel):
    primary_disease: str
    icd10: str
    confidence: int
    reasoning: str # NEW: Primary reasoning
    differentials: List[DifferentialContext] # UPDATED: Now uses strict sub-schema

class LabContext(BaseModel):
    id: str
    name: str
    result: str
    flag: str
    ref: str

class CloseContextResponse(BaseModel):
    consultation_id: str
    status: str
    patient: PatientContext # Assuming PatientContext was defined previously
    ai_prediction: Optional[AIPredictionContext] = None
    labs: List[Dict[str, Any]] = [] # Flexible for now, or use LabContext
    prescription_draft: List[Dict[str, Any]] = [] # NEW: Added for amended statuses

# --- 2. Commit Schemas (POST /close) ---
class FinalDiagnosisInput(BaseModel):
    disease: str
    icd10: str
    type: str
    clinical_justification: str
    is_ai_override: bool

class UpdatedLabInput(BaseModel):
    id: str
    result: str
    flag: str

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
    specialist_referral_flagged: bool

class ConsultationCloseRequest(BaseModel):
    final_diagnosis: FinalDiagnosisInput
    updated_labs: List[UpdatedLabInput] = []
    prescription: List[PrescriptionInput] = []
    outcome: OutcomeInput
    signature_pin: str

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