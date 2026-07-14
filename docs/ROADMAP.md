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

## M3 — AI extraction pipeline ✅ (shipped 2026-07-14) · *screen 2b (queue, chips, banner)*
- Celery pipeline: upload → queued → processing → extracted | failed, with retries
- Claude (Opus 4.8, structured outputs) reads PDFs/images natively — one call does
  OCR + classification + field extraction, replacing the planned Tesseract/Textract split
- Auto-categorization into the six vault categories, title rewrite, expiry-date capture
- Free-tier OCR quota enforced (5 extractions/month); no key or over quota → doc stays uploaded
- "Warranty detected → create warranty + reminder" suggestion banner (action activates at M5)
- Deferred: labeled accuracy corpus for the 95% PRD target → M10 hardening
- **Exit met:** dropped receipt auto-populated vendor/amount/dates/chips with no user input

## M4 — Search ✅ (shipped 2026-07-14) · *screen 2c*
- Postgres FTS with prefix matching + ts_rank over `search_text` (title + filename +
  extracted vendor/dates/amounts/fields), GIN-indexed; ILIKE net for mid-word fragments
- Latency measured server-side and shown in the query bar (observed: 5–50ms, well under
  the 300ms PRD target); category filter chips with live counts; highlighted snippets + scores
- ⌘K overlay from anywhere with debounced live results; ask bar opens it
- Deferred: pgvector semantic embeddings need an embedding provider (Voyage API key —
  Anthropic has no embeddings API) → folded into M8 with the AI assistant
- **Exit met:** "Samsung Washer" (and even a mid-word "Samsu", or the order number)
  finds the receipt instantly

## M5 — Reminders ✅ (shipped 2026-07-14) · *screen 2e*
- `reminders` (doc-linked or standalone) with per-reminder lead times (default 30/7/1d);
  hourly Celery beat scan sends the most imminent pending lead exactly once per
  (reminder, lead) via `reminder_sends` — idempotent by unique constraint, retries at
  the task level, failures recorded for the delivery metric
- `EmailProvider` interface: SMTP → Mailpit locally, SES/Resend in prod
- Delivery-rate stat (99% PRD target), needs-attention count feeding the sidebar badge,
  dashboard "Action needed" KPI, and the real 1a upcoming-deadlines list with date chips
- "Create both" on the extraction banner now creates the doc-linked reminder
- Reminders center per 2e: urgency groups, checkbox completes, source-doc links,
  Email/Push toggles (push = V3), lead-time chips, delivery-rate card
- **Exit met:** reminder → beat scan → email delivered to Mailpit, audit-logged,
  idempotent on rescan; delivery rate 100% (1/1)

## M6 — Domain modules ✅ (shipped 2026-07-14) · *screens 2f, 2g, 1a fully live*
- Insurance center (2f): policy cards derived from Claude-extracted insurance docs —
  type badge, policy #, coverage lines, premium, renewal status tag, add-policy slot
- Medical bills (2g): summary stats (outstanding / claims pending / paid YTD) + claims
  table with click-to-cycle status (outstanding → pending → paid) persisted via
  `documents.bill_status`; PATCH /documents/{id} also allows title/category fixes
  (search index rebuilt on edit)
- Receipt Manager + Warranty Tracking: category filter on the documents list
  (server param + UI chips) with dashboard category tiles deep-linking in
- Dashboard 1a fully live since M5 (KPIs, deadlines, categories, recent imports)
- **Exit met:** real policy + hospital-bill PDFs extracted into a working policy card
  and claims row; status cycled and persisted; all four PRD V1 modules usable

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
