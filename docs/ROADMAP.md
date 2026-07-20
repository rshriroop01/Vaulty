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

## M7 — Family sharing & emergency binder ✅ (shipped 2026-07-15) · *screens 2i, 2h*
- Emailed invites (hashed tokens, 7-day expiry, single-use) → accept page → membership;
  role dropdowns (admin/member/emergency-only), owner-only role management, 6-seat cap
- Category-access matrix (full/view/none) per member, enforced across documents list,
  search, download, edit, and delete; emergency-only members see nothing by default
- Multi-vault support: X-Vault-ID header / vaultly_vault cookie selection + sidebar
  vault switcher; sign-in/up honor ?next= for invite deep links
- Emergency binder (2h): contacts/medical/delegates editor, checklist derived from
  binder + vault contents, QR card (client-generated, printable, shown once), revocable
  argon2-PIN tokens, public /e/{token} page; every scan or failed PIN is audit-logged
  and emailed to owners
- **Exit met:** full journey verified live — invite email → spouse signup → member of
  family vault; QR + PIN → public binder with contacts, blood group, and the real ACME
  policy, zero credentials; owner notified, access log populated

## M8 — AI assistant ✅ (shipped 2026-07-19) · *screen 2c answer card*
- Claude-backed Q&A over the user's corpus behind a `RetrievalProvider` interface —
  `FtsRetrieval` reuses the M4 search service, always filtered by vault id + the M7
  visible-categories matrix; pgvector semantic retrieval stays deferred until an
  embedding provider key exists (Voyage — Anthropic has no embeddings API), same call
  made in M4
- `ClaudeAssistant` mirrors the M3 extractor: sync class, `messages.parse` structured
  output (`AssistantAnswer`: answer, citations, suggested actions), run off the event
  loop via `anyio.to_thread.run_sync`
- Guardrail post-filter (pure, unit-tested): any citation or suggested-action document
  id not in the retrieved set is dropped before the response leaves the service —
  the model's own ids are never trusted, closing off both hallucination and
  cross-tenant leakage even if retrieval were ever misconfigured
- Gated: `assistant` feature flag (seeded on via migration 0009), then Premium/Family
  plan (free vault → RFC 7807 403 `.../plan-upgrade-required` for the frontend upsell
  card), then a configured Anthropic key (missing → 503). `assistant.ask` audit-logged
  with question length + retrieved count, never the question text
- Search page (2c): navy "VAULTLY ANSWER" card fires alongside search — answer,
  source-count, citation chips, "Create reminder" (posts to the existing reminders
  API) / "Open document" actions; plain pending state, no card at all when the flag
  is off or the key is missing; ⌘K's ask bar already routed into `/search?q=`, so it
  reaches the same answer card with no changes needed
- **Exit met:** premium vault + a receipt/warranty in the corpus → asking about it
  returns a cited, source-linked answer; a free vault gets the upgrade card instead;
  a fake model asked to cite another vault's document id has that id stripped by the
  guardrail post-filter (verified in tests, not just retrieval scoping)

