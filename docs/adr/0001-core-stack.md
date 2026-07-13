# ADR 0001 — Core stack and foundational decisions

- **Status:** Accepted (2026-07-12)
- **Context:** Founding-phase choice of stack and the decisions the PRD left open.
- **Decision:** Monorepo; Next.js 15 + FastAPI + PostgreSQL 16 + Redis 7 + Celery; S3/MinIO object
  storage with presigned uploads; self-hosted JWT auth; server-side envelope encryption (not E2E);
  vault-centric tenancy; Gmail sync deferred to V2; OCR and email behind provider interfaces
  (Tesseract/Textract, Mailpit/SES); Claude API for AI features; Stripe deferred to M9.
- **Rationale and details:** see [../ARCHITECTURE.md](../ARCHITECTURE.md) — kept in one place
  deliberately; future ADRs record *changes* to it.
- **Consequences:** one repo to operate; contract-generated types prevent drift; provider
  interfaces cost a little indirection now to avoid vendor lock-in on the two riskiest
  dependencies (OCR accuracy, email deliverability).
