#!/usr/bin/env bash
#
# Create the IAM role and instance profile that EC2 will assume.
#
# This is the security boundary: the role's policy is the *complete*
# list of AWS actions our running container is allowed to take. If the
# container is ever compromised, the attacker can do exactly these
# things and nothing else.
#
# Two-layer object model AWS uses for EC2 permissions:
#   - "Role"             — the policy bundle (what's allowed)
#   - "Instance profile" — the wrapper EC2 actually attaches to a VM
#                          (a 1:1 container around the role)
# Both must exist with matching names.
#
# Permissions granted (least-privilege — narrow ARNs, not wildcards):
#   - ECR  : pull Docker images (read-only)
#   - S3   : read/write/list ONLY our resume bucket
#   - DynamoDB : read/write items ONLY in our five tables
#   - SSM  : read parameters ONLY under /role-tracker/*
#   - KMS  : decrypt SSM SecureStrings using the AWS-managed SSM key
#   - CloudWatch Logs : write logs (so we can debug from the console)
#
# Idempotent: safe to re-run.
# -----------------------------------------------------------------------------

source "$(dirname "$0")/00-vars.sh"

# ----- Trust policy: who can assume this role? ----------------------------
# Only the EC2 service. No humans, no other accounts, no other services.

TRUST_POLICY=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": { "Service": "ec2.amazonaws.com" },
        "Action": "sts:AssumeRole"
    }]
}
EOF
)

# ----- Permissions policy: what can the role do? --------------------------
# Resource ARNs are interpolated from 00-vars.sh so the policy targets
# our specific bucket / tables / parameters and nothing else.

PERMISSIONS_POLICY=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "EcrPullImage",
            "Effect": "Allow",
            "Action": [
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage"
            ],
            "Resource": "*"
        },
        {
            "Sid": "S3ResumeBucket",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::${S3_BUCKET}",
                "arn:aws:s3:::${S3_BUCKET}/*"
            ]
        },
        {
            "Sid": "DynamoDBTables",
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:BatchGetItem",
                "dynamodb:BatchWriteItem"
            ],
            "Resource": [
                "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DDB_APPLIED_TABLE}",
                "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DDB_LETTERS_TABLE}",
                "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DDB_USAGE_TABLE}",
                "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DDB_QUERIES_TABLE}",
                "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DDB_SEEN_JOBS_TABLE}",
                "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DDB_JOBS_TABLE}",
                "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DDB_USERS_TABLE}",
                "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DDB_GLOBAL_SETTINGS_TABLE:-role-tracker-global-settings}"
            ]
        },
        {
            "Sid": "SsmReadOurParameters",
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:GetParametersByPath"
            ],
            "Resource": [
                "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter${SSM_PREFIX}",
                "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter${SSM_PREFIX}/*"
            ]
        },
        {
            "Sid": "KmsDecryptSsm",
            "Effect": "Allow",
            "Action": "kms:Decrypt",
            "Resource": "*",
            "Condition": {
                "StringEquals": {
                    "kms:ViaService": "ssm.${AWS_REGION}.amazonaws.com"
                }
            }
        },
        {
            "Sid": "CloudWatchLogs",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*"
        }
    ]
}
EOF
)

# ----- Create the role ----------------------------------------------------

section "Creating IAM role: ${IAM_ROLE_NAME}"

if aws iam get-role --role-name "${IAM_ROLE_NAME}" >/dev/null 2>&1; then
    note "Role already exists — updating trust policy in place."
    aws iam update-assume-role-policy \
        --role-name "${IAM_ROLE_NAME}" \
        --policy-document "${TRUST_POLICY}" \
        >/dev/null
else
    aws iam create-role \
        --role-name "${IAM_ROLE_NAME}" \
        --assume-role-policy-document "${TRUST_POLICY}" \
        --description "EC2 role for ${PROJECT} container" \
        --tags "Key=Project,Value=${PROJECT}" \
        >/dev/null
    ok "Created ${IAM_ROLE_NAME}"
fi

# ----- Attach the permissions policy as an inline policy ------------------
# Inline (not managed) because this policy is specific to this role and
# we want it to live and die with the role. AWS removes inline policies
# automatically when the role is deleted.

section "Attaching permissions policy"

aws iam put-role-policy \
    --role-name "${IAM_ROLE_NAME}" \
    --policy-name "${PROJECT}-permissions" \
    --policy-document "${PERMISSIONS_POLICY}" \
    >/dev/null
ok "Permissions policy attached"

# Attach AWS's managed policy so the SSM Agent on the instance can
# register with Systems Manager (UpdateInstanceInformation +
# ssmmessages + ec2messages). Without this, GitHub Actions' Run
# Command-based deploys fail with "InvalidInstanceId".
section "Attaching AmazonSSMManagedInstanceCore"

aws iam attach-role-policy \
    --role-name "${IAM_ROLE_NAME}" \
    --policy-arn "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore" \
    >/dev/null
ok "Managed policy attached"

# ----- Create the instance profile ---------------------------------------
# EC2 attaches "instance profiles", not roles directly. The 1:1 wrapper
# is a quirk of how AWS evolved this feature.

section "Creating instance profile: ${IAM_INSTANCE_PROFILE}"

if aws iam get-instance-profile \
        --instance-profile-name "${IAM_INSTANCE_PROFILE}" >/dev/null 2>&1; then
    note "Instance profile already exists — skipping creation."
else
    aws iam create-instance-profile \
        --instance-profile-name "${IAM_INSTANCE_PROFILE}" \
        --tags "Key=Project,Value=${PROJECT}" \
        >/dev/null
    ok "Created ${IAM_INSTANCE_PROFILE}"
fi

# ----- Add the role to the instance profile -------------------------------

section "Linking role to instance profile"

# This call fails with EntityAlreadyExists if it's already linked, so
# we tolerate that.
if aws iam add-role-to-instance-profile \
        --instance-profile-name "${IAM_INSTANCE_PROFILE}" \
        --role-name "${IAM_ROLE_NAME}" 2>/dev/null; then
    ok "Role linked to instance profile"
else
    note "Role already linked to instance profile."
fi

# IAM is eventually-consistent — it can take a few seconds for the role
# to propagate everywhere. EC2 launch sometimes fails if we proceed
# immediately, so wait a bit.
section "Waiting 10s for IAM propagation"
sleep 10
ok "Done waiting"

section "Done"

cat <<EOF
IAM resources created:
  · Role:             ${IAM_ROLE_NAME}
  · Instance profile: ${IAM_INSTANCE_PROFILE}
  · Trust:            ec2.amazonaws.com only
  · Permissions:      least-privilege scoped to this project's
                      bucket, tables, and SSM parameters

Verify in the console:
  https://us-east-1.console.aws.amazon.com/iam/home#/roles/details/${IAM_ROLE_NAME}

(IAM is a global service — no region selector.)
EOF
