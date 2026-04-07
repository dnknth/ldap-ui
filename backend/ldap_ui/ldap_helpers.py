"""
Utilities for asynchronous LDAP operations.

HTTP endpoints typically trigger asynchronous LDAP requests
which return an ID for the operation being performed.
Results are then gathered in non-blocking mode.

Some shorthands are provided for common usages
like retrieving a unique result or waiting for an
operation to complete without results.
"""

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, AsyncGenerator

from anyio import sleep
from fastapi import HTTPException
from ldap3 import Connection, SchemaInfo
from ldap3.core.exceptions import LDAPResponseTimeoutError

from .schema import OCTET_STRING, Syntax


@dataclass(frozen=True)
class Result:  # TODO unused
    result: int
    description: str
    message: str | None
    dn: str | None
    referrals: list


@dataclass(frozen=True)
class ResponseEntry:
    raw_dn: bytes
    dn: str
    attributes: dict[str, Any]
    raw_attributes: dict[str, list[bytes]]
    type: str

    @property
    def hasSubordinates(self):
        return b"TRUE" in self.raw_attributes.get("hasSubordinates", []) or bool(
            self.raw_attributes.get("numSubordinates", 0)
        )

    def is_binary(self, attr: str, schema: SchemaInfo) -> bool:
        "Guess whether an attribute has binary content"

        # Octet strings are not used consistently in schemata.
        # Try to decode as text and treat as binary on failure
        attr_type = schema.attribute_types.get(attr)
        assert attr_type, f"Attribute '{attr}' not found in schema"
        if not attr_type.syntax or attr_type.syntax == OCTET_STRING:
            try:
                return any(
                    not val.decode("UTF-8").isprintable()
                    for val in self.raw_attributes[attr]
                )
            except UnicodeDecodeError:
                return True

        # Check human-readable flag
        syntax = schema.ldap_syntaxes.get(attr_type.syntax)
        assert syntax, f"Syntax '{attr_type.syntax}' not found in schema"
        return Syntax.of(syntax).not_human_readable


async def get_responses(
    connection: Connection, msgid: int
) -> AsyncGenerator[ResponseEntry, None]:
    "Stream LDAP result entries without blocking other tasks"

    assert type(msgid) is int, "Expected async operation"
    while True:
        try:
            entries, result = connection.get_response(
                msgid, timeout=0, get_request=False
            )
            for response in entries:
                yield ResponseEntry(**response)
            return
        except LDAPResponseTimeoutError:
            await sleep(0.01)


async def unique(
    connection: Connection,
    msgid: int,
) -> ResponseEntry:
    "Asynchronously collect a unique result"

    res = None
    async for r in get_responses(connection, msgid):
        if res is None:
            res = r
        else:
            connection.abandon(msgid)  # FIXME is this needed?
            raise HTTPException(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Non-unique result",
            )
    if res is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Empty search result")
    return res


async def empty(
    connection: Connection,
    msgid: int,
) -> None:
    "Asynchronously wait for an empty result"

    async for r in get_responses(connection, msgid):
        connection.abandon(msgid)
        raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, "Unexpected result")
