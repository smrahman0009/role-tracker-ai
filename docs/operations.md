# Operating the live deployment

Day-to-day operations for the deployed Role Tracker AI app on AWS.
This is reference material for the *operator* (you), not for someone
reading the project for the first time. Things you'll forget by the
time you need them and will be glad you wrote down.

---

## Recovering the bearer token

The live app is gated by a bearer token (`APP_TOKEN`). Browsers
remember it in `localStorage` after first sign-in, so you rarely see
it. To retrieve it on a new browser / device / cleared cookies:

```bash
# 1. From SSM Parameter Store — the canonical source of truth
aws ssm get-parameter \
  --name /role-tracker/APP_TOKEN \
  --with-decryption \
  --query Parameter.Value \
  --output text

# 2. From your local .env file
grep APP_TOKEN .env
```

3. **AWS Console** → Systems Manager → Parameter Store →
   `/role-tracker/APP_TOKEN` → click **Show** under Value.

### Rotating the token

If the token leaks, gets pasted in a screenshot, or you just want a
fresh one:

```bash
# Generate a new random token
NEW_TOKEN=$(openssl rand -base64 32)

# Replace it in SSM
aws ssm put-parameter \
  --name /role-tracker/APP_TOKEN \
  --value "$NEW_TOKEN" \
  --type SecureString \
  --overwrite

# Replace it in your local .env so dev still matches
sed -i.bak "s|^APP_TOKEN=.*|APP_TOKEN=$NEW_TOKEN|" .env

# Push to main — CI/CD redeploys, container picks up the new value
# from SSM at startup
git commit --allow-empty -m "rotate APP_TOKEN"
git push
```

After deploy completes, the old token stops working and the new one
takes over. Update your password manager.

---

## Inspecting the running container

### Logs

```bash
# Live tail of the systemd unit (most useful)
ssh ec2-user@<public-ip> 'sudo journalctl -u role-tracker -f'

# Last N lines of the container's stdout
ssh ec2-user@<public-ip> 'docker logs role-tracker --tail 100'

# Same but follow
ssh ec2-user@<public-ip> 'docker logs role-tracker -f'
```

### State

```bash
# Container running?
ssh ec2-user@<public-ip> 'sudo systemctl status role-tracker'

# What image SHA is it running?
ssh ec2-user@<public-ip> 'docker inspect role-tracker --format "{{.Config.Image}}"'
```

### Restart without redeploy

```bash
ssh ec2-user@<public-ip> 'sudo systemctl restart role-tracker'
# → docker stops, docker pulls :latest, docker runs
```

---

## Looking up the public IP

The instance's public IP changes if you stop/start it. Always look
it up by Name tag rather than caching it:

```bash
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=role-tracker-app" \
            "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text
```

---

## Updating SSH access from a new network

When you change Wi-Fi networks (coffee shop, travel, etc.), your
public IP changes and the security group rejects you on port 22.
Re-run [`infra/06-ec2.sh`](../infra/06-ec2.sh) — it adds your
current IP to the SG (the old rule stays in place; remove old ones
manually in the EC2 console if you want to keep the SG tidy).

---

## Force-redeploying without a code change

Three options, in order of cleanness:

```bash
# 1. Empty commit, push, CI re-runs
git commit --allow-empty -m "redeploy"
git push

# 2. Re-run the deploy workflow from the GitHub UI
# Actions → Deploy → Run workflow → Run workflow

# 3. Manual deploy from your laptop (bypasses CI)
./infra/07-deploy.sh
```

---

## Tearing down the AWS stack

If you ever want to walk away from the AWS bill:

```bash
# Stop being charged for EC2 / EBS immediately
aws ec2 terminate-instances --instance-ids <id>

# Delete the rest (idempotent — see infra/99-teardown.sh when written)
aws ecr delete-repository --repository-name role-tracker --force
aws s3 rb s3://role-tracker-data-<acct> --force
for t in applied letters usage queries seen-jobs; do
  aws dynamodb delete-table --table-name role-tracker-$t
done
```

DynamoDB tables and S3 are free at our scale anyway — only EC2 has a
non-trivial monthly cost after the free tier expires.

---

## Bumping a dependency

Backend:
```bash
uv add anthropic@latest      # or another package
uv run pytest -q             # confirm nothing broke
git commit -am "chore: bump anthropic"
git push                     # CI/CD redeploys
```

Frontend:
```bash
cd frontend
npm update                   # respects existing semver ranges
npm run build                # confirm it still bundles
git commit -am "chore: npm update"
git push
```
