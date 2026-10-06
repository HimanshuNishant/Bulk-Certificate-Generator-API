# Bulk Certificate Generator Backend API

A small production-style FastAPI backend for bulk certificate generation. It accepts one job containing many recipients, validates each recipient independently, generates certificates in the background, tracks progress, and provides download endpoints.

## Technology

- FastAPI
- SQLite + SQLAlchemy (relational database)
- Pydantic
- ReportLab for PDF generation
- Pytest
- FastAPI BackgroundTasks for background processing

SQLite is used to keep local setup simple while still satisfying the relational database requirement. The database layer uses SQLAlchemy, so the application can later be moved to PostgreSQL with configuration changes.

## Project structure

```text
bulk_certificate_generator/
├── app/
│   ├── __init__.py
│   ├── certificate_service.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
├── tests/
│   └── test_api.py
├── output/
├── .gitignore
├── README.md
└── requirements.txt
```

## Setup

Python 3.11+ is recommended.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\\Scripts\\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run the API

```bash
uvicorn app.main:app --reload
```

Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Submit a bulk generation request

`POST /api/jobs`

Example:

```json
{
  "course_name": "Python Fundamentals",
  "certificate_date": "2026-10-06",
  "recipients": [
    {
      "name": "Alice Sharma",
      "email": "alice@example.com"
    },
    {
      "name": "Bob Kumar",
      "email": "bob@example.com"
    }
  ]
}
```

The API returns `202 Accepted` and a job ID. Generation is processed in the background so the client does not have to wait for every PDF to finish.

## Check progress

`GET /api/jobs/{job_id}`

Example response:

```json
{
  "job_id": 1,
  "status": "COMPLETED",
  "total": 2,
  "successful": 2,
  "failed": 0,
  "pending": 0,
  "certificates": [
    {
      "certificate_id": 1,
      "recipient_name": "Alice Sharma",
      "recipient_email": "alice@example.com",
      "status": "SUCCESS",
      "download_url": "/api/certificates/1/download",
      "error_message": null
    }
  ]
}
```

## Download a certificate

`GET /api/certificates/{certificate_id}/download`

The endpoint returns the generated PDF when the certificate has successfully completed.

## Failure handling

Recipient validation is intentionally performed per certificate rather than rejecting the complete bulk job. Therefore, an invalid email can result in one `FAILED` certificate while all other valid recipients continue processing.

For example:

```text
Recipient A -> SUCCESS
Recipient B -> FAILED (invalid email)
Recipient C -> SUCCESS
```

The job status exposes successful and failed counts and an error message for failed certificates.

## Design decisions

### Why FastAPI?
FastAPI provides typed request/response models, automatic validation, OpenAPI/Swagger documentation, and a simple structure suitable for a small backend service.

### Why SQLite?
The assignment requires a relational database. SQLite makes the project easy to run locally without requiring a separate database server. SQLAlchemy keeps the persistence layer portable to PostgreSQL later.

### Why background processing?
Bulk PDF generation can take longer as recipient count grows. The API creates the job and immediately returns the job ID with HTTP 202. Background processing then updates each certificate and the aggregate job status.

For a high-scale production system, a durable worker queue such as Celery/RQ with Redis or a managed queue would be preferable. FastAPI BackgroundTasks is intentionally used here to keep the assignment simple and easy to run.

### Why one certificate template?
The assignment asks for a single predefined certificate template. The ReportLab implementation provides one fixed professional certificate design and injects recipient-specific data into it.

## Testing

Run:

```bash
pytest -q
```

The tests cover:

- Creating a generation job
- Invalid request handling
- Certificate generation
- Job status/progress
- Individual certificate failure without stopping other certificates
- Retrieving/downloading generated certificates

## API summary

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/jobs` | Create bulk certificate generation job |
| GET | `/api/jobs/{job_id}` | Get job progress and result |
| GET | `/api/certificates/{certificate_id}` | Get certificate status/details |
| GET | `/api/certificates/{certificate_id}/download` | Download generated PDF |

## Interview talking points

1. The API accepts one request for many recipients instead of one request per certificate.
2. HTTP 202 is returned because generation is asynchronous/background work.
3. Each certificate has its own status so one failure does not stop other valid recipients.
4. The relational database stores both job-level and certificate-level state.
5. SQLAlchemy separates persistence from the API layer and makes migration to PostgreSQL easier.
6. ReportLab creates the predefined PDF template.
7. For a production-scale deployment, replace in-process background tasks with a durable worker queue and object storage for generated files.
