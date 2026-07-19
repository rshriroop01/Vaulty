# Vaultly

Secure cloud platform that helps individuals and families organize every important document in one place — and reminds them before important dates. Think **Dropbox + Apple Health + TurboTax Document Vault + Gmail AI**, built for life's paperwork.

> **North star:** if it's an important life document, Vaultly should know where it is, when it expires, and who needs access to it.

- **PRD (source of truth):** [docs/PRD.md](docs/PRD.md)
- **Architecture & decisions:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Implementation roadmap:** [docs/ROADMAP.md](docs/ROADMAP.md)
- **Launch checklist:** [docs/LAUNCH.md](docs/LAUNCH.md)
- **UI design handoff (final, "Ledger" system):** [docs/design/handoff-v1/README.md](docs/design/handoff-v1/README.md)

## Features

### 📄 Document vault (M2–M3)
- Drag-and-drop upload (PDF/JPG/PNG/HEIC/WebP, 25 MB cap) via **presigned direct-to-S3** uploads — file bytes never proxy through the API, keeping uploads under the 2-second PRD target.
- **AI extraction pipeline** (Celery): every upload is read natively by Claude in a single structured-output call that does OCR + classification + field extraction at once. Vendor, dates, amounts, and up to six at-a-glance facts are captured; documents are auto-filed into six categories (Receipts, Warranties, Insurance, Medical, IDs & Legal, Home).
- Detection banners: a receipt with a warranty (or a policy with a renewal date) offers **"Create both"** — a tracked record plus an expiry reminder in one click.
- Free-tier quotas (100 MB / 25 documents / 5 extractions per month) enforced from the first upload; paid tiers are just limit changes.

### 🔍 Search (M4)
- Postgres full-text search with prefix matching and `ts_rank` over title, filename, and every extracted field, GIN-indexed, with an ILIKE net for mid-word fragments. Observed latency 5–50 ms — well under the 300 ms PRD target, and the latency is shown right in the query bar.
- **⌘K overlay** from anywhere with debounced live results, category filter chips with live counts, highlighted snippets, and relevance scores.

### 🤖 AI assistant (M8)
- Ask questions in plain language — *"Which warranties expire next month?"* — and get a **VAULTLY ANSWER** card with source citations and action buttons (create reminder / open document).
- Retrieval is strictly **vault-scoped** behind a `RetrievalProvider` interface (FTS today, pgvector-ready). A post-filter guardrail drops any citation the model emits that wasn't in the retrieved set — hallucinated or cross-tenant ids can never leave the service.
- Premium-gated per the PRD business model; free vaults get a clean upsell.

### ⏰ Reminders (M5)
- Doc-linked or standalone reminders with per-reminder lead times (default 30/7/1 days). An hourly Celery beat scan sends each (reminder, lead) **exactly once** — idempotent by unique constraint, retried at the task level, failures recorded.
- Provider-agnostic email (`EmailProvider`): Mailpit locally, SES/Resend in production. Delivery-rate stat tracks the 99% PRD target on the reminders page.

### 🏥 Domain modules (M6)
- **Insurance center:** policy cards derived automatically from extracted insurance documents — type badge, policy number, coverage lines, premium, renewal status.
- **Medical bills:** outstanding / claims-pending / paid-YTD stats and a claims table with click-to-cycle status persisted per document.
- **Receipt manager & warranty tracking:** category filters server-side and in the UI, with dashboard tiles deep-linking in.

### 👨‍👩‍👧 Family sharing (M7)
- Emailed invites (hashed single-use tokens, 7-day expiry) with role dropdowns — Owner / Admin / Member / Emergency-only — and a 6-seat cap on the Family plan.
- Per-member **category-access matrix** (full / view / none) enforced across list, search, download, edit, and delete. Multi-vault support with a sidebar switcher.

### 🆘 Emergency binder (M7)
- Owner-curated binder: emergency contacts, blood group, hospital, allergies, medications, delegates — plus a completeness checklist that auto-detects what's already in the vault.
- **Printable QR + family PIN** (argon2-hashed, revocable, shown once). Scanning opens a public page that unlocks with the PIN — no account needed in a crisis. Every scan and failed attempt is audit-logged and emailed to the owners.

### 💳 Billing & tiers (M9)
- Stripe subscriptions: Free / **Premium $8.99/mo** / **Family $14.99/mo** with checkout and customer-portal redirects. `Vault.plan` only ever changes from a **signature-verified webhook**; a `StripeEvent` ledger makes deliveries idempotent, and handler failures answer non-2xx so Stripe redelivers.
- Dunning: `past_due` keeps the plan through Stripe's retry window; cancellation downgrades to Free. Family-plan gating on invites with an in-context upsell.

### 🛡️ Hardening & operations (M10)
- **Rate limiting:** Redis-backed fixed-window limits on auth (10/min/IP), assistant (20/min/user), and public emergency endpoints (5/min), answering RFC 7807 `429` with `Retry-After`; fails open if Redis is down.
- **Sentry** behind an env var, structured `structlog` JSON logs, `X-Request-ID` on every request, append-only audit log.
- **Terraform** production baseline (`infra/terraform/`): VPC, RDS Postgres 16, ElastiCache Redis, S3 + SSE, ECS Fargate (web/api/worker/beat), ALB, SES, Secrets Manager — staging and prod environments, `terraform validate`-clean, no secret values in code.
- Backup/restore drill script + runbook, k6/httpx load-test scripts with PRD thresholds encoded (search p95 < 300 ms, upload < 2 s).

