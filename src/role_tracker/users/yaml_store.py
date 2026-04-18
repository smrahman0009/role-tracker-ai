"""YAML-file-backed UserProfileStore. One file per user in the users/ folder."""

from pathlib import Path

import yaml

from role_tracker.users.models import UserProfile


class YamlUserProfileStore:
    """Reads UserProfile objects from YAML files in a directory."""

    def __init__(self, root: Path = Path("users")) -> None:
        self._root = root

    def list_users(self) -> list[UserProfile]:
        if not self._root.exists():
            return []
        return [self._load_file(p) for p in sorted(self._root.glob("*.yaml"))]

    def get_user(self, user_id: str) -> UserProfile:
        path = self._root / f"{user_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(
                f"No user profile at {path}. Known users: "
                f"{[u.id for u in self.list_users()]}"
            )
        return self._load_file(path)

    @staticmethod
    def _load_file(path: Path) -> UserProfile:
        with open(path) as f:
            data = yaml.safe_load(f)
        return UserProfile(**data)
