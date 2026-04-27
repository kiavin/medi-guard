from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base
from app.models.base import AuditMixin

class User(Base, AuditMixin):
    __tablename__ = "users"

    # --- NEW FIELDS ---
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="active") # "active", "suspended", "disabled"
    
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String(50), nullable=False, default="clinician")

    # Security Fields (Backend Logic)
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    # ==========================================
    # RELATIONSHIPS
    # ==========================================
    consultations = relationship("Consultation", back_populates="clinician")
    prescriptions = relationship("Medication", back_populates="clinician")
    
    labs_ordered = relationship(
        "LabRequest",
        foreign_keys="LabRequest.ordered_by_id",
        back_populates="ordered_by",
    )
    labs_handled = relationship(
        "LabRequest",
        foreign_keys="LabRequest.handled_by_id",
        back_populates="handled_by",
    )

class TokenBlocklist(Base):
    __tablename__ = "token_blocklist"

    token = Column(String, primary_key=True, index=True)
    blacklisted_at = Column(DateTime, default=datetime.utcnow)