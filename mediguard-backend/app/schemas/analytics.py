from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AIPredictionHistoryItem(BaseModel):
    prediction_id: str
    consultation_id: str
    patient_name: str
    ai_predicted_disease: str
    confidence_score: float
    actual_diagnosis: Optional[str] = None
    consultation_status: str
    is_match: Optional[bool] = None  # True if AI matched Doc, False if wrong, None if ongoing
    queried_at: datetime