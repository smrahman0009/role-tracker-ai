"""Contract for loading user profiles. Swap implementations freely.

Today: YamlUserProfileStore reads users/*.yaml.
Future: DatabaseUserProfileStore reads rows from Postgres/SQLite.
Same protocol → zero changes in run_match.py when we migrate.
"""

from typing import Protocol

from role_tracker.users.models import UserProfile


class UserProfileStore(Protocol):
    """Minimal interface: list users, get one, persist updates."""

    def list_users(self) -> list[UserProfile]: ...

    def get_user(self, user_id: str) -> UserProfile: ...

    def save_user(self, profile: UserProfile) -> None: ...
