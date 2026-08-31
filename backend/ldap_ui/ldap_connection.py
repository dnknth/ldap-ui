"""
LDAP connection helpers.
"""

import re
from contextlib import asynccontextmanager
from random import random
from typing import Literal

import ldap3
from anyio import sleep
from ldap3 import Connection, Server
from ldap3.core.exceptions import LDAPInvalidCredentialsResult

from . import settings

# Connection URLs
URL_PATTERN = re.compile(
    r"""^(?P<scheme>ldap|ldapi|ldaps)://
         (?P<host>[/A-Za-z0-9_.-]*)
         (:(?P<port>[0-9]+))?
         (/(?P<dn>[^?]+))?
         .*""",
    re.IGNORECASE | re.VERBOSE,
)

InfoMode = Literal[ldap3.NONE, ldap3.DSA, ldap3.SCHEMA, ldap3.ALL]


def parse_url(url: str) -> tuple[str, str | None]:
    "Extract a base URL and optional base DN from a RFC 4516 URL"
    if match := URL_PATTERN.match(url):
        parts = match.groupdict()
        scheme = parts["scheme"]
        host = parts["host"]
        if not host or host == "/":
            if scheme == "ldapi":
                raise ValueError("Missing LDAPI domain socket path")
            else:
                host = "localhost"
        # ldap3 is not particularly smart with server URLs
        url = f"{scheme}://{host.rstrip('/')}"
        if scheme != "ldapi" and parts["port"]:
            url += f":{parts['port']}"
        return url, parts["dn"]

    raise ValueError(f"Invalid URL: {url}")


def open(url: str, get_info: InfoMode) -> Connection:
    "Open a connection and negotiate TLS before binding"

    connection = Connection(
        Server(url, get_info=get_info),
        client_strategy=ldap3.ASYNC,
        raise_exceptions=True,
    )

    # Negotiate StartTLS before binding. Otherwise the bind and the root DSE
    # lookup below are sent in clear text, and directories that mandate
    # confidentiality (e.g. OpenLDAP `olcSecurity: tls=1`) reject every
    # operation attempted before TLS is in place. See RFC 4513, §3.1.1.
    if settings.USE_TLS and url.startswith("ldap://"):
        connection.open(read_server_info=False)
        connection.start_tls()

    return connection


async def ldap_connect() -> Connection:
    "Open an anonymous LDAP connection"

    url, base_dn = parse_url(settings.LDAP_URL)
    get_info = (
        ldap3.DSA
        if (settings.BASE_DN is None and not base_dn) or settings.SCHEMA_DN is None
        else ldap3.NONE
    )
    connection = open(url, get_info)
    connection.bind()
    dsa_info = connection.server.info

    if not settings.BASE_DN:
        if base_dn:
            settings.BASE_DN = base_dn
        else:
            base_dns = dsa_info.naming_contexts
            if len(base_dns) != 1:
                raise ValueError(f"No unique base DN: {base_dns}")
            settings.BASE_DN = base_dns[0]

    elif base_dn and base_dn != settings.BASE_DN:
        raise ValueError(f"Contradictory base DNs: {base_dn} vs. {settings.BASE_DN}")

    if not settings.SCHEMA_DN:
        if not dsa_info.schema_entry:
            raise ValueError("Cannot determine LDAP schema")
        settings.SCHEMA_DN = dsa_info.schema_entry[0]

    return connection


async def rate_limit() -> None:
    "Delay a response on authentication failure, with jitter to defeat timing attacks"
    await sleep(0.5 + random() / 5)


@asynccontextmanager
async def bound(connection: Connection, dn: str, password: str | None):
    "Bind a connection as the given user, rate-limiting failures, always unbinding on exit"

    try:
        try:
            connection.rebind(user=dn, password=password)
        except LDAPInvalidCredentialsResult:
            await rate_limit()
            raise
        yield
    finally:
        try:
            connection.unbind()
        except Exception:  # noqa: BLE001, S110
            pass
