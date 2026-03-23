from sqlalchemy import Column, String, Date, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

# Import your Base and the AuditMixin
from app.core.database import Base
from app.models.base import AuditMixin

class Patient(Base, AuditMixin):
    __tablename__ = "patients"

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(20), nullable=False)
    national_id = Column(String(50), unique=True, index=True, nullable=False)
    phone_number = Column(String(20), nullable=False)
    blood_type = Column(String(10), nullable=True)
    known_allergies = Column(JSONB, default=list) 
    chronic_conditions = Column(JSONB, default=list)
    is_active = Column(Boolean, default=True)

    # Note: If you haven't created the consultation.py or medication.py files yet,
    # leave these commented out for now to prevent another ImportError!
    consultations = relationship("Consultation", back_populates="patient")
    medications = relationship("Medication", back_populates="patient")
    # Inside app/models/patient.py
    lab_requests = relationship("LabRequest", back_populates="patient", cascade="all, delete-orphan")