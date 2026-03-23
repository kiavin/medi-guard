import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Numeric, Date, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

# ==========================================
# 1. AUDIT MIXIN (Applied to all tables)
# ==========================================
class AuditMixin:
    """Provides common columns for all tables including soft deletes."""
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

# ==========================================
# 2. USERS TABLE
# ==========================================
class User(Base, AuditMixin):
    __tablename__ = "users"

    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String(50), nullable=False) # e.g., clinician, admin
    status = Column(Integer, default=1) # 1 = Active, 0 = Inactive
    
    # Relationships
    consultations = relationship("Consultation", back_populates="clinician")
    prescriptions = relationship("Medication", back_populates="clinician")

# ==========================================
# 3. PATIENTS TABLE
# ==========================================
class Patient(Base, AuditMixin):
    __tablename__ = "patients"

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(20), nullable=False)
    national_id = Column(String(50), unique=True, index=True, nullable=False)
    phone_number = Column(String(20), nullable=False)
    blood_type = Column(String(10), nullable=True)
    known_allergies = Column(JSONB, default=list) # Native Postgres JSONB
    chronic_conditions = Column(JSONB, default=list)

    # Relationships
    consultations = relationship("Consultation", back_populates="patient")
    medications = relationship("Medication", back_populates="patient")

# ==========================================
# 4. CONSULTATIONS TABLE
# ==========================================
class Consultation(Base, AuditMixin):
    __tablename__ = "consultations"

    patient_id = Column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    clinician_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    
    chief_complaint = Column(Text, nullable=False)
    clinical_notes = Column(Text, nullable=True)
    final_diagnosis = Column(String(255), nullable=True)
    treatment_plan = Column(Text, nullable=True)
    
    # Vitals
    bp_systolic = Column(Integer, nullable=True)
    bp_diastolic = Column(Integer, nullable=True)
    heart_rate = Column(Integer, nullable=True)
    temperature = Column(Numeric(4, 1), nullable=True)
    
    consultation_date = Column(DateTime, default=datetime.utcnow)
    follow_up_date = Column(Date, nullable=True)
    status = Column(String(20), default="open")

    # Relationships
    patient = relationship("Patient", back_populates="consultations")
    clinician = relationship("User", back_populates="consultations")
    symptoms = relationship("Symptom", back_populates="consultation", cascade="all, delete")
    prediction = relationship("Prediction", back_populates="consultation", uselist=False, cascade="all, delete")
    medications = relationship("Medication", back_populates="consultation", cascade="all, delete")

# ==========================================
# 5. SYMPTOMS TABLE
# ==========================================
class Symptom(Base, AuditMixin):
    __tablename__ = "symptoms"

    consultation_id = Column(String(36), ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False)
    symptom_name = Column(String(200), nullable=False)
    snomed_code = Column(String(20), nullable=True)
    severity = Column(String(20), nullable=False)
    duration_days = Column(Integer, nullable=True)
    is_free_text = Column(Boolean, default=False)

    consultation = relationship("Consultation", back_populates="symptoms")

# ==========================================
# 6. PREDICTIONS TABLE
# ==========================================
class Prediction(Base, AuditMixin):
    __tablename__ = "predictions"

    consultation_id = Column(String(36), ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False, unique=True)
    primary_disease = Column(String(255), nullable=False)
    primary_confidence = Column(Numeric(5, 4), nullable=False)
    differentials = Column(JSONB, nullable=True) 
    recommended_tests = Column(JSONB, nullable=True)
    model_used = Column(String(100), nullable=False)
    raw_response = Column(JSONB, nullable=False)
    was_confirmed = Column(Boolean, nullable=True)

    consultation = relationship("Consultation", back_populates="prediction")

# ==========================================
# 7. MEDICATIONS TABLE
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

    consultation = relationship("Consultation", back_populates="medications")
    patient = relationship("Patient", back_populates="medications")
    clinician = relationship("User", back_populates="prescriptions")

# ==========================================
# 8. MEDICATION INTERACTIONS (Safety Rules)
# ==========================================
class MedicationInteraction(Base, AuditMixin):
    __tablename__ = "medication_interactions"

    drug_a = Column(String(200), nullable=False, index=True)
    drug_b = Column(String(200), nullable=False, index=True)
    severity = Column(String(50), nullable=False) # critical, high, moderate, low
    effect = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)
    source = Column(String(100), nullable=False)