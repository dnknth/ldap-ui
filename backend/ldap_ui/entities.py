"Data types for ReST endpoints"

from pydantic import BaseModel, Field


class TreeItem(BaseModel):
    "Entry in the navigation tree"

    dn: str
    structuralObjectClass: str
    hasSubordinates: bool
    level: int


class Meta(BaseModel):
    "Attribute classification for an entry"

    dn: str
    required: list[str]
    aux: list[str]
    binary: list[str]
    autoFilled: list[str]
    isNew: bool = False


Attributes = dict[str, list[str]]


class Entry(BaseModel):
    "Directory entry"

    attrs: Attributes
    meta: Meta
    changed: list[str] = Field(default_factory=list)


class ChangedAttributes(BaseModel):
    "List of modified attributes"

    changed: list[str]


class ChangePasswordRequest(BaseModel):
    "Change a password"

    old: str
    new1: str


class SearchResult(BaseModel):
    "Search result"

    dn: str
    name: str


class Range(BaseModel):
    "Numeric attribute range"

    min: int
    max: int
    next: int
