# Design Notes

## Request lifecycle

1. Client submits one bulk request.
2. API validates required job-level fields.
3. A `GenerationJob` row is created.
4. One `Certificate` row is created per recipient.
5. API returns HTTP 202 with `job_id`.
6. Background processing handles each certificate independently.
7. Each certificate is marked SUCCESS or FAILED.
8. Job counters are recalculated after each certificate.
9. Client polls the job endpoint and downloads successful PDFs.

## Failure isolation

The processing loop does not abort when an individual recipient is invalid. Each certificate has its own status and error message.

## Scaling path

For a production system:

```text
API -> PostgreSQL
    -> Redis/Queue -> Worker processes -> Object Storage
```

The client would continue polling the job endpoint, while generated PDFs would be stored in object storage rather than local disk.
