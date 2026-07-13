# Vaultly Architecture

Approved 2026-07-12. Changes to load-bearing decisions require a new ADR in `docs/adr/`.

## System overview

```
Browser ── Next.js 15 (App Router, TS) ── FastAPI /api/v1 ── PostgreSQL 16 (+FTS, pgvector)
                │                              │  │
                └── presigned upload ──► S3 / MinIO  Redis 7 ──► Celery workers + beat
                                                              (OCR pipeline, reminders, email)
```

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 15, App Router, TypeScript strict, Tailwind v4 | SSR dashboard, server components for a document-heavy UI; Ledger design tokens live in `apps/web/app/globals.css` |
| API | FastAPI + Pydantic v2 + SQLAlchemy 2 (async) + Alembic | Async-native for I/O-heavy workloads; OpenAPI contract for free → satisfies "API-first" |
| Contract | OpenAPI → `packages/shared-types` (openapi-typescript) | Frontend and backend cannot drift; regenerate with `make types` |
| Database | PostgreSQL 16 | Single source of truth; `tsvector` FTS meets the <300ms search target at V1 scale; pgvector adds semantic search later without Elasticsearch |
| Jobs | Celery + Redis broker, Celery beat | OCR pipeline and daily reminder scan; `acks_late` + retries + DLQ path for the 99% reminder-delivery target |
| Files | S3 (prod) / MinIO (local), presigned direct uploads | The <2s upload target rules out proxying bytes through the API |
| Auth | Self-hosted JWT: short-lived access + rotating refresh (httpOnly cookies), argon2 | A security-branded vault should own its auth path; audit logging starts here |
| Email | Provider-agnostic interface; Mailpit local, SES/Resend prod | Deliverability target needs retries + idempotency, not a specific vendor |
| OCR | `OcrProvider` interface; Tesseract local, AWS Textract prod | 95% accuracy on receipts/medical bills needs a cloud engine; interface keeps us portable |
| AI | Claude API (extraction, categorization, assistant) | Hybrid search: Postgres FTS for keywords + pgvector embeddings for semantic queries |

## Decisions log (approved with the architecture)

1. **Gmail sync is V2**, despite appearing in the PRD Day-1 journey — it's not in the V1 scope checklist and Google's restricted-scope OAuth verification takes months. V1 onboarding is manual upload + drag-and-drop (+ email-in address, per design screen 2b).
2. **Server-side envelope encryption, not E2E.** Per-document data keys wrapped by a KMS master key. True E2E would make OCR, AI search, and reminders impossible server-side. "Security above everything" is delivered via encryption at rest + TLS + strict tenant isolation + comprehensive audit logging.
3. **Tenancy: the unit of ownership is a *vault*,** with `user ↔ vault` memberships carrying roles (Owner/Admin/Member/Emergency-only, matching design screen 2i). A personal account is a vault with one member; Family plan = more members. This avoids the expensive user→family migration later.
4. **Emergency access** = owner-curated binder exposed via signed, time-limited, revocable tokens (QR), PIN-protected, every scan audit-logged + owner notified (design screen 2h).
5. **Billing (Stripe) is milestone M9**, but tier quotas (storage/docs/OCR counts) are enforced from the first upload endpoint so tiers are just limit changes.
6. **Medical data:** we assume consumer-directed storage (not HIPAA-covered), but treat it at HIPAA-adjacent rigor: encrypted, audited, access-controlled. Legal review before launch.

## Cross-cutting foundations (implemented)

- **Versioning:** everything under `/api/v1`; OpenAPI + docs served under the prefix.
- **Errors:** RFC 7807 `problem+json` everywhere (`app/core/errors.py`); domain code raises `AppError` subclasses; unhandled exceptions become sanitized 500s and are logged with stack traces.
- **Logging:** `structlog`, JSON in production, pretty in dev; `X-Request-ID` generated/propagated per request and bound to every log line (`app/core/logging.py`).
- **Health:** `/healthz` (liveness) and `/readyz` (checks Postgres + Redis concurrently, 2s timeout, 503 when degraded).
- **Audit:** append-only `audit_log` table from migration 0001.
- **Feature flags:** DB-backed (`feature_flags` table, `app/core/feature_flags.py`); unknown flags default off.
- **Config:** pydantic-settings only — zero hardcoded secrets; gitleaks in pre-commit and CI.
- **Testing:** pytest (+80% coverage gate) / vitest; CI runs lint, format, typecheck, tests, build, secret scan, compose validation.

## Design system

The UI implements the **Ledger** design system exactly as specified in
[design/handoff-v1/README.md](design/handoff-v1/README.md) — colors, IBM Plex Sans/Mono typography
(Mono for ALL numbers/dates/amounts/codes), spacing, radii are final. Tokens are encoded once in
`apps/web/app/globals.css` (Tailwind `@theme`); components must use tokens, never raw hex.
Icons: Lucide, 1.5px stroke. Approved screens: 1a (dashboard) and 2a–2k.
