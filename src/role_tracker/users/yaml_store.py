"""YAML-file-backed UserProfileStore. One file per user in the users/ folder."""

from pathlib import Path

import yaml

from role_tracker.users.models import UserProfile


class YamlUserProfileStore:
    """Reads + writes UserProfile objects to YAML files in a directory."""

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

    def save_user(self, profile: UserProfile) -> None:
        """Persist a profile back to disk. Overwrites any existing file."""
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / f"{profile.id}.yaml"
        # Atomic write: temp file, then rename.
        tmp = path.with_suffix(".yaml.tmp")
        data = profile.model_dump(mode="json")
        tmp.write_text(yaml.safe_dump(data, sort_keys=False))
        tmp.replace(path)

    @staticmethod
    def _load_file(path: Path) -> UserProfile:
        with open(path) as f:
            data = yaml.safe_load(f)
        return UserProfile(**data)
