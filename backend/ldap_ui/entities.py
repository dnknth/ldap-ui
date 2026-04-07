"Data types for ReST endpoints"

from base64 import b64encode
from typing import Self

from ldap3 import SchemaInfo
from pydantic import BaseModel

from .ldap_helpers import ResponseEntry

Attributes = dict[str, list[str]]

AttributeNames = list[str]  # Names of modified attributes


class Entry(BaseModel):
    "Directory entry"

    dn: str
    attrs: Attributes
    binary: AttributeNames
    autoFilled: AttributeNames
    changed: AttributeNames
    isNew: bool = False

    @classmethod
    def of(cls, entry: ResponseEntry, schema: SchemaInfo) -> Self:
        "Decode an LDAP entry for transmission"

        binary = sorted(
            set(attr for attr in entry.raw_attributes if entry.is_binary(attr, schema))
        )
        return cls(
            attrs={
                k: ["*****"]  # 23 suppress userPassword
                if k == "userPassword"
                else [b64encode(val).decode() for val in entry.raw_attributes[k]]
                if k in binary
                else [val.decode() for val in entry.raw_attributes[k]]
                for k in sorted(entry.raw_attributes)
            },
            dn=entry.dn,
            binary=binary,
            autoFilled=[],
            changed=[],
        )


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


class TreeItem(BaseModel):
    "Entry in the navigation tree"

    dn: str
    structuralObjectClass: str
    hasSubordinates: bool

    @classmethod
    def of(cls, entry: ResponseEntry):
        return cls(
            dn=entry.dn,
            structuralObjectClass=entry.attributes["structuralObjectClass"],
            hasSubordinates=entry.hasSubordinates,
        )
