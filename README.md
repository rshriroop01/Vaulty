# Vaultly

Secure cloud platform that helps individuals and families organize every important document in one place — and reminds them before important dates.

- **PRD (source of truth):** [docs/PRD.md](docs/PRD.md)
- **Architecture & decisions:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Implementation roadmap:** [docs/ROADMAP.md](docs/ROADMAP.md)
- **UI design handoff (final, "Ledger" system):** [docs/design/handoff-v1/README.md](docs/design/handoff-v1/README.md)

## Setup (under 10 minutes)

**Prerequisites:** Docker Desktop, `make`. That's it — Python/Node are only needed for running tools natively.

```bash
git clone <repo-url> vaultly && cd vaultly
cp .env.example .env   # local defaults work as-is; no secrets needed
make dev               # builds and starts everything
```

First build takes a few minutes; subsequent starts are seconds. Then:

| URL | What |
|---|---|
| http://localhost:3000 | Web app (foundation status page) |
| http://localhost:8000/api/v1/docs | Interactive API docs (Swagger) |
| http://localhost:8000/healthz · /readyz | Liveness / readiness |
| http://localhost:8025 | Mailpit — every locally sent email lands here |
| http://localhost:9001 | MinIO console (user `vaultly` / `vaultly-local`) |

You have working: hot reload on both apps, Postgres 16, Redis 7, Celery worker + beat, S3-compatible object storage, and a local email inbox.

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
infra/terraform/       IaC (populated at first deploy)
docs/                  PRD, architecture, ADRs, roadmap, design handoff
```

## Conventions that keep us honest

- **API-first:** every endpoint lives under `/api/v1/`; the OpenAPI schema is the contract and frontend types are generated from it (`make types`).
- **Errors:** all API errors are RFC 7807 `problem+json`; raise `AppError` subclasses, never ad-hoc responses.
- **Logging:** structured via `structlog`; every request carries an `X-Request-ID`. No `print()`.
- **Secrets:** environment only (`app/core/config.py`); gitleaks blocks commits containing secrets.
- **Feature flags:** new functionality ships behind a flag (`app/core/feature_flags.py`).
- **Audit:** security-relevant actions write to `audit_log`.
- **Design:** UI work follows the Ledger tokens in `apps/web/app/globals.css` — colors/type/spacing are final per the design handoff; don't invent values.
- **Tests:** backend coverage gate is 80% (PRD requirement) and CI enforces lint, types, tests, build, and secret scanning on every PR.
