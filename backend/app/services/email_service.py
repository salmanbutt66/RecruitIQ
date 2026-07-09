import uuid

import resend
from jinja2 import Template
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Candidate, EmailLog, Organization
from app.services.auth_service import create_audit_log

settings = get_settings()

INTERVIEW_TEMPLATE = Template("""
<p>Dear {{ candidate_name }},</p>
<p>You have been invited for an interview for the position of <strong>{{ position_title }}</strong>.</p>
<p><strong>Date:</strong> {{ scheduled_at }}<br>
<strong>Location:</strong> {{ location }}</p>
<p>{{ notes }}</p>
<p>Best regards,<br>{{ org_name }} HR Team</p>
""")

REJECTION_TEMPLATE = Template("""
<p>Dear {{ candidate_name }},</p>
<p>Thank you for your interest in the <strong>{{ position_title }}</strong> position at {{ org_name }}.</p>
<p>{{ feedback_paragraph }}</p>
<p>We wish you all the best in your career journey.</p>
<p>Warm regards,<br>{{ org_name }} HR Team</p>
""")

OFFER_TEMPLATE = Template("""
<p>Dear {{ candidate_name }},</p>
<p>We are pleased to offer you the position of <strong>{{ position_title }}</strong> at {{ org_name }}.</p>
<p><strong>Offer Amount:</strong> {{ amount }} {{ currency }}<br>
<strong>Offer Date:</strong> {{ offer_date }}</p>
<p>{{ notes }}</p>
<p>Please let us know your decision by clicking one of the buttons below:</p>
<p>
  <a href="{{ accept_url }}" style="background:#4f46e5;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;margin-right:12px;">Accept Offer</a>
  <a href="{{ reject_url }}" style="background:#ef4444;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;">Decline Offer</a>
</p>
<p>We look forward to hearing from you.</p>
<p>Best regards,<br>{{ org_name }} HR Team</p>
""")


class EmailService:
    def __init__(self) -> None:
        if settings.resend_api_key:
            resend.api_key = settings.resend_api_key

    async def send_email(
        self,
        db: AsyncSession,
        *,
        organization: Organization,
        candidate: Candidate,
        template_type: str,
        subject: str,
        html_body: str,
        user_id: uuid.UUID | None = None,
    ) -> EmailLog:
        from_email = organization.resend_from_email or settings.resend_from_email
        recipient = candidate.email
        if not recipient:
            raise ValueError("Candidate has no email address")

        message_id = None
        status = "sent"
        if settings.resend_api_key:
            try:
                response = resend.Emails.send(
                    {
                        "from": from_email,
                        "to": [recipient],
                        "subject": subject,
                        "html": html_body,
                    }
                )
                message_id = response.get("id") if isinstance(response, dict) else getattr(response, "id", None)
            except Exception as exc:
                status = "failed"
                raise exc
        else:
            status = "simulated"

        log = EmailLog(
            organization_id=organization.id,
            candidate_id=candidate.id,
            template_type=template_type,
            recipient_email=recipient,
            subject=subject,
            resend_message_id=message_id,
            status=status,
            body_preview=html_body[:500],
        )
        db.add(log)
        await create_audit_log(
            db,
            organization_id=organization.id,
            user_id=user_id,
            action="email_sent",
            entity_type="candidate",
            entity_id=str(candidate.id),
            details={"template": template_type, "recipient": recipient},
        )
        return log


email_service = EmailService()
