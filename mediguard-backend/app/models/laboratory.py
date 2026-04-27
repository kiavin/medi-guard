import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

# Import your core Base and AuditMixin exactly like the User model
from app.core.database import Base
from app.models.base import AuditMixin

class LabRequest(Base, AuditMixin):
    __tablename__ = "lab_requests"

    # Primary Key (Assuming AuditMixin only handles timestamps, not the ID)
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Core Foreign Keys
    consultation_id = Column(String, ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(String, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    
    # Audit trail for personnel
    ordered_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    handled_by_id = Column(String, ForeignKey("users.id"), nullable=True) 

    # Test Details
    test_name = Column(String, nullable=False) 
    status = Column(String, default="pending") 

    # Results 
    result_value = Column(String, nullable=True)
    reference_range = Column(String, nullable=True)
    flag = Column(String, nullable=True) 
    notes = Column(Text, nullable=True)
    ai_interpretation = Column(Text, nullable=True)

    # Specific Lab Timestamps
    ordered_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # ==========================================
    # RELATIONSHIPS
    # ==========================================
    consultation = relationship("Consultation", back_populates="lab_requests")
    patient = relationship("Patient", back_populates="lab_requests")
    
    # Links back to the User model so we know exactly who ordered and who resulted it
    ordered_by = relationship("User", foreign_keys=[ordered_by_id], back_populates="labs_ordered")
    handled_by = relationship("User", foreign_keys=[handled_by_id], back_populates="labs_handled")
