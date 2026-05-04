#!/usr/bin/env bash
#
# Create the S3 bucket where resume PDFs and DOCX exports live.
#
# Security defaults applied here are the ones every "AWS S3 best
# practices" article will tell you about — they're worth understanding:
#
#   1. Block ALL public access at the account level for this bucket.
#      Even if a future bucket policy or ACL is misconfigured, AWS
#      refuses to serve the objects publicly.
#   2. Enable server-side encryption (SSE-S3 / AES-256) so objects are
#      encrypted at rest. Free.
#   3. Enable versioning so a buggy delete or overwrite is recoverable.
#      Old versions are charged at the same rate as live objects, so
#      we add a lifecycle rule that auto-deletes versions older than 30
#      days to keep cost bounded.
#   4. Deny non-HTTPS requests via a bucket policy. Forces TLS for
#      every read/write — important since resumes contain personal data.
#
# Idempotent: safe to re-run.
# -----------------------------------------------------------------------------

source "$(dirname "$0")/00-vars.sh"

section "Creating S3 bucket: ${S3_BUCKET}"

if aws s3api head-bucket --bucket "${S3_BUCKET}" 2>/dev/null; then
    note "Bucket already exists — skipping creation."
else
    aws s3api create-bucket \
        --bucket "${S3_BUCKET}" \
        --region "${AWS_REGION}" \
        --create-bucket-configuration "LocationConstraint=${AWS_REGION}" \
        >/dev/null
    ok "Created ${S3_BUCKET}"
fi

section "Blocking all public access"

aws s3api put-public-access-block \
    --bucket "${S3_BUCKET}" \
    --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
    >/dev/null
ok "Public access blocked"

section "Enabling server-side encryption (AES-256)"

aws s3api put-bucket-encryption \
    --bucket "${S3_BUCKET}" \
    --server-side-encryption-configuration '{
        "Rules": [{
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "AES256"
            }
        }]
    }' \
    >/dev/null
ok "Encryption at rest enabled"

section "Enabling versioning"

aws s3api put-bucket-versioning \
    --bucket "${S3_BUCKET}" \
    --versioning-configuration "Status=Enabled" \
    >/dev/null
ok "Versioning enabled"

section "Adding lifecycle rule (delete old versions after 30 days)"

aws s3api put-bucket-lifecycle-configuration \
    --bucket "${S3_BUCKET}" \
    --lifecycle-configuration '{
        "Rules": [{
            "ID": "expire-noncurrent-versions",
            "Status": "Enabled",
            "Filter": {},
            "NoncurrentVersionExpiration": {
                "NoncurrentDays": 30
            },
            "AbortIncompleteMultipartUpload": {
                "DaysAfterInitiation": 7
            }
        }]
    }' \
    >/dev/null
ok "Lifecycle rule applied"

section "Enforcing HTTPS-only access"

# Bucket policy that denies any request not made over TLS. The
# Principal "*" means "anyone" but the Condition narrows it to
# only deny insecure requests — authenticated HTTPS still works.
aws s3api put-bucket-policy \
    --bucket "${S3_BUCKET}" \
    --policy "$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "DenyInsecureTransport",
        "Effect": "Deny",
        "Principal": "*",
        "Action": "s3:*",
        "Resource": [
            "arn:aws:s3:::${S3_BUCKET}",
            "arn:aws:s3:::${S3_BUCKET}/*"
        ],
        "Condition": {
            "Bool": { "aws:SecureTransport": "false" }
        }
    }]
}
EOF
)"
ok "HTTPS-only policy applied"

section "Done"

cat <<EOF
S3 bucket: ${S3_BUCKET}
  · Region:       ${AWS_REGION}
  · Encryption:   AES-256 (server-side)
  · Versioning:   enabled (old versions purged after 30 days)
  · Public:       blocked at every level
  · Transport:    HTTPS only

You can verify in the console at:
  https://${AWS_REGION}.console.aws.amazon.com/s3/buckets/${S3_BUCKET}
EOF
