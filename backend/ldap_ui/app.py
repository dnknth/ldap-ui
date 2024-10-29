"""
Simplistic ReST proxy for LDAP access.

Authentication is either hard-wired in the settings,
or else only HTTP basic auth is supported.

The backend is stateless, it re-connects to the directory on every request.
No sessions, no cookies, nothing else.
"""

import base64
import binascii
import contextlib
import logging
import sys
from typing import AsyncGenerator

import ldap
from ldap.schema import SubSchema
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
)
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import HTTPConnection, Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from . import settings
from .ldap_api import api
from .ldap_helpers import WITH_OPERATIONAL_ATTRS, empty, ldap_connect, unique

LOG = logging.getLogger("ldap-ui")

if not settings.BASE_DN:
    LOG.critical("An LDAP base DN is required!")
    sys.exit(1)

LOG.debug("Base DN: %s", settings.BASE_DN)

# Force authentication
UNAUTHORIZED = Response(
    "Invalid credentials",
    status_code=401,
    headers={"WWW-Authenticate": 'Basic realm="Please log in", charset="UTF-8"'},
)


class LdapConnectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: AsyncGenerator[Request, Response]
    ) -> Response:
        "Add an authenticated LDAP connection to the request"

        # Short-circuit static files
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        try:
            with ldap_connect() as connection:
                dn, password = None, None

                # Search for basic auth user
                if type(request.user) is LdapUser:
                    dn = settings.GET_BIND_PATTERN(request.user.username)
                    if dn is None:
                        dn, _attrs = await unique(
                            connection,
                            connection.search(
                                settings.BASE_DN,
                                ldap.SCOPE_SUBTREE,
                                settings.GET_BIND_DN_FILTER(request.user.username),
                            ),
                        )
                    password = request.user.password

                # Hard-wired credentials
                if dn is None:
                    dn = settings.GET_BIND_DN(request.user.display_name)
                    password = settings.GET_BIND_PASSWORD()

                if dn is None:
                    return UNAUTHORIZED

                # Log in
                await empty(connection, connection.simple_bind(dn, password))
                request.state.ldap = connection
                return await call_next(request)

        except ldap.INVALID_CREDENTIALS:
            return UNAUTHORIZED

        except ldap.LDAPError as err:
            msg = ldap_exception_message(err)
            LOG.error(msg)
            return PlainTextResponse(
                msg,
                status_code=500,
            )


def ldap_exception_message(exc: ldap.LDAPError) -> str:
    args = exc.args[0]
    if "info" in args:
        return args.get("info", "") + ": " + args.get("desc", "")
    return args.get("desc", "")


class LdapUser(SimpleUser):
    "LDAP credentials"

    def __init__(self, username: str, password: str):
        super().__init__(username)
        self.password = password


class BasicAuthBackend(AuthenticationBackend):
    "Handle basic authentication"

    async def authenticate(self, conn: HTTPConnection):
        "Place LDAP credentials in request.user"

        if "Authorization" in conn.headers:
            try:
                auth = conn.headers["Authorization"]
                scheme, credentials = auth.split()
                if scheme.lower() == "basic":
                    decoded = base64.b64decode(credentials).decode("ascii")
                    username, _, password = decoded.partition(":")
                    return (
                        AuthCredentials(["authenticated"]),
                        LdapUser(username, password),
                    )
            except (ValueError, UnicodeDecodeError, binascii.Error) as _exc:
                raise AuthenticationError("Invalid basic auth credentials")


class CacheBustingMiddleware(BaseHTTPMiddleware):
    "Forbid caching of API responses"

    async def dispatch(
        self, request: Request, call_next: AsyncGenerator[Request, Response]
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


async def http_exception(_request: Request, exc: HTTPException) -> Response:
    "Send error responses"
    assert exc.status_code >= 400
    if exc.status_code < 500:
        LOG.warning(exc.detail)
    else:
        LOG.error(exc.detail)
    return PlainTextResponse(
        exc.detail,
        status_code=exc.status_code,
        headers=exc.headers,
    )


async def forbidden(_request: Request, exc: ldap.LDAPError) -> Response:
    "HTTP 403 Forbidden"
    return PlainTextResponse(ldap_exception_message(exc), status_code=403)


async def http_422(_request: Request, e: ValidationError) -> Response:
    "HTTP 422 Unprocessable Entity"
    LOG.warn("Invalid request body", exc_info=e)
    return Response(repr(e), status_code=422)


@contextlib.asynccontextmanager
async def lifespan(app):
    with ldap_connect() as connection:
        # See: https://hub.packtpub.com/python-ldap-applications-part-4-ldap-schema/
        _dn, sub_schema = await unique(
            connection,
            connection.search(
                settings.SCHEMA_DN,
                ldap.SCOPE_BASE,
                attrlist=WITH_OPERATIONAL_ATTRS,
            ),
        )
        app.state.schema = SubSchema(sub_schema, check_uniqueness=2)
        yield


# Main ASGI entry
app = Starlette(
    debug=settings.DEBUG,
    exception_handlers={
        HTTPException: http_exception,
        ldap.INSUFFICIENT_ACCESS: forbidden,
        ValidationError: http_422,
    },
    lifespan=lifespan,
    middleware=(
        Middleware(AuthenticationMiddleware, backend=BasicAuthBackend()),
        Middleware(LdapConnectionMiddleware),
        Middleware(CacheBustingMiddleware),
        Middleware(GZipMiddleware, minimum_size=512, compresslevel=6),
    ),
    routes=[
        Mount("/api", routes=api.routes),
        Mount("/", StaticFiles(packages=["ldap_ui"], html=True)),
    ],
)
