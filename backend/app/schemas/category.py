from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CategoryOut(ORMModel):
    id: int
    name: str
    icon: str
    color: str
    type: str
    parent_id: int | None
    rollover: bool
    archived: bool
    sort_order: int


class CategoryCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    icon: str = Field(default="📁", max_length=16)
    color: str = Field(default="#10b981", max_length=9)
    type: str = Field(default="expense", pattern="^(income|expense)$")
    parent_id: int | None = None
    rollover: bool = True
    sort_order: int = 0


class CategoryUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    icon: str | None = Field(default=None, max_length=16)
    color: str | None = Field(default=None, max_length=9)
    parent_id: int | None = None
    clear_parent: bool = False
    rollover: bool | None = None
    archived: bool | None = None
    sort_order: int | None = None


class TagOut(ORMModel):
    id: int
    name: str


class TagCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
