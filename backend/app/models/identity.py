from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, Date, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..db.base import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), index=True)  # platform_admin|hospital_admin|doctor|patient
    full_name: Mapped[str] = mapped_column(String(255), default="")
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id"), nullable=True, index=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"), nullable=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Hospital(Base):
    __tablename__ = "hospitals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)  # draft|submitted|under_review|approved|rejected|suspended|corrections_requested
    address: Mapped[str] = mapped_column(Text, default="")
    city: Mapped[str] = mapped_column(String(128), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    contact_email: Mapped[str] = mapped_column(String(255), default="")
    operating_hours: Mapped[str] = mapped_column(Text, default="{}")
    services: Mapped[str] = mapped_column(Text, default="[]")
    ehr_vendor: Mapped[str] = mapped_column(String(64), default="mock")
    ehr_config: Mapped[str] = mapped_column(Text, default="{}")
    review_notes: Mapped[str] = mapped_column(Text, default="")
    external_facility_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Specialty(Base):
    __tablename__ = "specialties"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Doctor(Base):
    __tablename__ = "doctors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    specialty_id: Mapped[int | None] = mapped_column(ForeignKey("specialties.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    photo_url: Mapped[str] = mapped_column(String(512), default="")
    qualifications: Mapped[str] = mapped_column(Text, default="")
    experience_years: Mapped[int] = mapped_column(Integer, default=0)
    languages: Mapped[str] = mapped_column(Text, default="[]")
    consultation_types: Mapped[str] = mapped_column(Text, default='["in_person"]')
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(32), default="invited", index=True)  # invited|active|inactive|suspended
    external_provider_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    rating: Mapped[float] = mapped_column(default=4.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True, default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    dob: Mapped[str] = mapped_column(String(32), default="")
    gender: Mapped[str] = mapped_column(String(32), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    external_patient_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    home_hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class UserContextPref(Base):
    __tablename__ = "user_context_prefs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, unique=True)
    prefs: Mapped[str] = mapped_column(Text, default="{}")  # JSON: comm channel, language, hospital, specialty prefs
    clinical_notes: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
