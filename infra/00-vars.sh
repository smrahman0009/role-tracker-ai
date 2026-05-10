# shellcheck shell=bash
#
# Shared variables for every infra script. Sourced, not executed.
#
# Why a sourced file instead of a config.yaml: every line is a real
# shell command you can read top-to-bottom — no hidden parsing layer
# between you and the AWS API.
#
# Usage from any other script in this directory:
#   source "$(dirname "$0")/00-vars.sh"
#
# Override anything by exporting it before sourcing, e.g. to use a
# different region for one run:
#   AWS_REGION=us-east-1 ./infra/01-ecr.sh
# -----------------------------------------------------------------------------

set -euo pipefail

# Region — keeps data residency in Canada and minimises latency for you.
: "${AWS_REGION:=ca-central-1}"
export AWS_REGION
export AWS_DEFAULT_REGION="$AWS_REGION"

# Account ID — looked up dynamically so this script works regardless of
# which AWS account you're authenticated against.
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export AWS_ACCOUNT_ID

# Logical project name — used as a prefix on every resource so they're
# easy to find in the console and easy to delete in 99-teardown.sh.
: "${PROJECT:=role-tracker}"
export PROJECT

# ----- Resource names -----------------------------------------------------

# ECR repository (private Docker image registry).
export ECR_REPO="${PROJECT}"
export ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

# S3 bucket for resume PDFs / DOCX exports. Bucket names are globally
# unique across all of AWS, so we suffix with the account ID to avoid
# collisions with anything anyone else has ever created.
export S3_BUCKET="${PROJECT}-data-${AWS_ACCOUNT_ID}"

# DynamoDB tables — one per Protocol-backed store in the app.
export DDB_APPLIED_TABLE="${PROJECT}-applied"
export DDB_LETTERS_TABLE="${PROJECT}-letters"
export DDB_USAGE_TABLE="${PROJECT}-usage"
export DDB_QUERIES_TABLE="${PROJECT}-queries"
export DDB_SEEN_JOBS_TABLE="${PROJECT}-seen-jobs"
export DDB_USERS_TABLE="${PROJECT}-users"
# Single-row table holding admin-managed cross-tenant settings
# (currently just the global hidden-publishers list).
export DDB_GLOBAL_SETTINGS_TABLE="${PROJECT}-global-settings"

# SSM Parameter Store path prefix — secrets live under /role-tracker/.
export SSM_PREFIX="/${PROJECT}"

# IAM role assumed by the EC2 instance. Gives the running container
# read/write access to the S3 bucket, DynamoDB tables, and SSM
# parameters above — and nothing else.
export IAM_ROLE_NAME="${PROJECT}-ec2-role"
export IAM_INSTANCE_PROFILE="${PROJECT}-ec2-profile"

# EC2 details.
export EC2_INSTANCE_TYPE="t2.micro"
export EC2_KEY_NAME="${PROJECT}-key"
export EC2_SECURITY_GROUP="${PROJECT}-sg"
export EC2_NAME_TAG="${PROJECT}-app"

# ----- Helpers ------------------------------------------------------------

# Print a section header in yellow when the script is run interactively.
section() {
    if [[ -t 1 ]]; then
        printf "\n\033[1;33m▸ %s\033[0m\n" "$*"
    else
        printf "\n▸ %s\n" "$*"
    fi
}

# Print success in green.
ok() {
    if [[ -t 1 ]]; then
        printf "\033[0;32m✓ %s\033[0m\n" "$*"
    else
        printf "✓ %s\n" "$*"
    fi
}

# Print a warning in cyan (used when a resource already exists — not
# an error since these scripts are idempotent).
note() {
    if [[ -t 1 ]]; then
        printf "\033[0;36m· %s\033[0m\n" "$*"
    else
        printf "· %s\n" "$*"
    fi
}
