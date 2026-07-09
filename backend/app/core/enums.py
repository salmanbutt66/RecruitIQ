from enum import StrEnum


class UserRole(StrEnum):
    PLATFORM_ADMIN = "platform_admin"
    ORG_ADMIN = "org_admin"
    HR_MANAGER = "hr_manager"
    PANELIST = "panelist"


class PositionStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class PipelineStatus(StrEnum):
    NEW = "new"
    SCREENING = "screening"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    INTERVIEW = "interview"
    OFFER = "offer"
    HIRED = "hired"
    WITHDRAWN = "withdrawn"


class ScreeningDecision(StrEnum):
    SHORTLIST = "shortlist"
    REJECT = "reject"


class OfferStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class SubscriptionPlan(StrEnum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class DesignationTier(StrEnum):
    DIRECTOR = "director"
    MANAGER = "manager"
    EXECUTIVE = "executive"
    INTERN_TRAINEE = "intern_trainee"

class JobType(StrEnum):
    GENERATE_CRITERIA = "generate_criteria"
    SCREEN_RESUMES = "screen_resumes"
    REJECTION_FEEDBACK = "rejection_feedback"
    SEND_EMAIL = "send_email"


class EmailTemplateType(StrEnum):
    INTERVIEW_INVITATION = "interview_invitation"
    REJECTION = "rejection"
    OFFER = "offer"


PLAN_LIMITS = {
    SubscriptionPlan.STARTER: {"resumes_per_month": 100, "users": 5, "organizations": 1},
    SubscriptionPlan.PROFESSIONAL: {
        "resumes_per_month": 500,
        "users": 10,
        "organizations": 2,
    },
    SubscriptionPlan.ENTERPRISE: {
        "resumes_per_month": 999999,
        "users": 999999,
        "organizations": 999999,
    },
}
