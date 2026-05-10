#!/usr/bin/env python3
"""Manage Role Tracker user tokens.

Source of truth: a single SecureString SSM parameter at
`/role-tracker/APP_TOKENS` holding a JSON map of `{token: user_id}`.
The API container reads it at startup; after any change here, restart
the API (or wait for the next deploy) for the new map to take effect.

Subcommands
-----------

  add <user_id>            mint a new token for user_id, append to the map,
                           print the token to stdout (one-time display)
  rotate <user_id>         mint a new token, replace the old one for
                           user_id, print the new token
  remove <user_id>         drop user_id's token from the map (does NOT
                           delete the user's S3/DynamoDB data — see notes)
  list                     show user_id → token-prefix table

Why this isn't a shell script: the SSM value is JSON and needs an
atomic read-modify-write. Doing that in jq + bash is fragile; boto3
in Python is two lines.

Data-deletion is intentionally separate: removing a token locks the
user out of the API immediately, but their resume / letters / usage
rows stay in S3 + DynamoDB so audit/CloudTrail context is preserved.
If you need a hard purge, do it manually through the AWS console
after confirming with the user.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from typing import Any

try:
    import boto3
except ImportError:
    sys.stderr.write(
        "boto3 is required. Install with: pip install boto3\n"
        "Or run via: uv run python infra/users/manage_users.py ...\n"
    )
    sys.exit(2)

REGION_DEFAULT = "ca-central-1"
PARAM_NAME = "/role-tracker/APP_TOKENS"
TOKEN_BYTES = 32  # 256 bits → 43 url-safe chars


def _ssm_client(region: str) -> Any:
    return boto3.client("ssm", region_name=region)


def _load(client: Any) -> dict[str, str]:
    """Read the APP_TOKENS parameter; return {} if it doesn't exist yet."""
    try:
        resp = client.get_parameter(Name=PARAM_NAME, WithDecryption=True)
    except client.exceptions.ParameterNotFound:
        return {}
    raw = resp["Parameter"]["Value"].strip()
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise SystemExit(f"{PARAM_NAME} is not a JSON object")
    return parsed


def _save(client: Any, tokens: dict[str, str]) -> None:
    client.put_parameter(
        Name=PARAM_NAME,
        Value=json.dumps(tokens, sort_keys=True),
        Type="SecureString",
        Overwrite=True,
        Description="Bearer tokens → user_id map (managed by manage_users.py)",
    )


def _mint() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def _user_to_tokens(tokens: dict[str, str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for tok, user in tokens.items():
        out.setdefault(user, []).append(tok)
    return out


# ----- subcommands --------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    client = _ssm_client(args.region)
    tokens = _load(client)
    if not tokens:
        print("(no users registered)")
        return 0
    grouped = _user_to_tokens(tokens)
    width = max(len(u) for u in grouped) + 2
    print(f"{'user_id'.ljust(width)}token (prefix)")
    print(f"{'-' * (width - 2)}  {'-' * 16}")
    for user in sorted(grouped):
        for tok in grouped[user]:
            print(f"{user.ljust(width)}{tok[:12]}…")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    client = _ssm_client(args.region)
    tokens = _load(client)
    if args.user_id in tokens.values():
        sys.stderr.write(
            f"User {args.user_id!r} already has a token. "
            f"Use `rotate` to issue a new one.\n"
        )
        return 1
    new_token = _mint()
    tokens[new_token] = args.user_id
    _save(client, tokens)
    print(f"Added user: {args.user_id}")
    print(f"Token (one-time display, save it now):\n\n  {new_token}\n")
    print("Restart the API container so the new token is loaded.")
    return 0


def cmd_rotate(args: argparse.Namespace) -> int:
    client = _ssm_client(args.region)
    tokens = _load(client)
    old = [t for t, u in tokens.items() if u == args.user_id]
    if not old:
        sys.stderr.write(f"User {args.user_id!r} not found.\n")
        return 1
    for t in old:
        del tokens[t]
    new_token = _mint()
    tokens[new_token] = args.user_id
    _save(client, tokens)
    print(f"Rotated token for: {args.user_id}")
    print(f"New token (one-time display):\n\n  {new_token}\n")
    print(f"Old token(s) revoked: {len(old)}")
    print("Restart the API container so the change takes effect.")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    client = _ssm_client(args.region)
    tokens = _load(client)
    matches = [t for t, u in tokens.items() if u == args.user_id]
    if not matches:
        sys.stderr.write(f"User {args.user_id!r} not found.\n")
        return 1
    for t in matches:
        del tokens[t]
    _save(client, tokens)
    print(f"Removed {len(matches)} token(s) for: {args.user_id}")
    print(
        "Note: this does NOT delete the user's S3 resume or DynamoDB rows.\n"
        "Those are preserved for audit context. Purge manually if needed."
    )
    print("Restart the API container so the change takes effect.")
    return 0


def cmd_make_admin(args: argparse.Namespace) -> int:
    """Flip is_admin=True on the user's profile so they can edit
    the global hidden-publishers list. Reads the configured profile
    store (DynamoDB in prod, YAML in dev — same as the API uses).
    """
    return _set_admin_flag(args.user_id, True)


def cmd_revoke_admin(args: argparse.Namespace) -> int:
    """Flip is_admin=False on the user's profile."""
    return _set_admin_flag(args.user_id, False)


def _set_admin_flag(user_id: str, value: bool) -> int:
    # Local import — keeps this CLI usable without the full app's
    # boto3 chain when only --region/SSM commands are run.
    from role_tracker.users.factory import make_user_profile_store

    store = make_user_profile_store()
    try:
        profile = store.get_user(user_id)
    except FileNotFoundError:
        sys.stderr.write(f"User profile {user_id!r} not found.\n")
        return 1
    if profile.is_admin == value:
        verb = "already" if value else "already not"
        print(f"User {user_id!r} is {verb} an admin. No change.")
        return 0
    updated = profile.model_copy(update={"is_admin": value})
    store.save_user(updated)
    verb = "granted" if value else "revoked"
    print(f"Admin privileges {verb} for: {user_id}")
    return 0


# ----- argparse plumbing --------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage Role Tracker user tokens (SSM-backed).",
    )
    parser.add_argument(
        "--region",
        default=REGION_DEFAULT,
        help=f"AWS region (default: {REGION_DEFAULT})",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Mint a new token for a user")
    p_add.add_argument("user_id")
    p_add.set_defaults(func=cmd_add)

    p_rot = sub.add_parser("rotate", help="Rotate a user's token")
    p_rot.add_argument("user_id")
    p_rot.set_defaults(func=cmd_rotate)

    p_rm = sub.add_parser("remove", help="Revoke all tokens for a user")
    p_rm.add_argument("user_id")
    p_rm.set_defaults(func=cmd_remove)

    p_ls = sub.add_parser("list", help="List registered users + token prefixes")
    p_ls.set_defaults(func=cmd_list)

    p_admin = sub.add_parser(
        "make-admin",
        help="Flip is_admin=True on the user's profile (lets them edit "
        "the global hidden-publishers list)",
    )
    p_admin.add_argument("user_id")
    p_admin.set_defaults(func=cmd_make_admin)

    p_revoke = sub.add_parser(
        "revoke-admin",
        help="Flip is_admin=False on the user's profile",
    )
    p_revoke.add_argument("user_id")
    p_revoke.set_defaults(func=cmd_revoke_admin)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
