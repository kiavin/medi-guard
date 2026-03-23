from sqlalchemy import Column, String, Text, Integer, Numeric, DateTime, Date, Boolean, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

# Import your Base and the AuditMixin
from app.core.database import Base
from app.models.base import AuditMixin

# ==========================================
# 1. CONSULTATIONS TABLE
# ==========================================
class Consultation(Base, AuditMixin):
    __tablename__ = "consultations"

    # Foreign Keys
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    clinician_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    
    # Clinical Data
    chief_complaint = Column(Text, nullable=False)
    clinical_notes = Column(Text, nullable=True)
    final_diagnosis = Column(String(255), nullable=True)
    treatment_plan = Column(Text, nullable=True)
    status = Column(String, default="open") # "open", "amended", "closed"
    
    lab_results = Column(JSON, default=list)
    
    # Vitals
    bp_systolic = Column(Integer, nullable=True)
    bp_diastolic = Column(Integer, nullable=True)
    heart_rate = Column(Integer, nullable=True)
    temperature = Column(Numeric(4, 1), nullable=True)
    
    # Metadata
    consultation_date = Column(DateTime, default=datetime.utcnow)
    follow_up_date = Column(Date, nullable=True)
    status = Column(String(20), default="open") # open, completed, cancelled

    # Relationships (Using string names avoids circular imports!)
    patient = relationship("Patient", back_populates="consultations")
    clinician = relationship("User", back_populates="consultations")
    symptoms = relationship("Symptom", back_populates="consultation", cascade="all, delete-orphan")
    predictions = relationship(
        "Prediction", 
        back_populates="consultation", 
        cascade="all, delete-orphan",
        order_by="desc(Prediction.created_at)" 
    )
    medications = relationship("Medication", back_populates="consultation", cascade="all, delete-orphan") 

# ==========================================
# 2. SYMPTOMS TABLE
# ==========================================

class Symptom(Base, AuditMixin): # Assuming you are using your AuditMixin
    __tablename__ = "symptoms"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    consultation_id = Column(String, ForeignKey("consultations.id", ondelete="CASCADE"))
    
    # Updated column names to match the frontend JSON exactly
    name = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    duration = Column(String, nullable=True) # Changed to String to safely accept "2" or "2 days"
    
    # Relationship back to consultation
    consultation = relationship("Consultation", back_populates="symptoms")
# ==========================================
# 3. PREDICTIONS TABLE (AI Results)
# ==========================================
class Prediction(Base, AuditMixin):
    __tablename__ = "predictions"

    # unique=True enforces a 1-to-1 relationship (one prediction per consultation)
    consultation_id = Column(String(36), ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False)
    
    primary_disease = Column(String(255), nullable=False)
    primary_confidence = Column(Numeric(5, 4), nullable=False) # e.g. 0.8750
    differentials = Column(JSONB, nullable=True) # Stores the alternative predictions
    recommended_tests = Column(JSONB, nullable=True) # Stores suggested labs
    model_used = Column(String(100), nullable=False)
    raw_response = Column(JSONB, nullable=False) # Keep the raw Gemini API response for auditing
    was_confirmed = Column(Boolean, nullable=True)

    # Relationship back to the parent consultation
    consultation = relationship("Consultation", back_populates="predictions")
    lab_requests = relationship("LabRequest", back_populates="consultation")
    lab_requests = relationship("LabRequest", back_populates="consultation", cascade="all, delete-orphan")