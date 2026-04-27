from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Any, Dict, Literal
from datetime import date, datetime

# ==========================================
# 1. SYMPTOM SCHEMAS
# ==========================================
class SymptomBase(BaseModel):
    symptom_name: str = Field(..., min_length=2, max_length=200)
    snomed_code: Optional[str] = None
    severity: str = Field(..., pattern="^(mild|moderate|severe)$")
    duration_days: Optional[int] = Field(None, ge=0)
    is_free_text: bool = False

class SymptomCreate(BaseModel):
    name: str
    severity: str
    duration: str

class SymptomResponse(BaseModel):
    id: str
    name: str
    severity: str
    duration: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 2. PREDICTION SCHEMAS (AI Results)
# ==========================================
class PredictionBase(BaseModel):
    primary_disease: str
    primary_confidence: float = Field(..., ge=0.0, le=1.0)
    differentials: Optional[List[Dict[str, Any]]] = None
    recommended_tests: Optional[List[str]] = None
    model_used: str
    raw_response: Dict[str, Any]
    was_confirmed: Optional[bool] = None

    model_config = ConfigDict(protected_namespaces=())

class PredictionCreate(PredictionBase):
    pass

class PredictionResponse(PredictionBase):
    id: str
    consultation_id: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        protected_namespaces=() # Suppresses warnings for fields starting with 'model_'
    )

# ==========================================
# 3. CONSULTATION SCHEMAS
# ==========================================
class ConsultationBase(BaseModel):
    patient_id: str
    chief_complaint: str 
    clinical_notes: Optional[str] = None
    final_diagnosis: Optional[str] = None
    treatment_plan: Optional[str] = None
    
    # We keep these as standard types here so the response doesn't crash 
    # if historical legacy data exists.
    bp_systolic: Optional[int] = None
    bp_diastolic: Optional[int] = None
    heart_rate: Optional[int] = None
    temperature: Optional[float] = None
# 1. Update the Symptom sub-model to enforce severity
class SymptomCreate(BaseModel):
    name: str = Field(..., min_length=1)
    # Enforces that severity is provided AND matches your UI buttons exactly
    severity: Literal["Mild", "Moderate", "Severe"] = Field(..., description="Severity is required")
    # Duration can remain optional as the UI shows it as a placeholder input
    duration: Optional[str] = None

class ConsultationCreate(BaseModel):
    """
    Strictly enforces that all fields necessary for the AI CDSS engine 
    must be filled out perfectly before a record can be opened.
    """
    patient_id: str
    
    # AI Requirement 1: A valid chief complaint
    chief_complaint: str = Field(..., min_length=5, description="Chief complaint is required for AI prediction")
    
    # FIXED: Removed Optional[str]. Clinical notes are now strictly required.
    clinical_notes: str = Field(..., min_length=2, description="Clinical observations are required")
    
    # AI Requirement 2: Strict Vital Signs (No zeros allowed)
    bp_systolic: int = Field(..., ge=50, le=250)
    bp_diastolic: int = Field(..., ge=30, le=150)
    heart_rate: int = Field(..., ge=30, le=300)
    temperature: float = Field(..., ge=30.0, le=45.0)
    
    # AI Requirement 3: At least one actual symptom recorded
    # (The severity requirement is now handled by the SymptomCreate model above)
    symptoms: List[SymptomCreate] = Field(..., min_length=1, description="At least one symptom is required")
    
    final_diagnosis: Optional[str] = None
    treatment_plan: Optional[str] = None
    lab_results: Optional[List[Dict[str, Any]]] = []
    
    save_as_draft: bool = True

class ConsultationFinalize(BaseModel):
    final_diagnosis: str
    treatment_plan: str
    lab_results: Optional[List[Dict[str, Any]]] = []

class ConsultationResponse(ConsultationBase):
    id: str
    clinician_id: str
    consultation_date: datetime
    follow_up_date: Optional[date] = None
    status: str
    
    symptoms: List[SymptomResponse] = []
    predictions: List[PredictionResponse] = []    
    model_config = ConfigDict(from_attributes=True)

class ConsultationUpdate(BaseModel):
    chief_complaint: Optional[str] = None
    clinical_notes: Optional[str] = None
    final_diagnosis: Optional[str] = None
    treatment_plan: Optional[str] = None
    symptoms: Optional[List[SymptomCreate]] = None

class ConsultationDiagnosisUpdate(BaseModel):
    final_diagnosis: str = Field(..., min_length=1)

# ==========================================
# 4. SUMMARY SCHEMAS (Closed Consultation)
# ==========================================
class LabSummary(BaseModel):
    test_name: str
    result_value: Optional[str] = None
    flag: Optional[str] = None

class MedicationSummary(BaseModel):
    drug_name: str
    dosage: str
    duration_days: int

class AIPredictionSummary(BaseModel):
    primary_disease: str
    confidence: int

class ConsultationSummaryResponse(BaseModel):
    consultation_date: datetime # The date it was closed
    presenting_symptoms: List[str]
    ai_prediction: Optional[AIPredictionSummary] = None
    final_diagnosis: Dict[str, str] # { "disease": "...", "icd10": "..." }
    labs: List[LabSummary]
    medications: List[MedicationSummary]