## Architecture at a glance

```
Browser ── Next.js 15 (App Router, TS) ── FastAPI /api/v1 ── PostgreSQL 16 (+FTS)
                │                              │  │
                └── presigned upload ──► S3 / MinIO  Redis 7 ──► Celery workers + beat
                                                     (extraction, reminders, email)
```

| Layer | Choice |
|---|---|
| Frontend | Next.js 15, TypeScript strict, Tailwind v4 — "Ledger" design tokens, IBM Plex Sans/Mono |
| API | FastAPI + Pydantic v2 + async SQLAlchemy 2 + Alembic |
| AI | Claude API (structured outputs) for extraction, categorization, and the assistant |
| Jobs | Celery + Redis broker, Celery beat |
| Files | S3 (prod) / MinIO (local), presigned direct uploads, SSE AES-256 at rest |
| Auth | Self-hosted JWT: short-lived access + rotating refresh in httpOnly cookies, argon2 |
| Billing | Stripe subscriptions, webhook-driven plan state |
| Email | Provider interface — Mailpit locally, SES/Resend in prod |

Tenancy: the unit of ownership is a **vault**; a personal account is a vault with one member, the Family plan is the same vault with up to six. Full rationale in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Setup (under 10 minutes)

**Prerequisites:** Docker Desktop, `make`. Python/Node are only needed for running tools natively.

```bash
git clone https://github.com/rshriroop01/Vaulty.git vaultly && cd vaultly
cp .env.example .env   # local defaults work as-is
make dev               # builds and starts everything
```

To use the AI features locally, set a valid `ANTHROPIC_API_KEY` in `.env`. Stripe keys (`STRIPE_*`) are optional — billing endpoints answer a clean 503 until configured.

| URL | What |
|---|---|
| http://localhost:3000 | Web app |
| http://localhost:8000/api/v1/docs | Interactive API docs (Swagger) |
| http://localhost:8000/healthz · /readyz | Liveness / readiness |
| http://localhost:8025 | Mailpit — every locally sent email lands here |
| http://localhost:9001 | MinIO console (user `vaultly` / `vaultly-local`) |

### Enable git hooks (once, before your first commit)

```bash
pip install pre-commit && make setup
```

## Everyday commands

```bash
make help        # list all targets
make test        # backend (pytest, ≥80% coverage gate) + frontend (vitest)
make lint        # ruff + eslint + prettier
make typecheck   # mypy --strict + tsc
make migrate m="add documents table"   # new Alembic migration (autogenerate)
make upgrade     # apply migrations
make types       # regenerate TS types from the API's OpenAPI contract
make db-shell    # psql into local Postgres
```

## Repository layout

```
apps/web/              Next.js 15 (App Router, TS, Tailwind v4 with Ledger design tokens)
apps/api/              FastAPI (async SQLAlchemy, Alembic, Celery worker + beat)
packages/shared-types/ TS types generated from the OpenAPI contract — never hand-edited
infra/docker/          Dockerfiles (compose file at repo root)
infra/terraform/       Production AWS baseline — modules + staging/prod envs
loadtest/              k6 + httpx load-test scripts (PRD latency thresholds encoded)
scripts/               Operational scripts (backup/restore drill)
docs/                  PRD, architecture, ADRs, roadmap, runbooks, launch checklist, design handoff
```

## Milestone status

| Milestone | Scope | Status |
|---|---|---|
| M0 | Engineering foundation (CI, flags, audit, tokens) | ✅ Shipped |
| M1 | Identity & vault shell | ✅ Shipped |
| M2 | Document upload & storage | ✅ Shipped |
| M3 | AI extraction pipeline | ✅ Shipped |
| M4 | Search | ✅ Shipped |
| M5 | Reminders | ✅ Shipped |
| M6 | Domain modules (insurance, medical, categories) | ✅ Shipped |
| M7 | Family sharing & emergency binder | ✅ Shipped |
| M8 | AI assistant | ✅ Shipped |
| M9 | Billing & tiers (Stripe) | ✅ Shipped |
| M10 | Hardening & launch | 🔧 In progress — rate limiting, Terraform, runbooks landed; launch checklist open |

Gmail sync, mobile apps, and further modules are V2/V3 — see the deferred list in [docs/ROADMAP.md](docs/ROADMAP.md).

## Conventions that keep us honest

- **API-first:** every endpoint lives under `/api/v1/`; the OpenAPI schema is the contract and frontend types are generated from it (`make types`).
- **Errors:** all API errors are RFC 7807 `problem+json`; raise `AppError` subclasses, never ad-hoc responses.
- **Logging:** structured via `structlog`; every request carries an `X-Request-ID`. No `print()`.
- **Secrets:** environment only (`app/core/config.py`); gitleaks blocks commits containing secrets.
- **Feature flags:** new functionality ships behind a flag (`app/core/feature_flags.py`).
- **Audit:** security-relevant actions write to `audit_log`.
- **Design:** UI work follows the Ledger tokens in `apps/web/app/globals.css` — colors/type/spacing are final per the design handoff; don't invent values.
- **Tests:** backend coverage gate is 80% (PRD requirement) and CI enforces lint, types, tests, build, and secret scanning on every PR.
