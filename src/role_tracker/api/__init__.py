"""HTTP API surface for Role Tracker AI — Phase 5+.

The CLI script (scripts/run_match.py) and this API are *both* consumers of
the same engine code in src/role_tracker/. The agent, matching, jobs, and
users modules are unchanged; this layer only adds HTTP routing, auth
middleware, and Pydantic request/response shaping.
"""
