#!/usr/bin/env bash
#
# Build → push → deploy.
#
# Five steps:
#   1. Look up the EC2 instance's public IP.
#   2. Build the Docker image locally (forced to linux/amd64 so it runs
#      on x86 EC2 even when the laptop is Apple Silicon).
#   3. Tag and push to ECR.
#   4. SSH into EC2 and `systemctl restart role-tracker`.
#   5. Wait a few seconds, then hit /api/health to confirm the
#      container is alive.
#
# Used by hand until GitHub Actions takes over in Phase D.
#
# Idempotent: each run overwrites the :latest tag in ECR and triggers
# a fresh container start.
# -----------------------------------------------------------------------------

source "$(dirname "$0")/00-vars.sh"

# ----- 1. Look up EC2 public IP -------------------------------------------

section "Looking up EC2 instance"

INSTANCE_PUBLIC_IP=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=${EC2_NAME_TAG}" \
              "Name=instance-state-name,Values=running" \
    --query "Reservations[0].Instances[0].PublicIpAddress" \
    --output text)

if [[ -z "${INSTANCE_PUBLIC_IP}" ]] || [[ "${INSTANCE_PUBLIC_IP}" == "None" ]]; then
    echo "ERROR: no running instance tagged Name=${EC2_NAME_TAG}"
    echo "Run ./infra/06-ec2.sh first."
    exit 1
fi
ok "Instance: ${INSTANCE_PUBLIC_IP}"

# ----- 2. Build the Docker image -----------------------------------------

section "Building Docker image (linux/amd64)"

# --platform forces an x86 build even when the laptop is Apple Silicon.
# Without this flag, `docker build` on an M-series Mac would produce an
# arm64 image that can't run on t2.micro (which is x86_64).
docker buildx build \
    --platform linux/amd64 \
    -t "role-tracker:local" \
    --load \
    "$(dirname "$0")/.."
ok "Image built"

# ----- 3. Tag + push to ECR ----------------------------------------------

ECR_HOST="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

section "Authenticating Docker to ECR"

aws ecr get-login-password --region "${AWS_REGION}" \
    | docker login --username AWS --password-stdin "${ECR_HOST}" \
    >/dev/null
ok "Logged in to ${ECR_HOST}"

section "Pushing image to ${ECR_URI}:latest"

docker tag role-tracker:local "${ECR_URI}:latest"
docker push "${ECR_URI}:latest"
ok "Pushed"

# ----- 4. Restart the systemd service on EC2 -----------------------------

section "Restarting role-tracker service on EC2"

# StrictHostKeyChecking=accept-new auto-trusts the host key on first
# connect, then enforces normal key checking on subsequent connects.
# Better than `=no` (which never enforces) for long-term use.
ssh -o StrictHostKeyChecking=accept-new \
    "ec2-user@${INSTANCE_PUBLIC_IP}" \
    "sudo systemctl restart role-tracker.service && sudo systemctl status role-tracker.service --no-pager -l | head -20"
ok "Service restart triggered"

# ----- 5. Smoke test ------------------------------------------------------

section "Waiting for container to come up (15s)"
sleep 15

section "Hitting /api/health"

# Try a few times — first request after a fresh `docker pull` can be
# slow because the image is being unpacked.
for attempt in 1 2 3 4 5; do
    if curl -fsS "http://${INSTANCE_PUBLIC_IP}/api/health"; then
        echo
        ok "Health check passed"
        break
    fi
    note "Attempt ${attempt} failed, retrying in 10s..."
    sleep 10
done

section "Done"

cat <<EOF
Deployed. The app is live at:
  http://${INSTANCE_PUBLIC_IP}/

Useful follow-ups:
  · Watch the container's logs:
      ssh ec2-user@${INSTANCE_PUBLIC_IP} 'sudo journalctl -u role-tracker -f'

  · See what the container is doing right now:
      ssh ec2-user@${INSTANCE_PUBLIC_IP} 'docker ps && docker logs role-tracker --tail 50'

  · Restart the container without redeploying:
      ssh ec2-user@${INSTANCE_PUBLIC_IP} 'sudo systemctl restart role-tracker'
EOF
