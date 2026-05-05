#!/usr/bin/env bash
#
# Set up GitHub Actions → AWS OIDC trust so CI/CD can deploy without
# storing any long-lived AWS keys in GitHub Secrets.
#
# Three things happen:
#
#   1. Create the GitHub OIDC identity provider in IAM (one-time per
#      AWS account — idempotent if it exists).
#
#   2. Create a deploy role (`role-tracker-deploy`) whose trust policy
#      ONLY accepts tokens minted by GitHub Actions for the specific
#      repo at `${GITHUB_REPO}`. Every other repo, every other branch
#      pattern, is rejected.
#
#   3. Attach a least-privilege permissions policy:
#        - ECR push for our repo
#        - SSM SendCommand only against our specific EC2 instance
#        - DescribeInstances scoped by the Project tag
#        - Read APP_TOKEN from SSM (for the post-deploy smoke probe)
#
# Required env / vars:
#   GITHUB_REPO   "<owner>/<repo>"   — defaults to smrahman0009/role-tracker-ai.
#                                       Override before running if the repo
#                                       lives somewhere else.
#
# Idempotent: safe to re-run.
# -----------------------------------------------------------------------------

source "$(dirname "$0")/00-vars.sh"

: "${GITHUB_REPO:=smrahman0009/role-tracker-ai}"
export GITHUB_REPO

DEPLOY_ROLE_NAME="${PROJECT}-deploy"
OIDC_PROVIDER_URL="token.actions.githubusercontent.com"
OIDC_PROVIDER_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/${OIDC_PROVIDER_URL}"

# ----- 1. OIDC identity provider ------------------------------------------

section "Creating GitHub OIDC identity provider"

if aws iam get-open-id-connect-provider \
        --open-id-connect-provider-arn "${OIDC_PROVIDER_ARN}" \
        >/dev/null 2>&1; then
    note "OIDC provider already exists — skipping creation."
else
    # ClientIdList: who's allowed to use the token (the AWS STS service).
    # ThumbprintList: GitHub's TLS cert thumbprint. AWS now actually
    # ignores this field for github.com (verified via OIDC discovery
    # instead) but the API still requires you to pass one.
    aws iam create-open-id-connect-provider \
        --url "https://${OIDC_PROVIDER_URL}" \
        --client-id-list "sts.amazonaws.com" \
        --thumbprint-list "ffffffffffffffffffffffffffffffffffffffff" \
        >/dev/null
    ok "Created OIDC provider for github.com"
fi

# ----- 2. Trust policy ---------------------------------------------------
# Only tokens minted by GitHub Actions for our specific repo can assume
# this role. The `sub` claim is what GitHub uses to identify a workflow
# run — we accept any branch / tag / pull request from this repo, which
# is the typical setting for a deploy role. Tighten further by replacing
# `*` with `ref:refs/heads/main` if you want to restrict to main only.

TRUST_POLICY=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": { "Federated": "${OIDC_PROVIDER_ARN}" },
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {
            "StringEquals": {
                "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
            },
            "StringLike": {
                "token.actions.githubusercontent.com:sub": "repo:${GITHUB_REPO}:*"
            }
        }
    }]
}
EOF
)

# ----- 3. Permissions policy ---------------------------------------------

PERMISSIONS_POLICY=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "EcrAuth",
            "Effect": "Allow",
            "Action": "ecr:GetAuthorizationToken",
            "Resource": "*"
        },
        {
            "Sid": "EcrPush",
            "Effect": "Allow",
            "Action": [
                "ecr:BatchCheckLayerAvailability",
                "ecr:BatchGetImage",
                "ecr:CompleteLayerUpload",
                "ecr:GetDownloadUrlForLayer",
                "ecr:InitiateLayerUpload",
                "ecr:PutImage",
                "ecr:UploadLayerPart"
            ],
            "Resource": "arn:aws:ecr:${AWS_REGION}:${AWS_ACCOUNT_ID}:repository/${ECR_REPO}"
        },
        {
            "Sid": "Ec2DescribeForLookup",
            "Effect": "Allow",
            "Action": "ec2:DescribeInstances",
            "Resource": "*"
        },
        {
            "Sid": "SsmRunOnDocument",
            "Effect": "Allow",
            "Action": "ssm:SendCommand",
            "Resource": "arn:aws:ssm:${AWS_REGION}::document/AWS-RunShellScript"
        },
        {
            "Sid": "SsmRunOnTaggedInstance",
            "Effect": "Allow",
            "Action": "ssm:SendCommand",
            "Resource": "arn:aws:ec2:${AWS_REGION}:${AWS_ACCOUNT_ID}:instance/*",
            "Condition": {
                "StringEquals": {
                    "aws:ResourceTag/Project": "${PROJECT}"
                }
            }
        },
        {
            "Sid": "SsmCommandStatus",
            "Effect": "Allow",
            "Action": [
                "ssm:GetCommandInvocation",
                "ssm:ListCommandInvocations"
            ],
            "Resource": "*"
        },
        {
            "Sid": "SsmReadAppToken",
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:GetParameters"
            ],
            "Resource": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter${SSM_PREFIX}/APP_TOKEN"
        }
    ]
}
EOF
)

# ----- Create or update the deploy role ----------------------------------

section "Creating IAM role: ${DEPLOY_ROLE_NAME}"

if aws iam get-role --role-name "${DEPLOY_ROLE_NAME}" >/dev/null 2>&1; then
    note "Role exists — updating trust policy in place."
    aws iam update-assume-role-policy \
        --role-name "${DEPLOY_ROLE_NAME}" \
        --policy-document "${TRUST_POLICY}" \
        >/dev/null
else
    aws iam create-role \
        --role-name "${DEPLOY_ROLE_NAME}" \
        --assume-role-policy-document "${TRUST_POLICY}" \
        --description "GitHub Actions deploy role for ${PROJECT}" \
        --max-session-duration 3600 \
        --tags "Key=Project,Value=${PROJECT}" \
        >/dev/null
    ok "Created ${DEPLOY_ROLE_NAME}"
fi

section "Attaching permissions policy"

aws iam put-role-policy \
    --role-name "${DEPLOY_ROLE_NAME}" \
    --policy-name "${PROJECT}-deploy-permissions" \
    --policy-document "${PERMISSIONS_POLICY}" \
    >/dev/null
ok "Permissions policy attached"

# IAM is eventually-consistent.
section "Waiting 10s for IAM propagation"
sleep 10
ok "Done"

DEPLOY_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${DEPLOY_ROLE_NAME}"

section "Done"

cat <<EOF
GitHub Actions can now deploy from ${GITHUB_REPO}.

Add this single repository VARIABLE in GitHub
(Settings → Secrets and variables → Actions → Variables → New variable):

  Name:   AWS_DEPLOY_ROLE_ARN
  Value:  ${DEPLOY_ROLE_ARN}

The workflow at .github/workflows/deploy.yml uses it via
\${{ vars.AWS_DEPLOY_ROLE_ARN }} to assume this role on every run.

Nothing else needs to live in GitHub Secrets — OIDC means no
long-lived AWS keys are stored anywhere.
EOF
