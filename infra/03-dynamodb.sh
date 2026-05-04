#!/usr/bin/env bash
#
# Create the five DynamoDB tables — one per Protocol-backed store in
# the app. Each table has the same shape:
#
#   PK (HASH):  user_id   — partitions data by user
#   SK (RANGE): item_id   — sort key within a user's partition
#                           (job_id, year_month, query_id, etc.)
#
# This shape makes "list all of X for user Y" a single Query call,
# which is the most common access pattern across the app.
#
# Billing: PAY_PER_REQUEST (on-demand). No capacity planning, no
# minimum charge, scales to zero. AWS's always-free DynamoDB tier
# covers 25 GB of storage, which is far more than we'll use.
#
# Idempotent: safe to re-run.
# -----------------------------------------------------------------------------

source "$(dirname "$0")/00-vars.sh"

create_table() {
    local table_name="$1"
    local sk_name="$2"
    local description="$3"

    section "Creating table: ${table_name}  (${description})"

    if aws dynamodb describe-table --table-name "${table_name}" >/dev/null 2>&1; then
        note "Table already exists — skipping creation."
        return
    fi

    aws dynamodb create-table \
        --table-name "${table_name}" \
        --attribute-definitions \
            "AttributeName=user_id,AttributeType=S" \
            "AttributeName=${sk_name},AttributeType=S" \
        --key-schema \
            "AttributeName=user_id,KeyType=HASH" \
            "AttributeName=${sk_name},KeyType=RANGE" \
        --billing-mode PAY_PER_REQUEST \
        --tags "Key=Project,Value=${PROJECT}" \
        >/dev/null

    # Wait for the table to leave CREATING state before returning —
    # without this, a fast-running follow-up script could try to use
    # the table while it's still provisioning.
    aws dynamodb wait table-exists --table-name "${table_name}"
    ok "Created ${table_name}"
}

# -----------------------------------------------------------------------------
# applied — every job a user has marked as applied, with the rich record
# captured at apply time (applied_at, resume snapshot, letter version).
#
# Item shape:
#   user_id (S)         — partition key
#   job_id  (S)         — sort key
#   applied_at, resume_filename, resume_sha256, letter_version_used
# -----------------------------------------------------------------------------
create_table "${DDB_APPLIED_TABLE}"   "job_id"     "user → job → application record"

# -----------------------------------------------------------------------------
# letters — every saved cover-letter version. Sort key combines job_id
# and version so list-versions-for-job is a Query with a prefix.
#
# Item shape:
#   user_id (S)
#   job_version (S)     — formatted as "{job_id}#{version:04d}"
#   text, strategy, critique, refinement_index, edited_by_user, …
# -----------------------------------------------------------------------------
create_table "${DDB_LETTERS_TABLE}"   "job_version" "user → job#version → letter"

# -----------------------------------------------------------------------------
# usage — per-user, per-month rollups for the quota dashboard.
#
# Item shape:
#   user_id (S)
#   year_month (S)      — "YYYY-MM"
#   jsearch_calls, feature_calls (M / map)
# -----------------------------------------------------------------------------
create_table "${DDB_USAGE_TABLE}"     "year_month" "user → month → usage rollup"

# -----------------------------------------------------------------------------
# queries — the user's saved searches.
#
# Item shape:
#   user_id (S)
#   query_id (S)
#   what, where, enabled
# -----------------------------------------------------------------------------
create_table "${DDB_QUERIES_TABLE}"   "query_id"   "user → query → saved search"

# -----------------------------------------------------------------------------
# seen-jobs — long-lived per-user index of every job we've ever seen.
# This is the table the detail page, applied page, manual list, etc.
# all read from. Will be the largest table by item count.
#
# Item shape:
#   user_id (S)
#   job_id (S)
#   posting (M)         — full JobPosting
#   score (N)
# -----------------------------------------------------------------------------
create_table "${DDB_SEEN_JOBS_TABLE}" "job_id"     "user → job → seen-job entry"

section "Done"

cat <<EOF
DynamoDB tables created in ${AWS_REGION}:
  · ${DDB_APPLIED_TABLE}
  · ${DDB_LETTERS_TABLE}
  · ${DDB_USAGE_TABLE}
  · ${DDB_QUERIES_TABLE}
  · ${DDB_SEEN_JOBS_TABLE}

All using on-demand billing — no minimum charge, scales to zero,
covered by the always-free DynamoDB tier (25 GB / 25 RCU / 25 WCU).

Verify in the console at:
  https://${AWS_REGION}.console.aws.amazon.com/dynamodbv2/home?region=${AWS_REGION}#tables
EOF
