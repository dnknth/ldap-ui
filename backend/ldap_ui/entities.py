"Data types for ReST endpoints"

from pydantic import BaseModel

from .ldap_helpers import LdapEntry

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
    def from_entry(cls, entry: LdapEntry):
        return cls(
            dn=entry.dn,
            structuralObjectClass=entry.attr("structuralObjectClass")[0],
            hasSubordinates=entry.hasSubordinates,
        )
