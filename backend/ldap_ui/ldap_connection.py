"""
LDAP connection and authentication helpers.
"""

import base64
import re
import ssl
from binascii import Error as BinasciiError
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from random import random
from typing import Literal

import ldap3
from anyio import Lock, sleep
from fastapi import HTTPException
from ldap3 import BASE, Connection, SchemaInfo, Server, Tls
from ldap3.core.exceptions import LDAPInvalidCredentialsResult

from . import settings
from .ldap_helpers import unique

# Connection URLs
URL_PATTERN = re.compile(
    r"""^(?P<scheme>ldap|ldapi|ldaps)://
         (?P<host>[/A-Za-z0-9_.-]*)
         (:(?P<port>[0-9]+))?
         (/(?P<dn>[^?]+))?
         .*""",
    re.IGNORECASE | re.VERBOSE,
)

InfoMode = Literal["NO_INFO", "DSA", "SCHEMA", "ALL"]


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

    # Validate the server certificate by default; `INSECURE_TLS=1` downgrades
    # to no verification (the flag is documented as dangerous). Previously the
    # Tls object was never constructed and ldap3 silently defaulted to
    # ssl.CERT_NONE, leaving TLS connections open to active MITM.
    tls = Tls(
        validate=ssl.CERT_NONE
        if settings.INSECURE_TLS
        else ssl.CERT_REQUIRED,
    )

    connection = Connection(
        Server(url, get_info=get_info, tls=tls),
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


@asynccontextmanager
async def ldap_connect() -> AsyncIterator[Connection]:
    """
    Open an anonymous LDAP connection and resolve the base/schema if possible.

    Best-effort resolution only: when the directory is ambiguous (multiple
    naming contexts), contradicts the configuration, or lacks a schema entry,
    the matching settings stay unset. Diagnosing those conditions is the job
    of the /api/probe endpoint, not the connection setup.

    The connection is always unbound on exit, no matter how the body ends.
    """

    url, base_dn = parse_url(settings.LDAP_URL)
    get_info: InfoMode = (
        "DSA"
        if (settings.BASE_DN is None and not base_dn) or settings.SCHEMA_DN is None
        else "NO_INFO"
    )
    connection = open(url, get_info)
    try:
        connection.bind()
        dsa_info = connection.server.info

        if not settings.BASE_DN:
            if base_dn:
                settings.BASE_DN = base_dn
            elif len(dsa_info.naming_contexts) == 1:
                settings.BASE_DN = dsa_info.naming_contexts[0]

        if not settings.SCHEMA_DN and dsa_info.schema_entry:
            settings.SCHEMA_DN = dsa_info.schema_entry[0]

        yield connection
    finally:
        try:
            connection.unbind()
        except Exception:  # noqa: BLE001, S110
            pass


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


def get_basic_credentials(authorization: str) -> tuple[str, str]:
    """
    Parse a HTTP Basic Authorization header.

    Raises LDAPInvalidCredentialsResult for malformed headers.
    """
    try:
        scheme, credentials = authorization.split(maxsplit=1)
    except ValueError:
        raise LDAPInvalidCredentialsResult(
            [{"desc": "Malformed Authorization header"}]
        )

    if scheme.lower() != "basic":
        raise LDAPInvalidCredentialsResult(
            [{"desc": f"Unsupported authorization scheme: {scheme}"}]
        )

    try:
        decoded = base64.b64decode(credentials, validate=True).decode("utf-8")
    except (UnicodeDecodeError, BinasciiError):
        raise LDAPInvalidCredentialsResult([{"desc": "Invalid Authorization header"}])

    if ":" not in decoded:
        raise LDAPInvalidCredentialsResult([{"desc": "Malformed Basic credentials"}])

    username, password = decoded.split(":", 1)
    return username, password


async def anonymous_user_search(connection: Connection, username: str) -> str | None:
    "Search anonymously for the user's bind DN"
    if not username:
        return None

    try:
        bind_user = await unique(
            connection,
            connection.search(
                require_base_dn(),
                search_filter=settings.GET_BIND_DN_FILTER(username),
            ),
        )
        return bind_user.dn
    except HTTPException:
        pass


async def find_bind_dn(connection: Connection, username: str) -> str | None:
    "Resolve the user's DN: from BIND_PATTERN, or by searching the directory"
    return settings.GET_BIND_PATTERN(username) or await anonymous_user_search(
        connection, username
    )


# Schema cache: lazy-initialized once, guarded by a lock because several
# concurrent requests may hit the empty cache simultaneously.
SCHEMA: SchemaInfo | None = None
_SCHEMA_LOCK = Lock()


def require_base_dn() -> str:
    "The base DN, or raise ValueError when it is unset"
    if not settings.BASE_DN:
        raise ValueError("An LDAP base DN is required")
    return settings.BASE_DN


def require_schema() -> SchemaInfo:
    "The cached schema, or raise ValueError when it is unavailable"
    if SCHEMA is None:
        raise ValueError("An LDAP schema is required")
    return SCHEMA


async def get_schema(connection: Connection) -> SchemaInfo:
    "Read the directory schema from the configured schema DN"
    if not settings.SCHEMA_DN:
        raise ValueError("An LDAP schema DN is required")
    response = await unique(
        connection,
        connection.search(
            settings.SCHEMA_DN,
            search_scope=BASE,
            get_operational_attributes=True,
            search_filter="(objectClass=*)",
        ),
    )
    return SchemaInfo(response, response.attributes, response.raw_attributes)


async def ensure_schema(connection: Connection) -> SchemaInfo:
    """
    Return the directory schema, loading it once.

    Concurrent requests only perform the schema search a single time: waiters
    re-check the global after acquiring the lock instead of fetching again.
    """
    global SCHEMA
    if SCHEMA is not None:
        return SCHEMA
    async with _SCHEMA_LOCK:
        if SCHEMA is None:
            SCHEMA = await get_schema(connection)
        return SCHEMA
