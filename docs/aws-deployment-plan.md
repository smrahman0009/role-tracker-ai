# AWS deployment plan

The end-to-end plan for getting Role Tracker AI live on AWS as a
**cloud-native (Tier 2) deployment** — single Docker container on
EC2, with binary blobs in S3, structured records in DynamoDB,
secrets in AWS Secrets Manager.

This doc is the master checklist for the deployment work. Every
script we'll write, every code change we'll make, the order in
which they happen, and what each one costs.

---

## Target architecture

```
                     ┌──────────────────────────────────────────┐
                     │         AWS account (ca-central-1)       │
                     │                                          │
   browser ─────────►│   EC2 t2.micro (Docker container)        │
                     │     │                                    │
                     │     ├──► S3   (resume PDFs, DOCX exports)│
                     │     ├──► DynamoDB (applied / letters /   │
                     │     │              usage / queries /     │
                     │     │              seen_jobs)            │
                     │     └──► Secrets Manager (API keys)      │
                     │                                          │
   GitHub Actions ──►│   ECR (Docker image registry)            │
                     │                                          │
                     └──────────────────────────────────────────┘
```

Each AWS service is used for what it's best at: S3 for blobs, DynamoDB
for structured records, Secrets Manager for secrets. The container itself
is stateless — it can die and respawn without losing any data.

---

## Files we'll create

Everything below gets committed to the repo so the deployment is
reproducible — no clicking through the AWS console for the real setup.

### Infrastructure scripts (`infra/`)

