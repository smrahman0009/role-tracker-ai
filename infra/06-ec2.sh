#!/usr/bin/env bash
#
# Launch the EC2 t2.micro that runs the Docker container.
#
# Five things happen, in order:
#
#   1. Import your local SSH public key as an EC2 key pair so you can
#      `ssh ec2-user@<public-ip>` after launch.
#
#   2. Create a security group (a stateful firewall around the
#      instance) that allows:
#        - port 22 (SSH) inbound, only from your current public IP
#        - port 80 (HTTP) inbound, from anywhere
#        - all outbound traffic
#
#   3. Look up the latest Amazon Linux 2023 AMI for our region. We use
#      AWS's public SSM parameter for this so we always get the
#      current patched version, not a hard-coded ID that will go stale.
#
#   4. Build a user-data script — runs once on first boot inside the
#      VM. It installs Docker, logs into ECR, sets up a systemd unit
#      that pulls + runs our container. Until we push an image
#      (handled in 07-deploy.sh), the unit will fail-and-retry, which
#      is fine.
#
#   5. Launch the instance, tag it, attach the IAM instance profile
#      from 05-iam.sh, wait for "running" state, and print the public
#      IP / SSH command.
#
# Idempotent: re-running won't launch a second instance — it stops at
# step 5 if an instance with our Name tag already exists.
# -----------------------------------------------------------------------------

source "$(dirname "$0")/00-vars.sh"

# ----- 1. SSH key pair ---------------------------------------------------

