# Vaultly production launch checklist

M10 exit criterion: this checklist green. Checked items carry a one-line
evidence note for what was actually verified **in this hardening session**
(2026-07-20) — unchecked items are real work still pending, most of them
blocked on the parallel `infra/terraform` track or on external
parties (legal, a live Sentry project, a live Stripe account).

## Infrastructure

- [ ] `terraform apply` run against the target AWS account (staging, then
      production) — owned by the parallel infra/terraform track in this
      milestone; not touched from this session.
- [ ] DNS cut over to the production load balancer / CDN.
- [ ] TLS certificates issued and auto-renewing (ACM or equivalent).
- [ ] Secrets injected via the deployment platform's secret store (never
      `.env` in prod) — `SECRET_KEY`, `DATABASE_URL`, `STRIPE_SECRET_KEY`,
      `STRIPE_WEBHOOK_SECRET`, `ANTHROPIC_API_KEY`, `SENTRY_DSN`, S3
      credentials.
- [ ] Production `docker compose`-equivalent images are rebuilt and
      current. **Found broken in this session**: the local `api` image was
      stale and crash-looping (`ModuleNotFoundError: stripe`) because it
      predates the M9 dependency addition and was never rebuilt — caught
      only because the load test needed a working API. Confirm the prod
      image build pipeline actually rebuilds on every dependency change
      (this should be a CI-enforced image build, not a manual step) before
      launch. See `loadtest/RESULTS.md` for the full story.

## Data

- [ ] Alembic migrations applied cleanly against a production-shaped
      database (all 10 migrations, `0001`–`0010`, currently apply cleanly
      against local Postgres 16 — verified via `alembic upgrade head`
      during this session's backup drill, but not against an RDS instance).
- [x] Backup + restore drill green — `scripts/backup_drill.sh` run against
      the local docker-compose Postgres 2026-07-20: dump/restore round-trip
      verified, all 7 sampled tables matched row counts (users, vaults,
      vault_memberships, documents, reminders, audit_log, feature_flags).
      See `docs/runbooks/backup-restore.md` for the production posture
      (RDS automated backups + PITR) and the required quarterly cadence —
      that cadence is a process commitment, not something a single session
      can "complete."
- [ ] RDS automated backups + PITR enabled on the production instance
      (Terraform track).
- [ ] First production backup-restore drill executed against the real RDS
      instance (the local drill above validates the *procedure*, not the
      production database).

## Security (pen-test pass)

- [x] Rate limiting implemented and tested — `app/core/rate_limit.py`
      (Redis-backed fixed window, fail-open on Redis outage), applied to
      auth login/signup (10/min/IP), assistant ask (20/min/user), and the
      public emergency PIN endpoint (5/min/IP+token). 6 tests in
      `apps/api/tests/test_rate_limit.py` cover over-limit -> 429 in the
      RFC 7807 shape with `Retry-After`, window reset, fail-open when Redis
      is unreachable, and disabled-by-default in the test environment.
- [ ] Rate limits verified against a real client from outside localhost
      (this session verified the logic with a fake backend + unit tests,
      and confirmed live Redis wiring via `/readyz`, but did not fire 10+
      real login attempts at a running server to watch a real 429 —
      reasonable follow-up before launch).
- [x] Authz / category-access matrix spot-checked — existing coverage in
      `apps/api/tests/test_family.py` (category_access matrix: full/view/
      none per member) and `tests/test_documents.py`/`tests/test_emergency.py`
      (emergency-only members see nothing by default, `_get_owned` hides
      invisible-category documents as 404s). Not re-derived this session;
      confirmed still passing as part of the full test run (104 passed).
- [x] Webhook signature verification — Stripe webhook handler
      (`app/api/v1/endpoints/billing.py`) calls
      `BillingProvider.verify_webhook`, which wraps
      `stripe.Webhook.construct_event`; `test_webhook_invalid_signature_returns_400`
      in `tests/test_billing.py` covers the rejection path. Never verified
      against Stripe's real signing secret (no live keys in this
      environment, same caveat M9 shipped with).
- [x] Presigned-URL scoping — `app/core/storage.py`: upload/download URLs
      are scoped to a single `{vault_id}/{document_id}/...` object key,
      15-minute TTL (`PRESIGN_TTL_SECONDS`), and `download_document`/
      `initiate_upload` both re-check `ctx.can_write` / category access
      before signing — a URL can't be minted for a document outside the
      caller's vault or visible categories.
- [x] Cookie flags — `app/api/v1/endpoints/auth.py` sets `httponly=True`,
      `samesite="lax"` on both access and refresh cookies;
      `secure=settings.cookie_secure`. **Action required**: `cookie_secure`
      defaults to `False` for local dev — confirm `COOKIE_SECURE=true` is
      set in the staging/production secret store, since nothing in code
      enforces this the way `SECRET_KEY` is enforced at startup
      (`app/main.py` only hard-fails on the default secret key, not on an
      insecure cookie flag — worth the same treatment before launch).
- [x] Dependency audit run — see **Dependency audit findings** below.
- [ ] External pen-test (or at minimum a structured internal red-team pass)
      against a staging deployment — the items above are code-level
      self-checks, not an adversarial test.

### Dependency audit findings (run 2026-07-20)

**`pip audit` (apps/api)**: initially found `pip` itself (26.0.1, the build
tool, not a runtime dependency) affected by 3 known CVEs
(`PYSEC-2026-196`, `PYSEC-2026-2875`, `PYSEC-2026-2876`); fixed in this
session by upgrading `apps/api/.venv`'s pip to 26.1.2. Re-run is clean: **no
known vulnerabilities** in any runtime dependency.

**`npm audit` (apps/web)**: 7 findings, all requiring a breaking major-version
bump to fix — **not applied in this session** (out of scope for a hardening
pass without a dedicated regression cycle; `npm audit fix --force` was not
run):