| File | What it does | Idempotent? |
|------|--------------|-------------|
| `infra/00-vars.sh` | Shared variables (region, account ID, resource names). Sourced by every other script. | n/a |
| `infra/01-ecr.sh` | Creates the ECR repository for our Docker image. Sets a lifecycle rule to auto-delete old images so we don't pay for storage forever. | ✅ |
| `infra/02-s3.sh` | Creates the S3 bucket for resume PDFs / DOCX. Sets versioning, server-side encryption, and a private ACL. | ✅ |
| `infra/03-dynamodb.sh` | Creates 5 DynamoDB tables (applied, letters, usage, queries, seen_jobs) with on-demand billing. | ✅ |
| `infra/04-secrets.sh` | Creates Secrets Manager entries for `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `JSEARCH_RAPIDAPI_KEY`, and `APP_TOKEN`. You paste the values once. | ✅ |
| `infra/05-iam.sh` | Creates an IAM role for EC2 with **least-privilege** access to the resources above (read/write on the named tables and bucket only — nothing else). | ✅ |
| `infra/06-ec2.sh` | Launches the EC2 t2.micro with the IAM role attached, security group (ports 80/443/22), SSH key, and a user-data script that installs Docker + pulls our image on first boot. | ✅ |
| `infra/07-deploy.sh` | One-shot deploy: build the Docker image locally, push to ECR, SSH into EC2, pull the new image, restart the container. Used until GitHub Actions takes over. | ✅ |
| `infra/99-teardown.sh` | Optional. Deletes everything we created so the account goes back to zero cost. Useful if you want to start over or stop using AWS. | ✅ |

Each script will be ~30–80 lines of `aws` CLI commands, heavily
commented so you can read what each command does before running it.

### Code changes (`src/role_tracker/`)

| New module | Replaces | Why |
|------------|----------|-----|
| `aws/s3_resume_store.py` | `resume.store.FileResumeStore` | Resume PDFs go to S3 instead of `data/resumes/*.pdf` |
| `aws/dynamodb_applied_store.py` | `applied.store.FileAppliedStore` | Applied records → DynamoDB |
| `aws/dynamodb_letter_store.py` | `letters.store.FileLetterStore` | Cover letters → DynamoDB |
| `aws/dynamodb_usage_store.py` | `usage.store.FileUsageStore` | Monthly usage rollups → DynamoDB |
| `aws/dynamodb_query_store.py` | `queries.json_store.JsonQueryStore` | Saved queries → DynamoDB |
| `aws/dynamodb_seen_jobs_store.py` | `jobs.seen.FileSeenJobsStore` | Seen jobs index → DynamoDB |
| `aws/secrets.py` | `.env` reads | Loads API keys from Secrets Manager when running on AWS |

The route layer **doesn't change** — every store class implements the
same `Protocol` it always did. The factory functions in
`api/routes/*.py` will pick the file-backed or AWS-backed
implementation based on a `STORAGE_BACKEND` env var:

```python
def get_applied_store() -> AppliedStore:
    if Settings().storage_backend == "aws":
        return DynamoDBAppliedStore(table_name=Settings().applied_table)
    return FileAppliedStore()
```

This means the same Docker image runs on your laptop (file backend)
and on EC2 (AWS backend) — no two-image fork.

### Tests (`tests/aws/`)

For each new store class, a test file using `moto` (the AWS
mocking library) so we can verify behaviour without hitting real AWS.
Same coverage standard as the existing file-backed stores.

### CI/CD (`.github/workflows/`)

| File | What it does |
|------|--------------|
| `.github/workflows/deploy.yml` | On push to `main`: build the Docker image, push to ECR, trigger the EC2 to pull + restart the container. Uses GitHub OIDC (no long-lived AWS keys in GitHub Secrets). |

---

## Order of operations

Each step is its own commit on `phase/8-docker` (or a follow-on branch
once we merge). At the end of each step the app should still work —
no big-bang deployments.

### Phase A: Provision infrastructure (no code changes yet)

1. **Write `infra/00-vars.sh` + `infra/01-ecr.sh`** through
   `infra/06-ec2.sh`. You eyeball each one before we run it.
2. **Run them in order.** After step 6 you have an EC2 instance running
   the *current* Docker image (file-backed storage on EBS) — Tier 1
   essentially, just as a sanity check that the infra is correct.
3. **Smoke test:** visit the EC2 public IP in a browser. SPA loads,
   API answers. ~1 hour total.

### Phase B: Build the cloud-native stores

For each store, do all of these in one focused session:

1. Write the new store class (`src/role_tracker/aws/X.py`).
2. Write its tests (`tests/aws/test_X.py`) using `moto`.
3. Update the factory in the relevant `api/routes/*.py` to pick it
   when `STORAGE_BACKEND=aws`.
4. Run the full test suite — both file-backed tests and the new AWS
   tests pass.
5. Commit. Push.

Order (smallest blast radius first):
- `usage` (read-mostly, low traffic)
- `queries`
- `applied`
- `letters` (most complex shape)
- `seen_jobs`
- `s3_resume_store` (binary blobs are different shape)

After each store lands, redeploy to EC2 (`infra/07-deploy.sh`) and
verify the app still works against the real AWS resource.

### Phase C: Secrets

1. Replace `.env` reads with Secrets Manager reads (only when running on AWS).
2. Bake the Secrets Manager loader into `Settings`.
3. Test locally with `STORAGE_BACKEND=file` — `.env` still works.
4. Test on EC2 with `STORAGE_BACKEND=aws` — keys load from Secrets Manager.

### Phase D: CI/CD

1. Create the GitHub OIDC federated credential in IAM (one-time AWS console click).
2. Write `.github/workflows/deploy.yml`.
3. Push a no-op commit, watch the workflow build + push + deploy automatically.
4. From now on, every push to `main` ships.

### Phase E: Polish (optional but recommended)

1. **Custom domain.** Buy `roletracker.app` (or similar) on Route 53, point it at the EC2's public IP. ~$12/year.
2. **HTTPS.** Add a Caddy or nginx sidecar with auto-renewing Let's Encrypt cert. (Or skip and use AWS-issued ACM cert + CloudFront.)
3. **Soft monthly caps** on the usage dashboard now that it has real data.
4. **Backups.** Enable DynamoDB point-in-time recovery (one CLI command per table) so we can restore to any point in the last 35 days.

---

## What this costs

| Service | Free tier (12 months) | Year 2+ |
|---------|----------------------|---------|
| EC2 t2.micro | 750 hrs/mo (= 24/7) | ~$8/mo |
| EBS 30 GB | included | ~$3/mo |
| ECR | 500 MB private storage | $0.10/GB/mo over 500 MB (we'll stay under) |
| S3 | 5 GB + 20k GET + 2k PUT | $0.023/GB/mo (negligible) |
| DynamoDB | 25 GB always free + 25 RCU + 25 WCU | $0 at our volume — always-free, not 12-month |
| Secrets Manager | ❌ no free tier | $0.40/secret/mo × 4 secrets = **$1.60/mo from day one** |
| Data transfer out | 100 GB/mo | $0.09/GB after |
| Route 53 (if used) | ❌ | $0.50/zone/mo + ~$12/yr for the domain |

**Year 1 expected cost: ~$2/mo** (Secrets Manager — the only thing
without a free tier). Optionally $0 if we keep API keys in EC2 user-data
or SSM Parameter Store (which IS free) instead of Secrets Manager.

**Year 2 expected cost: ~$10–15/mo** depending on whether we have a
custom domain + Route 53.

---

## Open decisions you should weigh in on

These don't need answers right now, but they'll come up:

1. **Secrets Manager ($1.60/mo) vs SSM Parameter Store (free).** Both
   work; Secrets Manager has nicer rotation features we won't use.
   Default to SSM Parameter Store unless you'd rather have the resume
   bullet "AWS Secrets Manager" specifically.
2. **Custom domain or just the EC2 IP.** Custom domain costs ~$12/year
   plus $0.50/mo for the hosted zone. Looks more professional in the
   portfolio. EC2 IP works fine but reads as "demo project."
3. **HTTPS now or later.** A live URL that's HTTP-only looks amateurish
   for a portfolio piece. We should do HTTPS, but it adds a Caddy
   sidecar to the container or a CloudFront layer in front. Both are
   small changes.
4. **Public SPA or login-gated.** Right now the app has a simple bearer
   token. For a portfolio you want recruiters to click around without
   asking for credentials — we should add a "demo mode" that shows
   sample data, gated behind nothing.

---

## Status / progress tracker

Tick as we go.

**Phase A — Infrastructure**
- [ ] `infra/00-vars.sh`
- [ ] `infra/01-ecr.sh`
- [ ] `infra/02-s3.sh`
- [ ] `infra/03-dynamodb.sh`
- [ ] `infra/04-secrets.sh`
- [ ] `infra/05-iam.sh`
- [ ] `infra/06-ec2.sh`
- [ ] EC2 launched, smoke test passes

**Phase B — Cloud-native stores**
- [ ] `usage` → DynamoDB
- [ ] `queries` → DynamoDB
- [ ] `applied` → DynamoDB
- [ ] `letters` → DynamoDB
- [ ] `seen_jobs` → DynamoDB
- [ ] `resume` → S3

**Phase C — Secrets**
- [ ] Settings loads from Secrets Manager / SSM when on AWS

**Phase D — CI/CD**
- [ ] GitHub OIDC federated credential
- [ ] `.github/workflows/deploy.yml`
- [ ] Push-to-main auto-deploy verified

**Phase E — Polish**
- [ ] Custom domain
- [ ] HTTPS
- [ ] Soft monthly caps
- [ ] Backups (DynamoDB PITR)
