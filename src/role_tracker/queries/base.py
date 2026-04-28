"""QueryStore Protocol — the abstract interface every storage backend implements.

Today: JsonQueryStore (file-backed at data/queries/{user_id}.json).
Phase 8 deploy: will add CosmosQueryStore. Routes don't change because
they depend on the Protocol, not the concrete class.
"""

from typing import Protocol

from role_tracker.queries.models import SavedQuery


class QueryStore(Protocol):
    """Abstract storage for saved search queries."""

    def list_queries(self, user_id: str) -> list[SavedQuery]:
        """Return all queries for the user, in creation order."""
        ...

    def get_query(self, user_id: str, query_id: str) -> SavedQuery | None:
        """Return one query, or None if not found."""
        ...

    def add_query(self, user_id: str, what: str, where: str) -> SavedQuery:
        """Create a new query. Returns the saved record (with assigned id)."""
        ...

    def update_query(
        self,
        user_id: str,
        query_id: str,
        *,
        what: str | None = None,
        where: str | None = None,
        enabled: bool | None = None,
    ) -> SavedQuery | None:
        """Patch fields on an existing query. None values are skipped.

        Returns the updated record, or None if the id was not found.
        """
        ...

    def delete_query(self, user_id: str, query_id: str) -> bool:
        """Remove a query. Returns True if it existed, False otherwise."""
        ...
