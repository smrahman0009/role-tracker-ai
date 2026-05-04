#!/usr/bin/env bash
#
# Create the ECR repository where our Docker image lives.
#
# ECR (Elastic Container Registry) is AWS's private Docker registry —
# the equivalent of Docker Hub but inside your AWS account. EC2 will
# pull the image from here at deploy time.
#
# What this script does:
#   1. Creates the ECR repo (idempotent — silent if it already exists).
#   2. Sets a lifecycle policy: keep the 5 most recent images, expire
#      the rest. Without this, every deploy would leave the previous
#      image lying around forever, eating into your 500 MB free tier.
#   3. Prints the URI you'd use to push images to it.
#
# Idempotent: safe to re-run.
# -----------------------------------------------------------------------------

source "$(dirname "$0")/00-vars.sh"

section "Creating ECR repository: ${ECR_REPO}"

if aws ecr describe-repositories \
        --repository-names "${ECR_REPO}" >/dev/null 2>&1; then
    note "Repository already exists — skipping creation."
else
    aws ecr create-repository \
        --repository-name "${ECR_REPO}" \
        --image-scanning-configuration scanOnPush=true \
        --image-tag-mutability MUTABLE \
        >/dev/null
    ok "Created ${ECR_REPO}"
fi

section "Applying lifecycle policy (keep last 5 images)"

# JSON inline because it's small. AWS reads this and auto-deletes
# images beyond the 5 most recent.
aws ecr put-lifecycle-policy \
    --repository-name "${ECR_REPO}" \
    --lifecycle-policy-text '{
        "rules": [
            {
                "rulePriority": 1,
                "description": "Keep last 5 images",
                "selection": {
                    "tagStatus": "any",
                    "countType": "imageCountMoreThan",
                    "countNumber": 5
                },
                "action": { "type": "expire" }
            }
        ]
    }' \
    >/dev/null
ok "Lifecycle policy applied"

section "Done"

cat <<EOF
ECR URI:
  ${ECR_URI}

To push your local image, run:
  aws ecr get-login-password --region ${AWS_REGION} \\
    | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

  docker tag role-tracker:local ${ECR_URI}:latest
  docker push ${ECR_URI}:latest

(We'll automate this in infra/07-deploy.sh later.)
EOF
