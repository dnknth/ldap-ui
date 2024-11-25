"""
Simplistic ReST proxy for LDAP access.

Authentication is either hard-wired in the settings,
or else only HTTP basic auth is supported.

The backend is stateless, it re-connects to the directory on every request.
No sessions, no cookies, nothing else.
"""

import base64
import binascii
import logging
import sys
from http import HTTPStatus
from typing import Optional

from ldap import (
    INSUFFICIENT_ACCESS,  # pyright: ignore[reportAttributeAccessIssue]
    INVALID_CREDENTIALS,  # pyright: ignore[reportAttributeAccessIssue]
    SCOPE_BASE,  # pyright: ignore[reportAttributeAccessIssue]
    SCOPE_SUBTREE,  # pyright: ignore[reportAttributeAccessIssue]
    UNWILLING_TO_PERFORM,  # pyright: ignore[reportAttributeAccessIssue]
    LDAPError,  # pyright: ignore[reportAttributeAccessIssue]
)
from ldap.ldapobject import LDAPObject
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
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import HTTPConnection, Request
from starlette.responses import Response
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from . import settings
from .ldap_api import api
from .ldap_helpers import WITH_OPERATIONAL_ATTRS, empty, ldap_connect, unique

LOG = logging.getLogger("ldap-ui")


def ldap_exception_message(exc: LDAPError) -> str:
    args = exc.args[0]
    if "info" in args:
        return args.get("info", "") + ": " + args.get("desc", "")
    return args.get("desc", "")


if not settings.BASE_DN or not settings.SCHEMA_DN:
    # Try auto-detection from root DSE
    try:
        with ldap_connect() as connection:
            _dn, attrs = connection.search_s(  # pyright: ignore[reportAssignmentType, reportOptionalSubscript]
                "", SCOPE_BASE, attrlist=WITH_OPERATIONAL_ATTRS
            )[0]
            base_dns = attrs.get("namingContexts", [])
            if len(base_dns) == 1:
                settings.BASE_DN = settings.BASE_DN or base_dns[0].decode()
            else:
                LOG.warning("No unique base DN: %s", base_dns)
            schema_dns = attrs.get("subschemaSubentry", [])
            settings.SCHEMA_DN = settings.SCHEMA_DN or schema_dns[0].decode()
    except LDAPError as err:
        LOG.error(ldap_exception_message(err), exc_info=err)

if not settings.BASE_DN:
    LOG.critical("An LDAP base DN is required!")
    sys.exit(1)

if not settings.SCHEMA_DN:
    LOG.critical("An LDAP schema DN is required!")
    sys.exit(1)


async def anonymous_user_search(connection: LDAPObject, username: str) -> Optional[str]:
    try:
        # No BIND_PATTERN, try anonymous search
        dn, _attrs = await unique(
            connection,
            connection.search(
                settings.BASE_DN,
                SCOPE_SUBTREE,
                settings.GET_BIND_DN_FILTER(username),
            ),
        )
        return dn

    except HTTPException:
        pass  # No unique result


class LdapConnectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        "Add an authenticated LDAP connection to the request"

        # No authentication required for static files
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        try:
            with ldap_connect() as connection:
                # Hard-wired credentials
                dn = settings.GET_BIND_DN()
                password = settings.GET_BIND_PASSWORD()

                # Search for basic auth user
                if not dn and type(request.user) is LdapUser:
                    password = request.user.password
                    dn = settings.GET_BIND_PATTERN(
                        request.user.username
                    ) or await anonymous_user_search(connection, request.user.username)

                if dn:  # Log in
                    await empty(connection, connection.simple_bind(dn, password))
                    request.state.ldap = connection
                    return await call_next(request)

        except INVALID_CREDENTIALS:
            pass

        except INSUFFICIENT_ACCESS as err:
            return Response(
                ldap_exception_message(err),
                status_code=HTTPStatus.FORBIDDEN.value,
            )

        except UNWILLING_TO_PERFORM:
            LOG.warning("Need BIND_DN or BIND_PATTERN to authenticate")
            return Response(
                HTTPStatus.FORBIDDEN.phrase,
                status_code=HTTPStatus.FORBIDDEN.value,
            )

        except LDAPError as err:
            LOG.error(ldap_exception_message(err), exc_info=err)
            return Response(
                ldap_exception_message(err),
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            )

        return Response(
            HTTPStatus.UNAUTHORIZED.phrase,
            status_code=HTTPStatus.UNAUTHORIZED.value,
            headers={
                # Trigger authentication
                "WWW-Authenticate": 'Basic realm="Please log in", charset="UTF-8"'
            },
        )


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
        self, request: Request, call_next: RequestResponseEndpoint
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
    return Response(
        exc.detail,
        status_code=exc.status_code,
        headers=exc.headers,
    )


async def http_422(_request: Request, e: ValidationError) -> Response:
    "HTTP 422 Unprocessable Entity"
    LOG.warn("Invalid request body", exc_info=e)
    return Response(repr(e), status_code=HTTPStatus.UNPROCESSABLE_ENTITY.value)


# Main ASGI entry
app = Starlette(
    debug=settings.DEBUG,
    exception_handlers={  # pyright: ignore[reportArgumentType]
        HTTPException: http_exception,
        ValidationError: http_422,
    },
    middleware=(
        Middleware(AuthenticationMiddleware, backend=BasicAuthBackend()),
        Middleware(LdapConnectionMiddleware),
        Middleware(CacheBustingMiddleware),
        Middleware(GZipMiddleware, minimum_size=512, compresslevel=6),
    ),
    routes=[
        Mount("/api", app=api),
        Mount("/", StaticFiles(packages=["ldap_ui"], html=True)),
    ],
)
