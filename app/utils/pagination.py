from typing import Annotated, Generic, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel

T = TypeVar("T")

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class PaginationParams:
    """Parametres de pagination communs, injectes comme dependance."""

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


Pagination = Annotated[PaginationParams, Depends(PaginationParams)]


class Page(BaseModel, Generic[T]):
    """Enveloppe de reponse paginee."""

    items: list[T]
    total: int
    limit: int
    offset: int