## M9 — Billing & tiers ✅ (shipped 2026-07-20)
- Stripe subscriptions behind a `BillingProvider` Protocol (mirrors M8's `AssistantProvider`):
  `StripeBilling` wraps `checkout.Session`/`billing_portal.Session`/`Webhook.construct_event`,
  injected via `get_billing()` so tests never touch the network; `Vault.plan` is written only
  from a verified webhook event, never from client input — checkout/portal endpoints just
  redirect to Stripe-hosted pages
- `billing_customers` (vault ↔ Stripe customer/subscription linkage) and `stripe_events`
  (webhook idempotency ledger — event id inserted before processing; a conflict short-circuits
  to 200 without reprocessing) added in migration 0010; quotas (`app/core/quotas.py`) already
  reacted to `Vault.plan` since M1–M6, so this milestone is entirely about moving that one field
- `POST /billing/checkout` (owner-only, else 403) and `/billing/portal` create/reuse the
  `BillingCustomer` row and redirect; `GET /billing/summary` reports plan, subscription status,
  member count, and usage vs. plan limits. All three gate on configured Stripe keys the same
  way the assistant gates on an Anthropic key — empty `STRIPE_SECRET_KEY` → RFC 7807 503, not a 500
- `POST /billing/webhook` is unauthenticated by design (Stripe is the caller, authenticated via
  the signed payload, not a session cookie) and never 500s Stripe: `checkout.session.completed`
  flips the plan (price id carried in session metadata, mapped via a pure `price_for_plan`/
  `plan_for_price` helper), `customer.subscription.updated` syncs status and keeps the plan
  through a `past_due` dunning window (audits `billing.payment_failed` on the transition),
  `customer.subscription.deleted` downgrades to free; every handler tolerates an unknown
  customer/vault by logging and returning 200
- Family invites (`app/api/v1/endpoints/family.py`) now gate a NEW invite on
  `Vault.plan == family` (RFC 7807 403 `.../plan-upgrade-required`) — the 6-seat `MAX_MEMBERS`
  cap from M7 is unchanged, existing memberships/role management/emergency binder untouched
- Frontend: `/billing` page (three plan cards, current-plan badge, usage line, Stripe Checkout/
  portal redirects, owner-only actions disabled with a hint for non-owners, mono font for every
  price/date/number per the Ledger system) and a Family-page upsell card (matches
  `AnswerUpgradeCard`'s dashed-card styling) when an invite 403s on `plan-upgrade-required`
- **Exit met:** a free vault flipped to Family via a signed-webhook simulation, then the real
  M7 invite/accept flow filled all 6 member seats and a 7th invite was rejected by
  `MAX_MEMBERS` — verified end-to-end in `tests/test_billing.py`'s exit-criterion test. Caveat:
  Stripe is mocked throughout (a `BillingProvider` fake, never the real SDK/network) — no live
  Stripe keys are present in this environment, so the real Checkout/portal redirect and real
  webhook signature verification are unverified against Stripe's actual servers

## M10 — Hardening & launch 🔧 (engineering landed 2026-07-20; exit pending external steps)
- Terraform AWS baseline (`infra/terraform/`): 7 modules (network/database/redis/
  storage/email/app/secrets) + staging & prod envs — ECS Fargate ×4 services, RDS
  Postgres 16, ElastiCache, S3+SSE, ALB, SES, Secrets Manager; `fmt`/`validate`
  clean on both envs; no secret values in code (RDS manages its own master secret)
- Rate limiting: Redis fixed-window behind a provider Protocol — auth 10/min/IP,
  assistant 20/min/user, public emergency 5/min — RFC 7807 429 + Retry-After,
  fail-open on Redis outage; fully unit-tested
- Sentry wired in the API behind `SENTRY_DSN` (web deliberately deferred — see
  LAUNCH.md); backup/restore drill script run green against compose Postgres +
  runbook (`docs/runbooks/backup-restore.md`)
- Load tests (local, 10 VUs/30s, real Postgres/Redis/MinIO): search p95 75.8ms
  (target <300ms), upload ticket flow p95 227.3ms (target <2s) — k6 scripts ready
  for a staging-scale rerun; found + documented a stale-image CI gap on the way
- `docs/LAUNCH.md`: dependency audits run, cookie/authz/webhook/presigned-URL
  checks recorded, SES SMTP-auth + S3 task-role app gaps captured as blockers
- **Exit (pending):** checklist items owned outside this repo — terraform apply,
  DNS/TLS, live Sentry/Stripe accounts, legal review of the medical-data posture

**Deferred (V2/V3 per PRD + decisions log):** Gmail sync (M-V2, needs Google restricted-scope
verification lead time — start the application during M5), mobile apps (2j pattern exists),
vehicle/tax/estate modules, wallet integrations, voice, calendar sync.
