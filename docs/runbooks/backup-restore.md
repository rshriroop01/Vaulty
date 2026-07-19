# Backup & restore runbook

M10 hardening. Two halves: the local drill you can run today against
docker-compose, and the production posture that runs unattended on RDS.

## Local drill

```
scripts/backup_drill.sh
```

What it does:

1. `pg_dump`s the compose `postgres` service (`vaultly` database, custom
   format) via `docker compose exec`, and pulls the dump to the host with
   `docker compose cp` — no `pg_dump`/`psql` install required on the host,
   only Docker.
2. Creates a throwaway `vaultly_restore_drill` database on the same Postgres
   server and `pg_restore`s the dump into it.
3. Runs a row-count sanity diff between the source `vaultly` database and the
   restored copy across a representative slice of tables (`users`, `vaults`,
   `vault_memberships`, `documents`, `reminders`, `audit_log`,
   `feature_flags`).
4. Drops the scratch database and the remote dump file, and prints a single
   `PASS`/`FAIL` line (non-zero exit on any mismatch or step failure).

Requires the `postgres` compose service to be up (`docker compose up -d
postgres` or the full stack). Safe to run repeatedly — it never touches the
real `vaultly` database beyond `pg_dump`, and the scratch database is dropped
both before (defensively) and after the run.

**Last verified run:** 2026-07-20, against the local dev stack — PASS, all 7
sampled tables matched (users=3, vaults=3, vault_memberships=4, documents=5,
reminders=2, audit_log=34, feature_flags=1). Dump size 37,616 bytes — tiny
local corpus, not representative of a production backup's size or duration.

## Production posture

- **Automated backups:** RDS automated backups enabled at creation
  (`infra/terraform`), daily snapshot window + transaction-log backups
  retained per the RDS retention window (target: 7-day retention at launch,
  revisit for a longer window once real usage data exists).
- **Point-in-time recovery (PITR):** RDS PITR is enabled by the same
  automated-backups setting — restore to any point within the retention
  window, not just the nightly snapshot. This is the primary recovery
  mechanism for "we deleted the wrong thing" and "bad migration" incidents.
- **Cross-region / long-term retention:** manual or scheduled snapshots
  copied to a second region on a slower cadence (weekly), for disaster
  recovery beyond the automated-backup window. Tracked as a launch-checklist
  item (`docs/LAUNCH.md`) — depends on the Terraform infra work landing.
- **Drill cadence:** run `scripts/backup_drill.sh`'s logic (or an equivalent
  RDS-snapshot-restore-to-scratch-instance drill) **quarterly**, and after
  any schema change that touches a table in the sanity-check list. A restore
  drill that isn't regularly exercised is not a backup strategy — it's an
  assumption. Record each run's PASS/FAIL and row counts in this file (or a
  linked ops log) so drift is visible.
- **What the drill does NOT cover:** S3/MinIO document bytes (object storage
  has its own versioning/replication story — S3 versioning + cross-region
  replication in production, not covered by this Postgres-focused drill) and
  Redis (ephemeral job/cache state, not a source of truth — nothing there
  needs backing up).

## Recovery runbook (sketch — expand before launch)

1. Identify the target recovery point (timestamp for PITR, or a specific
   snapshot).
2. Restore RDS to a **new** instance (never in place) — PITR/snapshot restore
   creates a fresh instance by design, so this is the default, not an extra
   precaution.
3. Point a staging copy of the API at the restored instance; run the same
   row-count sanity check as the local drill against a handful of key tables,
   plus a manual spot-check of a recently modified record.
4. Only after validation, cut the production `DATABASE_URL` over (maintenance
   window, per the launch checklist).
5. Audit-log and postmortem the triggering incident — this runbook is a
   safety net, not a substitute for finding out why it was needed.
