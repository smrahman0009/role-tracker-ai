# Multi-user operations

Role Tracker supports a small private-beta deployment: a few hand-picked
testers, each with their own `user_id` and bearer token. This is **not**
a full SaaS auth system — there's no signup form, no email verification,
no password reset. Tokens are minted by an admin (you) on the command
line and shared with each tester out-of-band.

## How it works

- A single SSM parameter at `/role-tracker/APP_TOKENS` holds a JSON map:
  `{"<token>": "<user_id>"}`. The API reads it at container startup.
- Each request must include `Authorization: Bearer <token>`.
- The bearer-token middleware rejects:
  - missing / malformed header → 401
  - token not in the map → 401
  - token's bound `user_id` doesn't match the URL path's `user_id` → 403
- A daily spend cap (default $1.50) protects against runaway costs per
  user. Once a user hits it, every Anthropic call returns 429 until the
  bucket resets at 00:00 UTC.

Per-user data isolation is automatic: every store is keyed by `user_id`
(DynamoDB partition key, S3 object prefix, YAML profile filename). The
middleware enforces that the token's owner can only address their own
key.

## Adding a new tester

```bash
uv run python infra/users/manage_users.py add <user_id>
```

Prints a 43-character token. Save it before closing the terminal — the
script does not store it anywhere readable.

Then **restart the API container** so it loads the new token map:

```bash
ssh ec2-user@<ec2-ip> 'sudo systemctl restart role-tracker'
```

Send the tester three things:
1. The URL: `https://roletracker.app`
2. Their `user_id` (e.g. `user_x_`)
3. Their token

They paste both into the login form on first visit.

## Rotating a token

If a token leaks (committed to a public repo, shared in screenshots):

```bash
uv run python infra/users/manage_users.py rotate <user_id>
```

This revokes the old token immediately on the next container restart
and prints a new one to give the tester. Their existing data (resume,
applications, letters) stays put — only the credential changes.

## Removing a tester

```bash
uv run python infra/users/manage_users.py remove <user_id>
```

Revokes the token. **Does not** delete S3 / DynamoDB rows for the user;
that's intentional so audit context (CloudTrail logs, application
history) is preserved. If you want a hard purge, do it manually
through the AWS console after the user confirms.

## Listing testers

```bash
uv run python infra/users/manage_users.py list
```

Prints `user_id` and a 12-character token prefix (so you can tell two
users apart in logs without the full secret).

## When a tester reports "429 Daily cost cap reached"

That's working as intended — they spent the configured cap of estimated
Anthropic cost in one UTC day. The bucket resets at 00:00 UTC; tell
them to try again tomorrow.

### Raising the cap globally

```bash
aws ssm put-parameter --name /role-tracker/DAILY_COST_CAP_USD \
    --value "3.00" --type String --overwrite

ssh ec2-user@<ec2-ip> 'sudo systemctl restart role-tracker'
```

Default if unset: `$1.50/day`.

### Per-user cap override

The admin (you, while iterating on the agent) typically needs more
headroom than friend testers. Push a JSON map of overrides to SSM:

```bash
aws ssm put-parameter \
    --name /role-tracker/DAILY_COST_CAP_USD_OVERRIDES \
    --value '{"smrah":10.00}' \
    --type SecureString --overwrite

ssh ec2-user@<ec2-ip> 'sudo systemctl restart role-tracker'
```

Effect: `smrah` gets a $10/day cap; everyone else falls back to the
global `DAILY_COST_CAP_USD`.

The map can list multiple users:
`{"smrah":10.00,"power_tester":5.00}`. Users not in the map use the
global cap. Empty / unset = no overrides.

The override is stored as a SecureString purely for hygiene (it's
not really a secret — but consistent with everything else under
`/role-tracker/`).

## Costs are estimates

The dashboard / cap math uses per-feature averages from
`role_tracker.usage.store.FEATURE_COST_USD`, not real Anthropic
billing. Real costs live in your Anthropic + OpenAI dashboards. The
estimate has been tuned to be a slight over-estimate so the cap fires
slightly early rather than slightly late.
