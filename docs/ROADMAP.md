# Vaultly — Technical Implementation Roadmap

Breaks the [PRD](PRD.md) V1 scope into deployable milestones. Every milestone ships behind a
feature flag, deploys independently, and maps to approved design screens
([handoff](design/handoff-v1/README.md)). Order is chosen so each milestone unblocks the next
and risk (OCR accuracy, search latency, reminder delivery) is retired early.

## M0 — Engineering foundation ✅ (this repo)
Monorepo, Docker Compose one-command stack, CI, pre-commit, logging, error handling, API
versioning, health endpoints, audit log, feature flags, design tokens, docs.

## M1 — Identity & vault shell ✅ (shipped 2026-07-13) · *screens 2a, 1a, sidebar*
- `users`, `vaults`, `vault_memberships` (roles: Owner/Admin/Member/Emergency-only), sessions
- Sign up / sign in (argon2, JWT access + rotating refresh in httpOnly cookies), 2FA scaffold
- App shell: Ledger sidebar, empty dashboard, auth screens pixel-perfect per 2a
- Audit: `auth.signup`, `auth.login`, `auth.failed_login`
- **Exit:** a user can register, sign in, and see their empty vault; ≥80% coverage holds

## M2 — Document upload & storage ✅ (shipped 2026-07-13) · *screen 2b (upload half)*
- `documents` table (vault-scoped), presigned direct-to-S3 upload, download, delete
- At-rest encryption via storage-layer SSE (S3 default AES-256; MinIO local). App-managed
  per-document envelope encryption moved to M10 hardening — direct presigned uploads make
  app-level crypto a client-side concern that needs its own design pass
- Tier quota enforcement (100MB / 25 docs free) — billing-ready without billing
- **Exit met:** upload→list→download→delete round-trip verified through the UI

## M3 — OCR & AI extraction pipeline · *screen 2b (queue, field chips, suggestion banner)*
- Celery pipeline: upload event → OCR (`OcrProvider`: Tesseract local / Textract prod) →
  Claude extraction (type, vendor, dates, amounts) → status updates (Queued / OCR % / Extracted)
- "Warranty detected → create warranty + reminder" suggestion flow
- OCR accuracy harness with a labeled receipt/policy corpus — tracks the 95% PRD target
- **Exit:** dropped receipt auto-populates extracted fields without user input

## M4 — Search · *screen 2c*
- Postgres FTS (tsvector over title/extracted text/metadata) + filters (category/date/owner)
- p95 latency instrumented; target <300ms (PRD)
- pgvector embeddings + hybrid ranking (semantic half of "AI Search")
- ⌘K overlay from anywhere (3-click rule)
- **Exit:** "Samsung Washer" finds the warranty PDF instantly (PRD Month-6 journey)

## M5 — Reminders · *screen 2e*
- `reminders` (doc-linked or standalone), lead times 30/7/1d, beat scan → email via
  `EmailProvider` (Mailpit local / SES prod), retries + dead-letter, idempotent sends
- Delivery-rate metric (99% PRD target); Email/Push channel toggles (push = V3)
- **Exit:** expiring warranty produces a delivered, audit-logged email on schedule

## M6 — Domain modules · *screens 2f, 2g, and 1a dashboard live*
- Receipts, Warranties, Insurance Center (policy cards), Medical Bills (status tracking)
  as typed views + linked records over the document core
- Dashboard 1a fully wired: KPI cards, upcoming deadlines, category grid, recent imports
- **Exit:** PRD V1 checklist items Receipt Manager / Warranty / Insurance / Medical all usable

## M7 — Family sharing & emergency binder · *screens 2i, 2h*
- Multi-member vaults, invites, role dropdowns, category-access matrix (full/view/none)
- Emergency binder: contents checklist, QR with signed time-limited revocable token + PIN,
  every scan notifies owner + writes audit log; delegate list + access log
- **Exit:** PRD Emergency journey works end-to-end without account credentials

## M8 — AI assistant · *screen 2c answer card*
- Claude-backed Q&A over the user's corpus ("VAULTLY ANSWER" card, source citations,
  action buttons that create reminders / open docs)
- Guardrails: vault-scoped retrieval only; answers cite sources; no cross-tenant leakage
- **Exit:** "Which warranties expire next month?" answers correctly with sources

## M9 — Billing & tiers
- Stripe subscriptions (Free/Premium/Family), quota upgrades, dunning, customer portal
- **Exit:** a family can pay $14.99/mo and add 6 members

## M10 — Hardening & launch
- Terraform for production infra, staging environment, backups + restore drill,
  Sentry + metrics dashboards, rate limiting, pen-test pass, legal review of medical data posture
- Load test: search p95 <300ms, upload <2s at 10k-user scale (PRD Year-1 target)
- **Exit:** production launch checklist green

**Deferred (V2/V3 per PRD + decisions log):** Gmail sync (M-V2, needs Google restricted-scope
verification lead time — start the application during M5), mobile apps (2j pattern exists),
vehicle/tax/estate modules, wallet integrations, voice, calendar sync.
