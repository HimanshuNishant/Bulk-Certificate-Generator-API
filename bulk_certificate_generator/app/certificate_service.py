from pathlib import Path
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session
from .models import Certificate

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_recipient(name: str, email: str) -> str | None:
    name = name.strip()
    email = email.strip()
    if not name:
        return "Recipient name is required"
    if len(name) > 200:
        return "Recipient name is too long"
    if not email:
        return "Recipient email is required"
    if not EMAIL_RE.match(email):
        return "Invalid email address"
    return None


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return cleaned[:80] or "recipient"


def generate_certificate_pdf(cert: Certificate) -> Path:
    path = OUTPUT_DIR / f"certificate_{cert.id}_{safe_filename(cert.recipient_name)}.pdf"
    width, height = landscape(A4)
    pdf = canvas.Canvas(str(path), pagesize=(width, height))

    # Predefined single certificate design.
    pdf.setStrokeColor(colors.HexColor("#1F4E79"))
    pdf.setLineWidth(5)
    pdf.rect(28, 28, width - 56, height - 56)
    pdf.setStrokeColor(colors.HexColor("#D9B44A"))
    pdf.setLineWidth(2)
    pdf.rect(42, 42, width - 84, height - 84)

    pdf.setFillColor(colors.HexColor("#1F4E79"))
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawCentredString(width / 2, height - 105, "CERTIFICATE OF COMPLETION")

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica", 15)
    pdf.drawCentredString(width / 2, height - 150, "This certificate is proudly presented to")

    pdf.setFillColor(colors.HexColor("#1F4E79"))
    pdf.setFont("Helvetica-Bold", 30)
    pdf.drawCentredString(width / 2, height - 205, cert.recipient_name)

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica", 15)
    pdf.drawCentredString(width / 2, height - 250, "for successfully completing")

    pdf.setFillColor(colors.HexColor("#1F4E79"))
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawCentredString(width / 2, height - 290, cert.course_name)

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(width / 2, 95, f"Date: {cert.certificate_date}")
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.drawCentredString(width / 2, 72, f"Certificate ID: {cert.id}")

    pdf.save()
    return path


def process_certificate(db: Session, cert_id: int) -> None:
    cert = db.get(Certificate, cert_id)
    if not cert:
        return

    cert.status = "PROCESSING"
    db.commit()

    try:
        error = validate_recipient(cert.recipient_name, cert.recipient_email)
        if error:
            cert.status = "FAILED"
            cert.error_message = error
        else:
            path = generate_certificate_pdf(cert)
            cert.file_path = str(path)
            cert.status = "SUCCESS"
        db.commit()
    except Exception as exc:
        cert.status = "FAILED"
        cert.error_message = f"Certificate generation failed: {exc}"
        db.commit()