- `vitest`/`vite`/`esbuild`/`vite-node`/`@vitest/mocker` — dev/test-only
  dependency chain, 1 critical (`vitest`), 1 high (`vite`), several
  moderate. Fix requires `vitest@2.x -> 4.x`. **Not a production runtime
  risk** (never ships to a built app) but should be scheduled — a major
  vitest upgrade needs its own test-suite verification pass.
- `postcss` (moderate, XSS in CSS stringify, bundled inside
  `next/node_modules/postcss`) — npm's suggested fix is downgrading `next`
  to `9.3.3`, which is nonsensical (a major regression); the actual fix is
  almost certainly a `next` patch/minor bump once one ships with an updated
  bundled postcss. Needs a real look, not the automated suggestion.
- **Action before launch**: re-run `npm audit` after addressing the above,
  and gate CI on `npm audit --omit=dev` (or equivalent) so new
  vulnerabilities in shipped dependencies fail the build.

## Observability

- [x] Sentry SDK wired for the API — `sentry-sdk[fastapi]` added to
      `apps/api/pyproject.toml`, initialized in `app/main.py` only when
      `settings.sentry_dsn` is non-empty (`SENTRY_DSN` env var, empty by
      default — verified zero behavior change: full test suite and mypy
      pass with the setting unset, and `sentry_sdk` is never imported in
      that path).
- [ ] Live `SENTRY_DSN` configured in the production secret store, and a
      real error verified to land in the Sentry project (untestable here —
      no Sentry account/DSN in this environment).
- [ ] Web error tracking — **deliberately skipped this session.**
      `@sentry/nextjs` was ruled out per the milestone's own guidance
      (heavy). A hand-rolled `instrumentation.ts` that POSTs directly to
      Sentry's envelope endpoint was considered, but the envelope protocol
      (multi-part NDJSON-ish framing, DSN parsing for project id/public
      key, required headers) is easy to get subtly wrong in a way that
      fails silently — errors look "reported" but never arrive. Given no
      live Sentry project was available to validate against, shipping an
      unverified hand-rolled implementation seemed worse than shipping
      nothing. `NEXT_PUBLIC_SENTRY_DSN=` was still added to `.env.example`
      so the wiring point is documented. **Recommendation**: either accept
      `@sentry/nextjs`'s bundle-size cost, or build the envelope POST
      against a real (even free-tier) Sentry project so it can actually be
      verified before launch.
- [ ] CloudWatch dashboards (or equivalent) for API latency, error rate,
      queue depth — Terraform track.
- [ ] Reminder delivery-rate metric wired to a dashboard/alert — the
      underlying data already exists (`reminder_sends`, M5's delivery-rate
      stat surfaced in the Reminders center) but isn't yet piped to an
      ops-facing dashboard.
- [ ] Structured logs (`app/core/logging.py`, already JSON-in-prod) shipped
      to a log aggregator — Terraform track.

## Legal

- [ ] Medical-data posture formally reviewed by counsel, per
      `docs/ARCHITECTURE.md` decision #6 ("we assume consumer-directed
      storage, not HIPAA-covered, but treat it at HIPAA-adjacent rigor").
      **Not performed this session** — this needs an actual lawyer, not an
      engineering self-assessment. What *was* confirmed present in code as
      input to that review: encryption at rest (S3/MinIO SSE, M2),
      TLS-only cookies in prod (`cookie_secure`), append-only audit logging
      on every document/emergency-binder access (`app/core/audit.py`,
      `audit_log` table since migration 0001), and role/category-based
      access control gating every document read (M7's access matrix).
      **Known gap flagged, not closed**: `docs/ROADMAP.md`'s M2 section
      calls out that *app-managed per-document envelope encryption* (on
      top of storage-layer SSE) was deferred to M10 hardening. It is
      **not** implemented as part of this session — it wasn't in this
      session's explicit deliverable list (rate limiting, Sentry, backups,
      load test, launch checklist) and doing it justice needs its own
      design pass (client-side key handling for presigned direct uploads,
      per the original deferral note), not a bolt-on. Flagging clearly so
      it isn't lost: **either implement it or explicitly re-scope decision
      #2 before launch**, don't let it sit as an implicit gap.
- [ ] Privacy policy published and linked from signup/footer.
- [ ] Terms of Service published and linked from signup/footer.
- [ ] Data processing agreement / subprocessor list (Stripe, Anthropic, AWS,
      email provider) prepared if required for the target market.

## PRD Year-1 metric gates

- [x] **Search p95 < 300ms** — local load test (`loadtest/pyloadtest.py`,
      10 VUs, 30s, 8-document corpus against the local docker-compose
      Postgres): **p50 24.8ms / p95 75.8ms / p99 109.3ms, 9,805 requests, 0
      errors. PASS**, well under target. Caveat in `loadtest/RESULTS.md`:
      tiny corpus and low concurrency — this is a code-path sanity check,
      not a 10k-user validation.
- [x] **Upload ticket flow < 2s** — same run: **p50 169.2ms / p95 227.3ms /
      p99 256.8ms, 1,183 requests, 0 errors. PASS.**
- [ ] **Both targets re-verified at PRD scale** (10k-user load pattern,
      staging infra, realistic corpus size) — blocked on the Terraform
      staging environment landing.
- [ ] **Reminder delivery rate ≥ 99%** — M5 shipped with 100% (1/1) in its
      own exit test; needs a real observed rate over a meaningful volume in
      production, fed by the delivery-rate dashboard above (not yet wired).
- [ ] **Crash rate** target — no crash-rate metric exists yet (frontend or
      backend); needs Sentry (web half still pending, see Observability)
      before this is measurable at all.
