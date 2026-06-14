"""
Shared schemas — common validation schemas used by multiple modules.

Usage::

    from app.shared.schemas import PaginationParams, validate_pagination
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PaginationParams:
    """Standard pagination parameters used across all list endpoints."""

    page: int = 1
    per_page: int = 25
    sort_by: Optional[str] = None
    sort_order: str = "asc"

    def __post_init__(self):
        self.page = max(1, int(self.page))
        self.per_page = max(1, min(100, int(self.per_page)))
        if self.sort_order not in ("asc", "desc"):
            self.sort_order = "asc"


def validate_pagination(args: dict) -> PaginationParams:
    """Parse pagination params from a request.args dict.

    Args:
        args: Request query parameters (e.g. request.args).

    Returns:
        Validated PaginationParams instance.
    """
    return PaginationParams(
        page=args.get("page", 1, type=int),
        per_page=args.get("per_page", 25, type=int),
        sort_by=args.get("sort_by", None, type=str),
        sort_order=args.get("sort_order", "asc", type=str),
    )


@dataclass
class SearchParams:
    """Standard search parameters used across list/search endpoints."""

    query: str = ""
    filters: Optional[dict] = None
    pagination: Optional[PaginationParams] = None

    def __post_init__(self):
        self.query = str(self.query).strip()[:500]
        if self.pagination is None:
            self.pagination = PaginationParams()