# Find an SSH public key — try common names first, then fall back to
# the first id_*.pub or *_ed25519.pub the shell can match. Override by
# setting PUBLIC_KEY_FILE in the environment before running.
if [[ -z "${PUBLIC_KEY_FILE:-}" ]]; then
    candidates=(
        "${HOME}/.ssh/id_ed25519.pub"
        "${HOME}/.ssh/id_rsa.pub"
    )
    # Glob for anything else that looks like a public key.
    shopt -s nullglob
    candidates+=( "${HOME}"/.ssh/id_*.pub "${HOME}"/.ssh/*_ed25519.pub )
    shopt -u nullglob

    for candidate in "${candidates[@]}"; do
        if [[ -f "${candidate}" ]]; then
            PUBLIC_KEY_FILE="${candidate}"
            break
        fi
    done
fi

if [[ -z "${PUBLIC_KEY_FILE:-}" ]] || [[ ! -f "${PUBLIC_KEY_FILE}" ]]; then
    echo "ERROR: no SSH public key found in ~/.ssh/"
    echo "Generate one with:  ssh-keygen -t ed25519"
    echo "Or point at an existing one:  PUBLIC_KEY_FILE=~/.ssh/your-key.pub ./infra/06-ec2.sh"
    exit 1
fi

note "Using SSH public key: ${PUBLIC_KEY_FILE}"

section "Importing SSH public key: ${EC2_KEY_NAME}"

if aws ec2 describe-key-pairs --key-names "${EC2_KEY_NAME}" >/dev/null 2>&1; then
    note "Key pair already exists — skipping import."
else
    aws ec2 import-key-pair \
        --key-name "${EC2_KEY_NAME}" \
        --public-key-material "fileb://${PUBLIC_KEY_FILE}" \
        >/dev/null
    ok "Imported ${PUBLIC_KEY_FILE} as ${EC2_KEY_NAME}"
fi

# ----- 2. Security group --------------------------------------------------

section "Creating security group: ${EC2_SECURITY_GROUP}"

SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=${EC2_SECURITY_GROUP}" \
    --query "SecurityGroups[0].GroupId" \
    --output text 2>/dev/null || echo "None")

if [[ "${SG_ID}" == "None" ]] || [[ -z "${SG_ID}" ]]; then
    SG_ID=$(aws ec2 create-security-group \
        --group-name "${EC2_SECURITY_GROUP}" \
        --description "Inbound SSH (your IP) + HTTP for ${PROJECT}" \
        --tag-specifications "ResourceType=security-group,Tags=[{Key=Project,Value=${PROJECT}}]" \
        --query "GroupId" \
        --output text)
    ok "Created ${EC2_SECURITY_GROUP} (${SG_ID})"
else
    note "Security group already exists (${SG_ID})."
fi

# Look up our current public IP — only this address gets to SSH.
MY_IP="$(curl -fsS https://checkip.amazonaws.com)/32"

section "Allowing SSH (port 22) from ${MY_IP}"

aws ec2 authorize-security-group-ingress \
    --group-id "${SG_ID}" \
    --protocol tcp --port 22 \
    --cidr "${MY_IP}" \
    >/dev/null 2>&1 \
    && ok "SSH rule added" \
    || note "SSH rule already present."

section "Allowing HTTP (port 80) from anywhere"

aws ec2 authorize-security-group-ingress \
    --group-id "${SG_ID}" \
    --protocol tcp --port 80 \
    --cidr "0.0.0.0/0" \
    >/dev/null 2>&1 \
    && ok "HTTP rule added" \
    || note "HTTP rule already present."

# ----- 3. Find the latest Amazon Linux 2023 AMI ---------------------------

section "Looking up latest Amazon Linux 2023 AMI"

AMI_ID=$(aws ssm get-parameter \
    --name "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64" \
    --query "Parameter.Value" \
    --output text)
ok "AMI: ${AMI_ID}"

# ----- 4. Build the user-data bootstrap script ----------------------------

# This runs once, on first boot. It installs Docker + the AWS CLI,
# enables ECR auth via the instance role, and creates a systemd unit
# that keeps the container running across reboots. The unit will
# crash-loop until we push an image to ECR — that's expected and fine.

USER_DATA=$(cat <<'USER_DATA_EOF'
#!/bin/bash
set -e
exec > /var/log/user-data.log 2>&1

echo "[user-data] starting at $(date)"

# Update + install Docker.
dnf update -y
dnf install -y docker
systemctl enable --now docker
usermod -aG docker ec2-user

# Map port 80 (where users connect) to the container's port 8000.
# We use iptables instead of running uvicorn as root — port 80 is
# privileged and our container deliberately runs as a non-root user.
# We need OUTPUT too because with --network=host the container shares
# the host's loopback, so health checks hitting 127.0.0.1:80 also
# need redirecting to 8000.
iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000
iptables -t nat -A OUTPUT -d 127.0.0.1 -p tcp --dport 80 -j REDIRECT --to-port 8000
iptables-save > /etc/sysconfig/iptables 2>/dev/null || true

# Install a systemd unit that pulls + runs the role-tracker container.
# Env vars come from the instance role — the boto3 client inside the
# container picks up credentials automatically from EC2 metadata.
cat > /etc/systemd/system/role-tracker.service <<'UNIT_EOF'
[Unit]
Description=Role Tracker AI container
Wants=docker.service network-online.target
After=docker.service network-online.target

[Service]
Type=simple
Restart=always
RestartSec=10
TimeoutStartSec=0

# Always pull the latest image before starting (so a redeploy is just
# `systemctl restart role-tracker`).
ExecStartPre=-/usr/bin/docker stop role-tracker
ExecStartPre=-/usr/bin/docker rm role-tracker
ExecStartPre=/bin/bash -c '/usr/bin/aws ecr get-login-password --region __REGION__ | /usr/bin/docker login --username AWS --password-stdin __ECR_HOST__'
ExecStartPre=/usr/bin/docker pull __ECR_URI__:latest

ExecStart=/usr/bin/docker run --rm --name role-tracker \
    --network=host \
    -e AWS_REGION=__REGION__ \
    -e STORAGE_BACKEND=aws \
    -e SSM_PREFIX=__SSM_PREFIX__ \
    -e S3_BUCKET=__S3_BUCKET__ \
    -e DDB_APPLIED_TABLE=__DDB_APPLIED__ \
    -e DDB_LETTERS_TABLE=__DDB_LETTERS__ \
    -e DDB_USAGE_TABLE=__DDB_USAGE__ \
    -e DDB_QUERIES_TABLE=__DDB_QUERIES__ \
    -e DDB_SEEN_JOBS_TABLE=__DDB_SEEN_JOBS__ \
    -e DDB_USERS_TABLE=__DDB_USERS__ \
    -e DDB_GLOBAL_SETTINGS_TABLE=__DDB_GLOBAL_SETTINGS__ \
    __ECR_URI__:latest

ExecStop=/usr/bin/docker stop role-tracker

[Install]
WantedBy=multi-user.target
UNIT_EOF

# Install the AWS CLI v2 (Amazon Linux 2023 ships v2 in default repos
# but we explicitly ensure it's there for ECR auth).
dnf install -y awscli || dnf install -y aws-cli

systemctl daemon-reload
systemctl enable role-tracker.service

# Don't `start` here — image isn't pushed yet on first launch. The
# 07-deploy.sh script will push the image then start the service.
echo "[user-data] complete at $(date)"
USER_DATA_EOF
)

# Substitute project-specific values into the user-data template.
USER_DATA="${USER_DATA//__REGION__/${AWS_REGION}}"
USER_DATA="${USER_DATA//__ECR_HOST__/${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com}"
USER_DATA="${USER_DATA//__ECR_URI__/${ECR_URI}}"
USER_DATA="${USER_DATA//__SSM_PREFIX__/${SSM_PREFIX}}"
USER_DATA="${USER_DATA//__S3_BUCKET__/${S3_BUCKET}}"
USER_DATA="${USER_DATA//__DDB_APPLIED__/${DDB_APPLIED_TABLE}}"
USER_DATA="${USER_DATA//__DDB_LETTERS__/${DDB_LETTERS_TABLE}}"
USER_DATA="${USER_DATA//__DDB_USAGE__/${DDB_USAGE_TABLE}}"
USER_DATA="${USER_DATA//__DDB_QUERIES__/${DDB_QUERIES_TABLE}}"
USER_DATA="${USER_DATA//__DDB_SEEN_JOBS__/${DDB_SEEN_JOBS_TABLE}}"
USER_DATA="${USER_DATA//__DDB_USERS__/${DDB_USERS_TABLE}}"
USER_DATA="${USER_DATA//__DDB_GLOBAL_SETTINGS__/${DDB_GLOBAL_SETTINGS_TABLE:-role-tracker-global-settings}}"

# ----- 5. Launch the instance ---------------------------------------------

section "Checking for existing instance tagged ${EC2_NAME_TAG}"

EXISTING_INSTANCE=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=${EC2_NAME_TAG}" \
              "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text 2>/dev/null || echo "None")

if [[ "${EXISTING_INSTANCE}" != "None" ]] && [[ -n "${EXISTING_INSTANCE}" ]]; then
    INSTANCE_ID="${EXISTING_INSTANCE}"
    note "Instance ${INSTANCE_ID} already exists — skipping launch."
else
    section "Launching ${EC2_INSTANCE_TYPE} (${EC2_NAME_TAG})"

    INSTANCE_ID=$(aws ec2 run-instances \
        --image-id "${AMI_ID}" \
        --instance-type "${EC2_INSTANCE_TYPE}" \
        --key-name "${EC2_KEY_NAME}" \
        --security-group-ids "${SG_ID}" \
        --iam-instance-profile "Name=${IAM_INSTANCE_PROFILE}" \
        --user-data "${USER_DATA}" \
        --tag-specifications \
            "ResourceType=instance,Tags=[{Key=Name,Value=${EC2_NAME_TAG}},{Key=Project,Value=${PROJECT}}]" \
        --metadata-options "HttpTokens=required,HttpEndpoint=enabled,HttpPutResponseHopLimit=2" \
        --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":20,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
        --query "Instances[0].InstanceId" \
        --output text)
    ok "Launched ${INSTANCE_ID}"
fi

# ----- Wait for the instance to be running and SSH-ready ------------------

section "Waiting for instance to reach 'running' state"
aws ec2 wait instance-running --instance-ids "${INSTANCE_ID}"
ok "Instance is running"

PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids "${INSTANCE_ID}" \
    --query "Reservations[0].Instances[0].PublicIpAddress" \
    --output text)

section "Done"

cat <<EOF
EC2 instance is running:
  · Instance ID:  ${INSTANCE_ID}
  · Public IP:    ${PUBLIC_IP}
  · Type:         ${EC2_INSTANCE_TYPE}
  · AMI:          ${AMI_ID} (Amazon Linux 2023)
  · Disk:         20 GB gp3
  · Role:         ${IAM_INSTANCE_PROFILE}

The user-data bootstrap is still running in the background (~2 min).
You can watch it from your laptop:

  ssh -o StrictHostKeyChecking=no ec2-user@${PUBLIC_IP} \\
      'sudo tail -f /var/log/user-data.log'

When that prints "[user-data] complete", Docker + the systemd unit are
installed but the container can't start yet — we haven't pushed an image
to ECR. Next up: ./infra/07-deploy.sh
EOF
