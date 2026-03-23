from sqlalchemy import Column, String, Integer, Date, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import AuditMixin

# ==========================================
# MEDICATIONS TABLE
# ==========================================
class Medication(Base, AuditMixin):
    __tablename__ = "medications"

    consultation_id = Column(String(36), ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    prescribing_clinician_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    
    drug_name = Column(String(200), nullable=False)
    dosage = Column(String(100), nullable=False)
    frequency = Column(String(100), nullable=False)
    duration_days = Column(Integer, nullable=False)
    prescribed_date = Column(Date, nullable=False)

    # Relationships
    consultation = relationship("Consultation", back_populates="medications")
    patient = relationship("Patient", back_populates="medications")
    clinician = relationship("User", back_populates="prescriptions")

# ==========================================
# MEDICATION INTERACTIONS (Safety Rules)
# ==========================================
class MedicationInteraction(Base, AuditMixin):
    __tablename__ = "medication_interactions"

    drug_a = Column(String(200), nullable=False, index=True)
    drug_b = Column(String(200), nullable=False, index=True)
    severity = Column(String(50), nullable=False) # critical, high, moderate, low
    effect = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)
    source = Column(String(100), nullable=False)