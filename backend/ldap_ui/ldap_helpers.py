"""
Utilities for asynchronous LDAP operations.

HTTP endpoints typically trigger asynchronous LDAP requests
which return an ID for the operation being performed.
Results are then gathered in non-blocking mode.

Some shorthands are provided for common usages
like retrieving a unique result or waiting for an
operation to complete without results.
"""

import contextlib
from typing import AsyncGenerator, Generator, Tuple

import ldap
from anyio import sleep
from ldap.ldapobject import LDAPObject
from starlette.exceptions import HTTPException

from . import settings

__all__ = (
    "empty",
    "get_entry_by_dn",
    "ldap_connect",
    "result",
    "unique",
    "WITH_OPERATIONAL_ATTRS",
)


# Constant to add technical attributes in LDAP search results
WITH_OPERATIONAL_ATTRS = ("*", "+")


@contextlib.contextmanager
def ldap_connect() -> Generator[LDAPObject, None, None]:
    "Open an LDAP connection"

    url = settings.LDAP_URL
    connection = ldap.initialize(url)

    # #43 TLS, see https://stackoverflow.com/a/8795694
    if settings.USE_TLS or settings.INSECURE_TLS:
        cert_level = (
            ldap.OPT_X_TLS_NEVER if settings.INSECURE_TLS else ldap.OPT_X_TLS_DEMAND
        )

        connection.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, cert_level)
        # See https://stackoverflow.com/a/38136255
        connection.set_option(ldap.OPT_X_TLS_NEWCTX, 0)
        if not url.startswith("ldaps://"):
            connection.start_tls_s()
    yield connection
    connection.unbind_s()


async def result(
    connection: LDAPObject, msgid: int
) -> AsyncGenerator[Tuple[str, dict[str, list[bytes]]], None]:
    "Stream LDAP result entries without blocking other tasks"

    while True:
        r_type, r_data = connection.result(msgid=msgid, all=0, timeout=0)
        if r_type is None:  # Throttle to 100 results / second
            await sleep(0.01)
        elif r_data == []:  # Operation completed
            break
        else:
            yield r_data[0]


async def unique(
    connection: LDAPObject,
    msgid: int,
) -> Tuple[str, dict[str, list[bytes]]]:
    "Asynchronously collect a unique result"

    res = None
    async for r in result(connection, msgid):
        if res is None:
            res = r
        else:
            connection.abandon(msgid)
            raise HTTPException(500, "Non-unique result")
    if res is None:
        raise HTTPException(404, "Empty search result")
    return res


async def empty(
    connection: LDAPObject,
    msgid: int,
) -> None:
    "Asynchronously wait for an empty result"

    async for r in result(connection, msgid):
        connection.abandon(msgid)
        raise HTTPException(500, "Unexpected result")


async def get_entry_by_dn(
    connection: LDAPObject,
    dn: str,
) -> Tuple[str, dict[str, list[bytes]]]:
    "Asynchronously retrieve an LDAP entry by its DN"

    try:
        return await unique(connection, connection.search(dn, ldap.SCOPE_BASE))
    except ldap.NO_SUCH_OBJECT:
        raise HTTPException(404, f"DN not found: {dn}")
