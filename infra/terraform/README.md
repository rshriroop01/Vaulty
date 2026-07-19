# Vaultly production infrastructure (Terraform)

AWS baseline for M10 (Hardening & launch): staging + prod environments built
from shared modules, matching the stack in `docs/ARCHITECTURE.md` — ECS
Fargate (web, api, worker, beat), RDS PostgreSQL 16, ElastiCache Redis 7, S3
for documents, SES for email.

```
infra/terraform/
  modules/
    network/    VPC, 2 AZs, public+private subnets, NAT, security groups
    database/   RDS PostgreSQL 16 — multi-AZ toggle, 30-day backups, deletion protection, encrypted storage
    redis/      ElastiCache Redis 7 — single node (staging) or replicated w/ failover (prod)
    storage/    S3 documents bucket — SSE-S3, versioning, public access blocked, lifecycle, CORS
    email/      SES domain identity + DKIM + MAIL FROM + DMARC (route53_zone_id assumed pre-existing)
    app/        ECS Fargate cluster, ALB, task/execution IAM roles, autoscaling, CloudWatch logs, ECR repos
    secrets/    Secrets Manager resource shells (names/ARNs only — no values)
  envs/
    staging/    small instances, single-AZ, short retention
    prod/       multi-AZ RDS, Redis replication, deletion protection on
```

Every module: `variables.tf` (described, sensible defaults), `outputs.tf`,
no provider blocks (providers live only in `envs/*/providers.tf`). All
resources get `project` / `env` / `managed-by` tags via each env's
`default_tags` block.

## Prerequisites / assumptions

- **Route53 hosted zone already exists** for the apex domain (e.g.
  `vaultly.example.com`) and its ID is passed in as `route53_zone_id`. This
  stack does not create hosted zones — DNS delegation is a one-time manual
  step outside Terraform's blast radius.
- **The S3 state bucket + DynamoDB lock table already exist** (bootstrap
  below) — a stack can't create the backend it stores its own state in.
- **`terraform.example.com` placeholders**: every `*.tfvars.example` uses
  `vaultly.example.com`; replace with the real domain before use.
- Container images are pushed to the ECR repos this stack creates (or to
  externally-managed repos if `create_ecr_repositories = false`) — Terraform
  does not build or push images.
- The RDS master password is never handled by Terraform: `manage_master_user_password = true`
  lets RDS generate and own the credential directly in Secrets Manager, so no
  plaintext DB password ever appears in `.tf` files, plan output, or state.
- All other app secrets (`SECRET_KEY`, `ANTHROPIC_API_KEY`, Stripe keys, S3
  static keys, SES SMTP creds) get **empty Secrets Manager shells** from the
  `secrets` module — Terraform creates the named container, a human (or a
  separate CI secret-injection step with real credential access) populates
  the value with `aws secretsmanager put-secret-value` after apply.

## Bootstrapping remote state (one-time, per AWS account)

Run this once, manually, before any env's `terraform init`:

```bash
aws s3api create-bucket --bucket vaultly-terraform-state --region us-east-1
aws s3api put-bucket-versioning --bucket vaultly-terraform-state \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket vaultly-terraform-state \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-public-access-block --bucket vaultly-terraform-state \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws dynamodb create-table --table-name vaultly-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

Both `envs/staging` and `envs/prod` share this one bucket/table — they're
kept apart by state `key` (`vaultly/staging/...` vs `vaultly/prod/...`), set
in each env's `versions.tf`.

## Init / plan / apply, per environment

```bash
cd infra/terraform/envs/staging   # or envs/prod
cp backend.hcl.example backend.hcl              # fill in real bucket/table/region
cp terraform.tfvars.example terraform.tfvars    # fill in real domain, zone ID, image URIs
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

`backend.hcl` and `terraform.tfvars` are gitignored (see
`infra/terraform/.gitignore`) — they hold real account-specific values, not
secrets, but still shouldn't drift from what's actually deployed without
review.

To switch AWS accounts/profiles, export `AWS_PROFILE` (or use SSO) before
`init`/`plan`/`apply` as usual; nothing in this stack hardcodes credentials.

## Building and pushing images

The `app` module creates two ECR repos per env (`<name_prefix>/web` and
`<name_prefix>/api` — worker and beat reuse the api image, just with a
different container `command`, mirroring `docker-compose.yml`). After the
first `apply` (so the repos exist), build and push using the Dockerfiles
already in `infra/docker/`:

```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com

docker build -f infra/docker/api.Dockerfile -t <account>.dkr.ecr.us-east-1.amazonaws.com/vaultly-staging/api:<tag> apps/api
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/vaultly-staging/api:<tag>

docker build -f infra/docker/web.Dockerfile -t <account>.dkr.ecr.us-east-1.amazonaws.com/vaultly-staging/web:<tag> apps/web
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/vaultly-staging/web:<tag>
```

Then set `image_web` / `image_api` in `terraform.tfvars` to the pushed
tag (prefer an immutable digest, `repo@sha256:...`, for prod) and
`terraform apply`. The dev Dockerfiles in `infra/docker/` run with `--reload`
/ `npm run dev`, which is fine for staging smoke-testing but not tuned for
prod (no multi-stage build, no `next build && next start`); hardening those
images is tracked as follow-up, not part of this Terraform change.

## Deploying a new release (migrations)

`alembic upgrade head` is **not** baked into the api/worker/beat service
startup — running it from N autoscaled api tasks concurrently would race.
Instead the `app` module publishes a standalone `migrate` task definition
(`module.app.migrate_task_definition_arn`). Run it once before rolling
tasks to a new image:

