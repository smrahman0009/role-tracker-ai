#!/usr/bin/env bash
#
# Upload secrets to AWS Systems Manager Parameter Store.
#
# Why SSM Parameter Store (not Secrets Manager):
#   - Free up to 10,000 standard parameters (Secrets Manager is $0.40/secret/mo).
#   - Same KMS-backed encryption-at-rest when you use SecureString type.
#   - Same IAM-based access control.
#   - For our use case (read once at container startup, never rotate),
#     Secrets Manager's auto-rotation features are wasted spend.
#
# We read values from your local .env file so you don't have to retype
# them. Anything missing is prompted interactively.
#
# Each secret lands at:    /role-tracker/{NAME}
# Type:                    SecureString (KMS-encrypted)
# IAM access:              read-only, granted to the EC2 role in 05-iam.sh
#
# Idempotent: re-running overwrites existing parameters in place.
# -----------------------------------------------------------------------------

source "$(dirname "$0")/00-vars.sh"

# Load values from .env if present. We do this in a subshell-safe way:
# `set -a` exports every variable that gets defined while it's on.
ENV_FILE="$(dirname "$0")/../.env"
if [[ -f "${ENV_FILE}" ]]; then
    note "Loading values from ${ENV_FILE}"
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

# Helper: upload one parameter. Reads value from the named env var; if
# unset or empty, prompts for it. Hides input so terminal scrollback
# doesn't leak the secret.
upload_param() {
    local name="$1"
    local env_var="$2"
    local description="$3"

    local value="${!env_var:-}"

    if [[ -z "${value}" ]]; then
        printf "  Enter value for %s: " "${env_var}"
        read -rs value
        echo
    fi

    if [[ -z "${value}" ]]; then
        printf "  (skipped — no value provided)\n"
        return
    fi

    aws ssm put-parameter \
        --name "${SSM_PREFIX}/${name}" \
        --description "${description}" \
        --value "${value}" \
        --type SecureString \
        --overwrite \
        --tags "Key=Project,Value=${PROJECT}" \
        >/dev/null 2>&1 || \
    aws ssm put-parameter \
        --name "${SSM_PREFIX}/${name}" \
        --description "${description}" \
        --value "${value}" \
        --type SecureString \
        --overwrite \
        >/dev/null
    # The first try includes tags (only valid on create). If the param
    # already exists, `--overwrite` is incompatible with tagging, so we
    # fall through to a second call without --tags.

    ok "${SSM_PREFIX}/${name}"
}

section "Uploading secrets to SSM Parameter Store"

upload_param "ANTHROPIC_API_KEY"   "ANTHROPIC_API_KEY"   "Anthropic Claude API key (cover-letter agent + Haiku passes)"
upload_param "OPENAI_API_KEY"      "OPENAI_API_KEY"      "OpenAI API key (text-embedding-3-small for matching)"
upload_param "JSEARCH_RAPIDAPI_KEY" "JSEARCH_RAPIDAPI_KEY" "RapidAPI key for the JSearch (Google for Jobs) endpoint"
upload_param "APP_TOKEN"           "APP_TOKEN"           "Bearer token required by the API (skipped in dev when empty)"

section "Done"

cat <<EOF
Parameters under ${SSM_PREFIX}/ — list them with:
  aws ssm get-parameters-by-path --path "${SSM_PREFIX}" --query "Parameters[].Name"

Read one (decrypted) for verification:
  aws ssm get-parameter \\
    --name "${SSM_PREFIX}/ANTHROPIC_API_KEY" \\
    --with-decryption \\
    --query "Parameter.Value" --output text

The EC2 role created in 05-iam.sh will get read-only access to these.
The container itself will load them at startup via boto3.
EOF
