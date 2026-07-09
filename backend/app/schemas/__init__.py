from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.core.enums import DesignationTier

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Auth
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2)
    organization_name: str = Field(min_length=2)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(ORMModel):
    id: UUID
    email: str
    full_name: str
    role: str
    organization_id: UUID
    is_active: bool


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "hr_manager"
    password: str = Field(min_length=8)


# Organization
class OrganizationResponse(ORMModel):
    id: UUID
    name: str
    slug: str
    is_active: bool
    resend_from_email: str | None


class OrganizationUpdate(BaseModel):
    name: str | None = None
    resend_from_email: str | None = None


# Position
class PositionCreate(BaseModel):
    title: str = Field(min_length=2)
    job_description: str = Field(min_length=20)
    designation: DesignationTier
    location: str | None = None


class PositionUpdate(BaseModel):
    title: str | None = None
    job_description: str | None = None
    designation: str | None = None
    location: str | None = None
    status: str | None = None


class PositionResponse(ORMModel):
    id: UUID
    organization_id: UUID
    title: str
    job_description: str
    status: str
    designation: str | None
    location: str | None
    created_at: datetime


class ScoringCriteriaResponse(ORMModel):
    id: UUID
    position_id: UUID
    jd_analysis: dict
    criteria: list
    total_points: int
    generated_by_model: str | None


# Candidate
class CandidateResponse(ORMModel):
    id: UUID
    organization_id: UUID
    position_id: UUID
    full_name: str | None
    email: str | None
    phone: str | None
    location: str | None
    designation: str | None
    pipeline_status: str
    created_at: datetime


class CandidateUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    pipeline_status: str | None = None


class BulkCandidateAction(BaseModel):
    candidate_ids: list[UUID]
    action: str


# Resume
class ResumeResponse(ORMModel):
    id: UUID
    candidate_id: UUID
    original_filename: str
    file_size_bytes: int
    storage_key: str
    created_at: datetime


# Screening
class ScreeningResultResponse(ORMModel):
    id: UUID
    candidate_id: UUID
    position_id: UUID
    total_score: int
    breakdown: list
    decision: str
    summary: str
    reason: str
    reviewed_by_openai: bool
    created_at: datetime


class ScreeningStartRequest(BaseModel):
    position_id: UUID
    resume_ids: list[UUID] | None = None


class CandidateWithScreening(CandidateResponse):
    screening_result: ScreeningResultResponse | None = None
    resume: ResumeResponse | None = None


# Interview
class InterviewBatchCreate(BaseModel):
    position_id: UUID
    name: str
    scheduled_at: datetime | None = None
    location: str | None = None
    notes: str | None = None
    candidate_ids: list[UUID]
    panelist_ids: list[UUID]


class InterviewBatchUpdate(BaseModel):
    name: str | None = None
    scheduled_at: datetime | None = None
    location: str | None = None
    notes: str | None = None
    candidate_order: list[UUID] | None = None
    panelist_ids: list[UUID] | None = None


class InterviewBatchResponse(ORMModel):
    id: UUID
    organization_id: UUID
    position_id: UUID
    name: str
    scheduled_at: datetime | None
    location: str | None
    notes: str | None
    candidate_order: list
    created_at: datetime


class EvaluationSubmit(BaseModel):
    criteria_scores: list[dict] = Field(min_length=7, max_length=7)
    compliance_checks: dict
    strengths: str | None = None
    weaknesses: str | None = None
    recommendation: str
    notes: str | None = None


class EvaluationResponse(ORMModel):
    id: UUID
    batch_id: UUID
    candidate_id: UUID
    panelist_id: UUID
    criteria_scores: list
    compliance_checks: dict
    strengths: str | None
    weaknesses: str | None
    recommendation: str
    overall_score: int | None
    notes: str | None
    created_at: datetime


# Offer
class OfferCreate(BaseModel):
    candidate_id: UUID
    amount: int = Field(gt=0)
    currency: str = "PKR"
    offer_date: datetime
    notes: str | None = None


class OfferUpdate(BaseModel):
    amount: int | None = None
    status: str | None = None
    joining_date: datetime | None = None
    notes: str | None = None


class OfferResponse(ORMModel):
    id: UUID
    candidate_id: UUID
    amount: int
    currency: str
    offer_date: datetime
    joining_date: datetime | None
    status: str
    notes: str | None
    status_history: list
    created_at: datetime


# Email
class SendEmailRequest(BaseModel):
    candidate_ids: list[UUID]
    template_type: str
    custom_subject: str | None = None


class EmailLogResponse(ORMModel):
    id: UUID
    template_type: str
    recipient_email: str
    subject: str
    status: str
    created_at: datetime


# Billing
class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class SubscriptionResponse(ORMModel):
    plan: str
    status: str
    resumes_used_this_month: int
    usage_period_start: datetime | None


# Jobs
class JobResponse(ORMModel):
    id: UUID
    job_type: str
    status: str
    progress: int
    total: int
    payload: dict
    result: dict
    error: str | None
    created_at: datetime


# Admin
class AdminOrgResponse(OrganizationResponse):
    user_count: int = 0
    subscription_plan: str | None = None
    resumes_used: int = 0


class AuditLogResponse(ORMModel):
    id: UUID
    action: str
    entity_type: str
    entity_id: str | None
    details: dict
    created_at: datetime
    user_id: UUID | None


# Dashboard
class DashboardStats(BaseModel):
    open_positions: int
    total_candidates: int
    shortlisted: int
    rejected: int
    in_interview: int
    offers_pending: int