```bash
aws ecs run-task \
  --cluster $(terraform output -raw -state=... ) \
  --task-definition $(terraform output -raw migrate_task_definition_arn) \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[<private-subnet-ids>],securityGroups=[<app-sg-id>],assignPublicIp=DISABLED}"
```

Then update the `image_api` (and `image_web`) vars and `terraform apply` (or
`aws ecs update-service --force-new-deployment` for a same-image redeploy).

## Secret injection

After `terraform apply`, `app_secret_arns` lists every Secrets Manager entry
Terraform created but left empty. Populate each from wherever the real
credential lives (never commit it):

```bash
aws secretsmanager put-secret-value \
  --secret-id vaultly/staging/anthropic-api-key \
  --secret-string "sk-ant-..."
```

Required before first real use: `secret-key`, `anthropic-api-key`. Optional
until billing/Stripe or IAM-user-based S3 auth are wired up:
`stripe-secret-key`, `stripe-webhook-secret`, `stripe-price-premium`,
`stripe-price-family`, `s3-access-key`, `s3-secret-key`, `smtp-username`,
`smtp-password` — see "Known gaps" below for why the last four aren't
wired into a task definition yet.

The RDS master password needs no manual step — it's generated directly into
Secrets Manager by AWS at `terraform apply` time (`manage_master_user_password`).

## Backup / restore posture

- **RDS**: automated backups with point-in-time recovery, retention
  30 days (prod) / 7 days (staging); prod also takes a final snapshot on
  destroy (`skip_final_snapshot = false`) and has `deletion_protection = true`.
  Multi-AZ in prod gives synchronous standby failover; staging is single-AZ.
- **S3 documents bucket**: versioning is on in both envs, so an accidental
  overwrite/delete is recoverable from a noncurrent version until it expires
  (90 days prod / 30 days staging) — this is a second line of defense
  alongside RDS backups, not a replacement (documents live in S3, metadata in
  Postgres).
- **Redis**: treated as a cache/broker, not a system of record — prod takes
  daily snapshots (7-day retention) purely to shorten Celery broker recovery
  time after a failure, not as a durability guarantee.

**Restore drill** (run this against staging, not prod, and periodically):

1. Snapshot restore: `aws rds restore-db-instance-to-point-in-time
   --source-db-instance-identifier vaultly-staging-postgres
   --target-db-instance-identifier vaultly-staging-postgres-restore-test
   --restore-time <ISO8601>` (or `--use-latest-restorable-time`), into the
   same `module.database`-created subnet group / security group.
2. Point a throwaway `psql` session at the restored instance (it's not
   attached to any ECS service automatically) and verify row counts / a few
   known documents against the live instance.
3. Tear down the restore-test instance (`aws rds delete-db-instance
   --skip-final-snapshot`) once verified — it's not managed by this
   Terraform stack and won't show up in `plan`/drift.
4. Record the wall-clock time from step 1 to a verified restore — that's
   your actual RTO, not the PRD target.

This drill is a manual runbook, deliberately not automated in Terraform:
restoring into the *same* Terraform-managed identifier would conflict with
state; restoring to a scratch identifier (as above) keeps the drill blast
radius outside anything `terraform apply` tracks.

## Known gaps / follow-ups (flagged, not fixed here — out of this module's scope)

- **`apps/api/app/services/email.py`'s `SmtpEmailProvider` sends unauthenticated,
  unencrypted SMTP** (`smtplib.SMTP(host, port)`, no `starttls()`/`login()`).
  This infra provisions SES domain verification + DKIM + a real SMTP
  endpoint (`email-smtp.<region>.amazonaws.com:587`) and secret shells for
  `smtp-username`/`smtp-password`, but the app can't actually authenticate
  against SES's SMTP interface until that provider gains STARTTLS + AUTH.
  Application-side fix, not a Terraform change.
- **S3 static credentials, not the task IAM role.** `apps/api/app/core/storage.py`
  always passes `aws_access_key_id`/`aws_secret_access_key` to `boto3.client(...)`
  from `settings.s3_access_key`/`s3_secret_key` (default `""`, not `None`), so
  it can't fall back to the ECS task role's credentials the way an
  IAM-role-only setup would. The `app` module's task role *is* scoped with
  the right S3 permissions for when that changes, but until the app omits
  empty-string creds (letting boto3's default credential chain take over),
  ops must create an IAM user scoped to the documents bucket and populate
  `s3-access-key`/`s3-secret-key` out-of-band for uploads/downloads to work
  in staging/prod at all.
- **Dev-mode Dockerfiles in prod.** `infra/docker/{api,web}.Dockerfile` run
  `uvicorn --reload` / `npm run dev` with source bind-mount assumptions from
  Compose; the ECS task definitions here point at whatever image URI is
  pushed, so a production-hardened multi-stage build (`next build && next start`,
  no `--reload`) should replace these before a real prod launch — tracked
  separately, not a Terraform concern.

## Verification

`terraform` was installed for this change (`hashicorp/tap/terraform`,
v1.15.8) and the following were run and pass clean:

```bash
$ terraform fmt -recursive -check infra/terraform
(exit 0, no output)

$ cd infra/terraform/envs/staging && terraform init -backend=false && terraform validate
Terraform has been successfully initialized!
Success! The configuration is valid.

$ cd ../prod && terraform init -backend=false && terraform validate
Terraform has been successfully initialized!
Success! The configuration is valid.
```

No credentials are configured in this environment, so `plan`/`apply` were
not (and cannot be) exercised — `validate` only checks internal consistency
(types, references, required arguments), not whether the AWS API will accept
every resource as configured. Review `terraform plan` output carefully
against real AWS credentials before the first `apply`.
