from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db.base import Base
from datetime import datetime

class Calendar(Base):
    __tablename__ = "calendars"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), default="Default")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    working_hours: Mapped[str] = mapped_column(Text, default="{}")  # {"mon":[["09:00","17:00"]],...}
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class AvailabilityRule(Base):
    __tablename__ = "availability_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calendar_id: Mapped[int] = mapped_column(ForeignKey("calendars.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)  # 0=mon
    start_time: Mapped[str] = mapped_column(String(8))  # HH:MM
    end_time: Mapped[str] = mapped_column(String(8))
    slot_minutes: Mapped[int] = mapped_column(Integer, default=30)
    appointment_type_id: Mapped[int | None] = mapped_column(ForeignKey("appointment_types.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class BlockedSlot(Base):
    __tablename__ = "blocked_slots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calendar_id: Mapped[int] = mapped_column(ForeignKey("calendars.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(255), default="")

class Leave(Base):
    __tablename__ = "leaves"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(255), default="leave")

class AppointmentType(Base):
    __tablename__ = "appointment_types"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    modes: Mapped[str] = mapped_column(Text, default='["in_person","video"]')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    calendar_id: Mapped[int | None] = mapped_column(ForeignKey("calendars.id"), nullable=True)
    appointment_type_id: Mapped[int | None] = mapped_column(ForeignKey("appointment_types.id"), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40), default="requested", index=True)
    mode: Mapped[str] = mapped_column(String(32), default="in_person")
    reason: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    external_appointment_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    integration_status: Mapped[str] = mapped_column(String(40), default="pending", index=True)  # pending|synced|verification_pending|failed|reconciliation_required|unknown_outcome
    conversation_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # Concurrency: uq_doctor_slot blocks exact-start duplicates at the DB level.
    # Overlapping ranges (10:00-10:30 vs 10:15-10:45) are additionally blocked by
    # Postgres exclusion constraint excl_doctor_no_overlap (see app/db/exclusion.py,
    # created idempotently on boot for postgresql/Neon, skipped on SQLite).
    __table_args__ = (UniqueConstraint("doctor_id", "starts_at", name="uq_doctor_slot"),)

class AppointmentHistory(Base):
    __tablename__ = "appointment_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str] = mapped_column(String(40), default="")
    to_status: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(64), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    correlation_id: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
