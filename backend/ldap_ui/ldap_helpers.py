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
from typing import AsyncGenerator, Generator

from anyio import sleep
from fastapi import HTTPException
from ldap import (
    OPT_X_TLS_DEMAND,  # type: ignore
    OPT_X_TLS_NEVER,  # type: ignore
    OPT_X_TLS_NEWCTX,  # type: ignore
    OPT_X_TLS_REQUIRE_CERT,  # type: ignore
    SCOPE_BASE,  # type: ignore
    SCOPE_SUBTREE,  # type: ignore
    initialize,
)
from ldap.ldapobject import LDAPObject
from ldap.schema import SubSchema

from . import settings

# Constant to add technical attributes in LDAP search results
WITH_OPERATIONAL_ATTRS = ("*", "+")


@dataclass(frozen=True)
class LdapEntry:
    dn: str
    attrs: dict[str, list[bytes]]

    def attr(self, name: str) -> list[str]:
        return [v.decode() for v in self.attrs[name]]

    @property
    def hasSubordinates(self):
        return (
            self.attr("hasSubordinates") == ["TRUE"]
            if "hasSubordinates" in self.attrs
            else bool(self.attrs.get("numSubordinates"))
        )


sub_schema: SubSchema | None = None


def ldap_connect() -> Generator[LDAPObject, None, None]:
    "Open an LDAP connection"

    url = settings.LDAP_URL
    connection = initialize(url)

    # #43 TLS, see https://stackoverflow.com/a/8795694
    if settings.USE_TLS or settings.INSECURE_TLS:
        cert_level = OPT_X_TLS_NEVER if settings.INSECURE_TLS else OPT_X_TLS_DEMAND

        connection.set_option(OPT_X_TLS_REQUIRE_CERT, cert_level)
        # See https://stackoverflow.com/a/38136255
        connection.set_option(OPT_X_TLS_NEWCTX, 0)
        if not url.startswith("ldaps://"):
            connection.start_tls_s()
    yield connection
    connection.unbind_s()


async def anonymous_user_search(connection: LDAPObject, username: str) -> str | None:
    try:
        return (
            await unique(
                connection,
                connection.search(
                    settings.BASE_DN,
                    SCOPE_SUBTREE,
                    settings.GET_BIND_DN_FILTER(username),
                ),
            )
        ).dn

    except HTTPException:
        pass  # No unique result


async def results(
    connection: LDAPObject, msgid: int
) -> AsyncGenerator[LdapEntry, None]:
    "Stream LDAP result entries without blocking other tasks"

    while True:
        r_type, r_data = connection.result(msgid=msgid, all=0, timeout=0)
        if r_type is None:  # Throttle to 100 results / second
            await sleep(0.01)
        elif r_data == []:  # Operation completed
            break
        else:
            yield LdapEntry(*r_data[0])  # type: ignore


async def unique(
    connection: LDAPObject,
    msgid: int,
) -> LdapEntry:
    "Asynchronously collect a unique result"

    res = None
    async for r in results(connection, msgid):
        if res is None:
            res = r
        else:
            connection.abandon(msgid)
            raise HTTPException(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Non-unique result",
            )
    if res is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Empty search result")
    return res


async def empty(
    connection: LDAPObject,
    msgid: int,
) -> None:
    "Asynchronously wait for an empty result"

    async for r in results(connection, msgid):
        connection.abandon(msgid)
        raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, "Unexpected result")


async def get_entry_by_dn(
    connection: LDAPObject,
    dn: str,
) -> LdapEntry:
    "Asynchronously retrieve an LDAP entry by its DN"

    return await unique(connection, connection.search(dn, SCOPE_BASE))


async def get_schema(connection: LDAPObject) -> SubSchema:
    global sub_schema
    # See: https://hub.packtpub.com/python-ldap-applications-part-4-ldap-schema/
    if sub_schema is None:
        result = await unique(
            connection,
            connection.search(
                settings.SCHEMA_DN,
                SCOPE_BASE,
                attrlist=WITH_OPERATIONAL_ATTRS,
            ),
        )
        sub_schema = SubSchema(result.attrs, check_uniqueness=2)
    return sub_schema
