from datetime import date, datetime, timezone
from pathlib import Path
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from .database import Base, engine, get_db, SessionLocal
from .models import Certificate, GenerationJob
from .schemas import CertificateRequest, JobCreatedResponse, JobStatusResponse, CertificateResponse
from .certificate_service import process_certificate

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Bulk Certificate Generator API",
    version="1.0.0",
    description="Generate certificates in bulk and track each certificate independently.",
)


def run_job(job_id: int, certificate_ids: list[int]) -> None:
    db = SessionLocal()
    try:
        job = db.get(GenerationJob, job_id)
        if not job:
            return
        job.status = "PROCESSING"
        db.commit()

        for cert_id in certificate_ids:
            process_certificate(db, cert_id)
            db.refresh(job)
            job.successful = sum(c.status == "SUCCESS" for c in job.certificates)
            job.failed = sum(c.status == "FAILED" for c in job.certificates)
            pending = job.total - job.successful - job.failed
            job.status = "COMPLETED" if pending == 0 else "PROCESSING"
            if pending == 0:
                job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/jobs", response_model=JobCreatedResponse, status_code=202)
def create_job(
    request: CertificateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if not request.course_name.strip():
        raise HTTPException(status_code=400, detail="course_name is required")
    if not request.recipients:
        raise HTTPException(status_code=400, detail="At least one recipient is required")
    if len(request.recipients) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 recipients per job")

    certificate_date = request.certificate_date or date.today()
    job = GenerationJob(total=len(request.recipients), status="PENDING")
    db.add(job)
    db.flush()

    certificate_ids = []
    for recipient in request.recipients:
        cert = Certificate(
            job_id=job.id,
            recipient_name=recipient.name,
            recipient_email=recipient.email,
            course_name=request.course_name.strip(),
            certificate_date=certificate_date.isoformat(),
            status="PENDING",
        )
        db.add(cert)
        db.flush()
        certificate_ids.append(cert.id)

    db.commit()
    background_tasks.add_task(run_job, job.id, certificate_ids)
    return JobCreatedResponse(job_id=job.id, status=job.status, total=job.total)


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    pending = job.total - job.successful - job.failed
    certificates = []
    for cert in job.certificates:
        certificates.append(
            CertificateResponse(
                certificate_id=cert.id,
                recipient_name=cert.recipient_name,
                recipient_email=cert.recipient_email,
                status=cert.status,
                download_url=(f"/api/certificates/{cert.id}/download" if cert.status == "SUCCESS" else None),
                error_message=cert.error_message,
            )
        )

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        total=job.total,
        successful=job.successful,
        failed=job.failed,
        pending=pending,
        certificates=certificates,
    )


@app.get("/api/certificates/{certificate_id}", response_model=CertificateResponse)
def get_certificate(certificate_id: int, db: Session = Depends(get_db)):
    cert = db.get(Certificate, certificate_id)
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return CertificateResponse(
        certificate_id=cert.id,
        recipient_name=cert.recipient_name,
        recipient_email=cert.recipient_email,
        status=cert.status,
        download_url=(f"/api/certificates/{cert.id}/download" if cert.status == "SUCCESS" else None),
        error_message=cert.error_message,
    )


@app.get("/api/certificates/{certificate_id}/download")
def download_certificate(certificate_id: int, db: Session = Depends(get_db)):
    cert = db.get(Certificate, certificate_id)
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if cert.status != "SUCCESS" or not cert.file_path:
        raise HTTPException(status_code=409, detail="Certificate is not available for download")

    path = Path(cert.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Generated certificate file not found")
    return FileResponse(path, media_type="application/pdf", filename=path.name)
