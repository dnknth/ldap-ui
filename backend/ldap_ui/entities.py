"Data types for ReST endpoints"

from base64 import b64encode
from typing import Annotated, Self

from ldap3 import SchemaInfo
from pydantic import BaseModel, Field

from .ldap_helpers import ResponseEntry

Attributes = dict[str, list[str]]

AttributeNames = list[str]  # Names of modified attributes

# Upper bound for the numeric attribute range reported by /api/range.
# Kept small so the next-free computation is bounded, and documented in the
# OpenAPI schema via the Range model constraints.
RANGE_LIMIT = 60000


class Entry(BaseModel):
    "Directory entry"

    dn: str
    attrs: Attributes
    binary: AttributeNames
    autoFilled: AttributeNames
    changed: AttributeNames
    isNew: bool = False

    @classmethod
    def _format_attrs(
        cls, entry: ResponseEntry, binary: set[str], schema: SchemaInfo
    ) -> Attributes:
        result = {}
        for k in sorted(entry.raw_attributes):
            if not entry.is_modifiable(k, schema):
                continue
            vals = entry.raw_attributes[k]
            if k == "userPassword":
                result[k] = ["*****"]
            elif k in binary:
                result[k] = [b64encode(val).decode() for val in vals]
            else:
                result[k] = [val.decode() for val in vals]
        return result

    @classmethod
    def of(cls, entry: ResponseEntry, schema: SchemaInfo) -> Self:
        "Decode an LDAP entry for transmission"

        binary = sorted(
            {
                attr
                for attr in entry.raw_attributes
                if entry.is_binary(attr, schema) and entry.is_modifiable(attr, schema)
            }
        )
        return cls(
            attrs=cls._format_attrs(entry, set(binary), schema),
            dn=entry.dn,
            binary=binary,
            autoFilled=[],
            changed=[],
        )


class ChangePasswordRequest(BaseModel):
    "Change a password"

    old: str | None = None
    new1: str


class SearchResult(BaseModel):
    "Search result"

    dn: str
    name: str


class Range(BaseModel):
    "Numeric attribute range, bounded to 0..RANGE_LIMIT"

    min: Annotated[int, Field(ge=0, le=RANGE_LIMIT)]
    max: Annotated[int, Field(ge=0, le=RANGE_LIMIT)]
    next: Annotated[int, Field(ge=0, le=RANGE_LIMIT)]


class TreeItem(BaseModel):
    "Entry in the navigation tree"

    dn: str
    structuralObjectClass: str
    hasSubordinates: bool

    @classmethod
    def of(cls, entry: ResponseEntry):
        return cls(
            dn=entry.dn,
            structuralObjectClass=entry.raw_attributes["structuralObjectClass"][0],
            hasSubordinates=entry.hasSubordinates,
        )
