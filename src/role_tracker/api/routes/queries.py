"""Saved-queries CRUD endpoints — see docs/api_spec.md §5."""

from fastapi import APIRouter, Depends, HTTPException, status

from role_tracker.api.schemas import (
    CreateQueryRequest,
    QueryListResponse,
    SavedQuery,
    UpdateQueryRequest,
)
from role_tracker.config import Settings
from role_tracker.queries.base import QueryStore
from role_tracker.queries.json_store import JsonQueryStore

router = APIRouter(
    prefix="/users/{user_id}/queries",
    tags=["queries"],
)


def get_query_store() -> QueryStore:
    """FastAPI dependency factory.

    Picks the cloud-native (DynamoDB) backend when STORAGE_BACKEND=aws,
    otherwise falls back to the JSON-file store used in dev. Tests
    override this dependency at the FastAPI level.
    """
    settings = Settings()
    if settings.storage_backend == "aws":
        from role_tracker.aws.dynamodb_query_store import DynamoDBQueryStore

        return DynamoDBQueryStore(
            table_name=settings.ddb_queries_table,
            region_name=settings.aws_region,
        )
    return JsonQueryStore()


@router.get("", response_model=QueryListResponse)
def list_queries(
    user_id: str,
    store: QueryStore = Depends(get_query_store),
) -> QueryListResponse:
    """List all saved queries for the user."""
    return QueryListResponse(
        queries=store.list_queries(user_id),
        next_refresh_allowed_at=None,  # populated when refresh endpoint lands
    )


@router.post(
    "",
    response_model=SavedQuery,
    status_code=status.HTTP_201_CREATED,
)
def create_query(
    user_id: str,
    body: CreateQueryRequest,
    store: QueryStore = Depends(get_query_store),
) -> SavedQuery:
    """Add a new query.

    Per the spec this is supposed to auto-trigger a job refresh, but the
    refresh endpoint doesn't exist yet, so we just persist for now. The
    auto-refresh wiring lands when the jobs router does.
    """
    return store.add_query(user_id, body.what, body.where)


@router.put("/{query_id}", response_model=SavedQuery)
def update_query(
    user_id: str,
    query_id: str,
    body: UpdateQueryRequest,
    store: QueryStore = Depends(get_query_store),
) -> SavedQuery:
    """Patch fields on an existing query."""
    updated = store.update_query(
        user_id,
        query_id,
        what=body.what,
        where=body.where,
        enabled=body.enabled,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Query '{query_id}' not found for user '{user_id}'",
        )
    return updated


@router.delete("/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_query(
    user_id: str,
    query_id: str,
    store: QueryStore = Depends(get_query_store),
) -> None:
    """Remove a query."""
    if not store.delete_query(user_id, query_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Query '{query_id}' not found for user '{user_id}'",
        )
