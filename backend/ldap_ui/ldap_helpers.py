"""
Utilities for asynchronous LDAP operations.

HTTP endpoints typically trigger asynchronous LDAP requests
which return an ID for the operation being performed.
Results are then gathered in non-blocking mode.

Some shorthands are provided for common usages
like retrieving a unique result or waiting for an
operation to complete without results.
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Self, cast

from anyio import fail_after, sleep
from fastapi import HTTPException
from ldap3 import Connection, SchemaInfo
from ldap3.core.exceptions import LDAPResponseTimeoutError

from .schema import OCTET_STRING, Syntax

# Overall bound for a single LDAP operation (seconds). A stuck directory must
# not hold a request and a connection slot forever.
OPERATION_TIMEOUT = 30.0


@dataclass(frozen=True)
class ResponseEntry:
    dn: str
    attributes: dict[str, Any]
    raw_attributes: dict[str, list[bytes]]

    @classmethod
    def of(cls, response: dict[str, Any]) -> Self:
        "Build an entry from an ldap3 response dictionary"
        return cls(
            dn=response["dn"],
            attributes=response["attributes"],
            raw_attributes=response["raw_attributes"],
        )

    @property
    def hasSubordinates(self):
        return b"TRUE" in self.raw_attributes.get("hasSubordinates", []) or bool(
            self.raw_attributes.get("numSubordinates", 0)
        )

    def is_modifiable(self, attr: str, schema: SchemaInfo):
        "Is an attribute modifiable by users?"
        attr_type = schema.attribute_types.get(attr)
        if not attr_type:
            raise ValueError(f"Attribute '{attr}' not found in schema")
        return not attr_type.no_user_modification

    def is_binary(self, attr: str, schema: SchemaInfo) -> bool:
        "Guess whether an attribute has binary content"

        # Octet strings are not used consistently in schemata.
        # Try to decode as text and treat as binary on failure
        attr_type = schema.attribute_types.get(attr)
        if not attr_type:
            raise ValueError(f"Attribute '{attr}' not found in schema")
        if not attr_type.syntax or attr_type.syntax == OCTET_STRING:
            try:
                return not all(
                    val.decode().isprintable() for val in self.raw_attributes[attr]
                )
            except UnicodeDecodeError:
                return True

        # Check human-readable flag.
        # computed_field getters are typed as callables by pydantic's stubs.
        syntax = schema.ldap_syntaxes.get(attr_type.syntax)
        return syntax is None or cast(bool, Syntax.of(syntax).not_human_readable)

    def is_updateable(self, attr: str, schema: SchemaInfo) -> bool:
        return (
            attr not in self.attributes
            # FIXME Handle binary attributes properly
            or not self.is_binary(attr, schema)
        )


async def get_raw_responses(
    connection: Connection, msgid: int
) -> AsyncGenerator[list[dict], None]:
    "Stream raw LDAP result entries without blocking other tasks"

    assert type(msgid) is int, "Expected async operation"
    try:
        with fail_after(OPERATION_TIMEOUT):
            while True:
                try:
                    entries, _result = connection.get_response(msgid, timeout=0)
                    yield entries
                    return
                except LDAPResponseTimeoutError:
                    await sleep(0.01)
    except TimeoutError:
        try:
            connection.abandon(msgid)
        except Exception:  # noqa: BLE001, S110
            pass
        raise HTTPException(
            HTTPStatus.GATEWAY_TIMEOUT,
            "LDAP operation timed out",
        )


async def get_responses(
    connection: Connection, msgid: int
) -> AsyncGenerator[ResponseEntry, None]:
    "Stream LDAP result entries without blocking other tasks"

    async for entries in get_raw_responses(connection, msgid):
        for response in entries:
            yield ResponseEntry.of(response)


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
