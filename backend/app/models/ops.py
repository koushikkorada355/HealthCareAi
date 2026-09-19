from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..db.base import Base
from datetime import datetime

class Questionnaire(Base):
    __tablename__ = "questionnaires"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    specialty_id: Mapped[int | None] = mapped_column(nullable=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"), nullable=True)
    appointment_type_id: Mapped[int | None] = mapped_column(nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="pre_visit")
    schema_json: Mapped[str] = mapped_column(Text, default="[]")  # list of {id,label,type,options,required}
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class QuestionnaireResponse(Base):
    __tablename__ = "questionnaire_responses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    questionnaire_id: Mapped[int] = mapped_column(ForeignKey("questionnaires.id"), index=True)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"), nullable=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    answers_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(32), default="assigned", index=True)  # assigned|in_progress|completed
    collected_via: Mapped[str] = mapped_column(String(32), default="web")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Workflow(Base):
    __tablename__ = "workflows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    trigger_event: Mapped[str] = mapped_column(String(128), index=True)
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), index=True)
    trigger_ref: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)  # running|completed|failed|scheduled|retried
    input_json: Mapped[str] = mapped_column(Text, default="{}")
    output_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    correlation_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(32), default="in_app")
    kind: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)  # queued|sent|failed
    ref_type: Mapped[str] = mapped_column(String(64), default="")
    ref_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class HealthcareConnection(Base):
    __tablename__ = "healthcare_connections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    vendor: Mapped[str] = mapped_column(String(64), default="mock")
    base_url: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)  # active|degraded|down|disabled
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ExternalIdMap(Base):
    __tablename__ = "external_id_maps"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)  # patient|doctor|appointment|facility
    internal_id: Mapped[str] = mapped_column(String(128), index=True)
    external_id: Mapped[str] = mapped_column(String(128), index=True)
    vendor: Mapped[str] = mapped_column(String(64), default="mock")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class IntegrationOperation(Base):
    __tablename__ = "integration_operations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)  # create|update|cancel|verify|lookup
    ref_type: Mapped[str] = mapped_column(String(32), default="appointment")
    ref_id: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="started", index=True)  # started|success|failed|timeout|unknown_outcome|rate_limited|auth_error
    request_json: Mapped[str] = mapped_column(Text, default="{}")
    response_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    idempotency_key: Mapped[str] = mapped_column(String(128), default="", index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class IntegrationVerification(Base):
    __tablename__ = "integration_verifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operation_id: Mapped[int] = mapped_column(ForeignKey("integration_operations.id"), index=True)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"), nullable=True)
    method: Mapped[str] = mapped_column(String(64), default="retrieve")
    result: Mapped[str] = mapped_column(String(32), default="pending", index=True)  # pending|matched|mismatched|not_found|error
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    correlation_id: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ReconciliationRecord(Base):
    __tablename__ = "reconciliation_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), index=True)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"), nullable=True)
    issue: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)  # open|resolved|escalated
    resolution: Mapped[str] = mapped_column(Text, default="")
    assignee: Mapped[str] = mapped_column(String(128), default="")
    correlation_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Review(Base):
    """Patient review of a doctor or hospital after a completed visit.

    One review per (appointment, target): a visit can carry both a doctor
    and a hospital review. Hospital Admin sees only their own hospital's
    rows; responses are the hospital's reply.
    """
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_type: Mapped[str] = mapped_column(String(16), index=True)  # doctor|hospital
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"), nullable=True, index=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), index=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer, default=5)  # 1..5
    title: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="approved", index=True)  # approved|hidden
    response_text: Mapped[str] = mapped_column(Text, default="")
    response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("appointment_id", "target_type", name="reviews_appt_target_key"),)
