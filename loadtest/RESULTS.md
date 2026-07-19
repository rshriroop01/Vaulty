# Load test results

M10 hardening — PRD Year-1 targets: search p95 < 300ms, upload p95 < 2s.
These numbers are **local-laptop, small-corpus, low-concurrency** — a sanity
check that the code path is fast, not a substitute for the 10k-user-scale
test the PRD ultimately calls for (that needs staging infra against RDS/S3,
which is the parallel Terraform track in this milestone).

## How this was run

- Driver: `loadtest/pyloadtest.py` (asyncio + httpx). **k6 is not installed**
  in this environment (`which k6` returned nothing) — `loadtest/search.js`
  and `loadtest/upload.js` are written and ready for whoever has k6, same
  scenarios and thresholds, but were not executed here.
- Target: Postgres, Redis, and MinIO from the project's `docker-compose`
  stack (real services, not mocks/fakes).
- **Deviation worth flagging:** the `api` container in docker-compose was
  crash-looping on startup (`ModuleNotFoundError: No module named 'stripe'`)
  — the image predates M9 adding the `stripe` dependency and was never
  rebuilt; `docker compose build api` in turn failed in this sandbox because
  the Docker credential helper (`docker-credential-desktop`) isn't on PATH
  here, blocking registry metadata fetches even for public base images. Load
  wasn't hard-blocked by this: `apps/api/.venv` already has every runtime
  dependency (it's what `pytest` uses), so the API was run **natively**
  (`uvicorn app.main:app`) against the compose Postgres/Redis/MinIO ports
  instead of inside its container. Same code, same config surface
  (`DATABASE_URL`/`REDIS_URL`/`S3_*` pointed at `localhost`), different
  process boundary — the numbers below reflect real network hops to real
  Postgres/Redis/MinIO, just not a containerized API process. The stale
  image is a separate, pre-existing gap worth fixing before launch (tracked
  in `docs/LAUNCH.md`).
- Concurrency: 10 VUs, 30s per scenario (modest, as scoped for this pass).
- Rate limiting (this milestone's own change) was **enabled** for this run
  (`ENVIRONMENT=local` outside the test suite) — it never triggered, because
  `/search` and `/documents/uploads` aren't in the rate-limited set (only
  auth login/signup, assistant ask, and the public emergency endpoint are).

## Results — 2026-07-20

### search — GET /api/v1/search

Corpus: 8 seeded documents (titles like `loadtest-acme-warranty-receipt-*`),
queries randomly drawn from `["acme", "warranty", "insurance", "receipt",
"policy", "loadtest"]`.

| requests | errors | p50 | p95 | p99 | threshold | result |
|---|---|---|---|---|---|---|
| 9,805 | 0 | 24.8ms | 75.8ms | 109.3ms | p95 < 300ms | **PASS** |

### upload — full ticket flow (POST /uploads -> PUT presigned -> POST /complete)

Each iteration deletes the document afterward to stay under the free-tier
25-document quota across a 30s run at 10 concurrent VUs.

| requests | errors | p50 | p95 | p99 | threshold | result |
|---|---|---|---|---|---|---|
| 1,183 | 0 | 169.2ms | 227.3ms | 256.8ms | p95 < 2000ms | **PASS** |

## Honest caveats

- **Corpus size**: 8 documents for search is nowhere near a real vault at
  scale, let alone the aggregate index size at 10k users. Postgres FTS
  latency is dominated by index size and concurrent write load, neither of
  which this run exercises.
- **Concurrency**: 10 VUs is a fraction of any meaningful production burst.
  No results here should be read as "validated at PRD scale" — that requires
  a staging environment (real RDS instance, real network latency, realistic
  document count) once the Terraform track lands.
- **Single machine**: driver and target share the same host, so there's no
  real network latency, and CPU contention between the load generator and
  the API process itself can only make these numbers look *better* than a
  real client would see.
- **Upload byte transfer**: the PUT to MinIO is real but tiny (1KB payloads)
  and local — a real client uploading a multi-MB file over the internet will
  see materially different (dominated by upload bandwidth, not API latency)
  numbers; that's expected and is why the PRD frames the target around the
  ticket flow rather than raw transfer time.

## Re-running

```
docker compose up -d postgres redis minio minio-init
cd apps/api && .venv/bin/python -m alembic upgrade head
DATABASE_URL=postgresql+asyncpg://vaultly:vaultly@localhost:5432/vaultly \
  REDIS_URL=redis://localhost:6379/0 \
  S3_ENDPOINT_URL=http://localhost:9000 S3_BUCKET=vaultly-documents \
  S3_ACCESS_KEY=vaultly S3_SECRET_KEY=vaultly-local SMTP_HOST=localhost \
  .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

.venv/bin/python ../../loadtest/pyloadtest.py --scenario both --vus 10 --duration 30
```

Once k6 is available: `k6 run loadtest/search.js` / `k6 run loadtest/upload.js`
with `BASE_URL` and `AUTH_COOKIE` set (see the scripts' header comments).
