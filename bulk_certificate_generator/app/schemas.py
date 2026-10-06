from datetime import date
from pydantic import BaseModel, Field


class RecipientRequest(BaseModel):
    name: str = Field(default="", description="Recipient's full name")
    email: str = Field(default="", description="Recipient email")


class CertificateRequest(BaseModel):
    course_name: str = Field(default="", description="Event or course name")
    certificate_date: date | None = Field(default=None)
    recipients: list[RecipientRequest] = Field(default_factory=list)


class JobCreatedResponse(BaseModel):
    job_id: int
    status: str
    total: int


class CertificateResponse(BaseModel):
    certificate_id: int
    recipient_name: str
    recipient_email: str
    status: str
    download_url: str | None = None
    error_message: str | None = None


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    total: int
    successful: int
    failed: int
    pending: int
    certificates: list[CertificateResponse]
