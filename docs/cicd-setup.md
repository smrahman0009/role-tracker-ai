# CI/CD setup

How pushes to `main` build, test, and deploy automatically — with no
long-lived AWS keys stored in GitHub.

---

## What this gives you

- `git push origin main` triggers a deploy. No more `./infra/07-deploy.sh`.
- Every PR runs the full backend test suite + frontend typecheck + lint.
  A red CI gate blocks broken code from ever reaching `main`.
- Builds happen on a fresh Ubuntu runner — same image artifact every
  time, regardless of which machine you're on.
- AWS auth uses **OIDC federated credentials**: GitHub mints a
  short-lived JWT on each run, AWS validates it via the OIDC trust
  we set up, and the deploy job gets 1-hour STS credentials. There
  are zero static AWS keys anywhere.

---

## Architecture

```
   GitHub (smrahman0009/role-tracker-ai)
        │
        │   1. push to main
        ▼
   ┌─────────────────────────────────────────────────────┐
   │ GitHub Actions: deploy.yml                          │
   │                                                     │
   │   • OIDC token issued by github.com                 │
   │   • configure-aws-credentials assumes               │
   │       arn:aws:iam::ACCT:role/role-tracker-deploy    │
   │     (trust policy validates the token's `sub`       │
   │      claim matches our exact repo)                  │
   │                                                     │
   │   • docker buildx → push to ECR                     │
   │   • aws ssm send-command "systemctl restart …"      │
   │   • curl /api/health to confirm                     │
   └─────────────────────────────────────────────────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │  AWS account         │
                   │   - ECR              │  ← image lands
                   │   - EC2              │  ← restart triggered
                   │   - DynamoDB / S3 /  │
                   │     SSM (read by    │
                   │     the container)   │
                   └──────────────────────┘
```

No SSH from CI. No AWS access keys in GitHub. The deploy role can
only push to *our* ECR repo and only restart *our* tagged EC2
instance — least privilege all the way down.

---

## Files involved

| File | Role |
|------|------|
| [`infra/08-github-oidc.sh`](../infra/08-github-oidc.sh) | One-time setup: creates the GitHub OIDC identity provider in IAM, the deploy role, and its scoped permissions policy. Idempotent — re-runnable. |
| [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | Lint + test + frontend typecheck. Runs on every push and PR. Required to be green for `main` to accept merges (once you turn on branch protection). |
| [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) | Build → push → restart → smoke test. Runs on every push to `main`, and can be triggered manually from the GitHub UI ("Actions" tab → "Deploy" → "Run workflow"). |

---

## One-time GitHub setup

After running `./infra/08-github-oidc.sh`, the script prints an ARN.
Add it to GitHub once:

1. Go to your repo → **Settings** → **Secrets and variables** →
   **Actions** → **Variables** tab → **New repository variable**.
2. Name: `AWS_DEPLOY_ROLE_ARN`
3. Value: the ARN the script printed
   (`arn:aws:iam::941894778585:role/role-tracker-deploy`).

It's a *variable* — not a secret — because the role ARN isn't
sensitive. Anyone seeing the ARN still can't assume the role
without holding a valid GitHub OIDC token for *this exact repo*.

That's the only credential GitHub needs. There's no
`AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` to manage, rotate, or
worry about.

---

## What happens on a deploy

1. **Checkout** — pulls the commit being deployed.
2. **`aws-actions/configure-aws-credentials@v4`** — exchanges the
   OIDC token for AWS STS credentials. Verified with
   `aws sts get-caller-identity` in the next step.
3. **`amazon-ecr-login`** — Docker auth against ECR.
4. **`docker buildx`** — builds for `linux/amd64` (matters because
   GitHub runners are x86 and t2.micro is x86, but we'd hit issues
   if either side ever switched). Layers are cached in the GitHub
   Actions cache, so subsequent builds are fast.
5. **Push** with two tags: `:latest` (always) and `:<commit-sha>` (so
   we can roll back by editing systemd to pin a specific tag).
6. **Look up the EC2 instance ID** by Name tag.
7. **`aws ssm send-command`** runs
   `systemctl restart role-tracker.service` on the instance.
   This pulls the new image (the systemd unit's `ExecStartPre` does
   `docker pull`) and starts the container. No SSH involved.
8. **Wait for the command to finish.** If `systemctl restart` exits
   non-zero, the workflow fails and prints the SSM output.
9. **`curl /api/health`** with retries. If five attempts in 50
   seconds all fail, the workflow fails. This catches "image started
   but crashed on boot" cases.
10. **Summary** — image SHA + instance ID + public URL written to
    the workflow run summary so it shows on the run's main page.

---

## Watching a deploy

After pushing to `main`:

```bash
git push origin main
```

Open the **Actions** tab in GitHub. You'll see the **Deploy** workflow
running. Click into it for live logs. End-to-end, expect ~3 minutes
on a clean cache, ~90 seconds with cache hits.

The summary panel at the top shows the new public URL. Click it —
you should see the new code live.

---

## Rolling back

If a deploy goes bad:

**Easy path**: revert the offending commit on `main`. Push. CI
deploys the rollback automatically. Total time: a couple of minutes.

**Faster path**: SSH in and pin to a previous tag. The image was
pushed with both `:latest` and `:<commit-sha>`, so any past commit
is still in ECR (subject to the 5-image lifecycle policy).

```bash
ssh ec2-user@<ip>
sudo systemctl edit role-tracker
# Add an override that points docker pull at the older :sha tag
```

For most cases, just revert and push — that's the whole point of CI.

---

## Cost

**$0.** GitHub Actions is free for public repos and 2,000 minutes/month
for private. A typical deploy uses ~2 CI minutes. 60 deploys/month is
~120 minutes — well within the free allowance.

ECR storage is the only AWS charge that grows with deploys, and the
`:keep last 5 images` lifecycle policy from `01-ecr.sh` caps it at
~750 MB → roughly $0 at our scale.

---

## Common pitfalls

**"Could not assume role" on the configure-aws-credentials step.**
Either the `AWS_DEPLOY_ROLE_ARN` repository variable is wrong, or
the trust policy on the role doesn't match the repo path. Re-run
`./infra/08-github-oidc.sh` — the trust policy is rebuilt on each
run. Also check the variable is in the right place
(Variables, not Secrets).

**"AccessDenied" on `ssm send-command`.**
The deploy role's `aws:ResourceTag/Project` condition only allows
SSM commands against EC2 instances tagged `Project=role-tracker`. If
you re-launched the instance without that tag, re-run
`./infra/06-ec2.sh` (it tags the instance on launch).

**Health check fails after restart.**
SSH in: `sudo journalctl -u role-tracker -n 50`. Most common
cause: a missing SSM parameter the new code expects. Re-run
`./infra/04-ssm.sh` to refresh secrets, then trigger a manual
deploy from the Actions tab.

**Frontend typecheck fails in CI but works locally.**
CI runs against a fresh `npm ci` install — your local node_modules
might be stale. Run `cd frontend && rm -rf node_modules && npm ci`
to reproduce locally.
