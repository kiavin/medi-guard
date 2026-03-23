from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base
from app.models.base import AuditMixin


class User(Base, AuditMixin):
    __tablename__ = "users"

    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String(50), nullable=False, default="clinician")

    # Security Fields
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    # ==========================================
    # MISSING RELATIONSHIPS ADDED HERE
    # ==========================================
    consultations = relationship("Consultation", back_populates="clinician")
    prescriptions = relationship("Medication", back_populates="clinician")


class TokenBlocklist(Base):
    __tablename__ = "token_blocklist"

    token = Column(String, primary_key=True, index=True)
    blacklisted_at = Column(DateTime, default=datetime.utcnow)

    # Inside app/models/user.py
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
