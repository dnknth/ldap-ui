"""
Simplistic ReST proxy for LDAP access.

Authentication is either hard-wired in the settings,
or else only HTTP basic auth is supported.

The backend is stateless, it re-connects to the directory on every request.
No sessions, no cookies, nothing else.
"""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from ldap3.core.exceptions import (
    LDAPEntryAlreadyExistsResult,
    LDAPException,
    LDAPInsufficientAccessRightsResult,
    LDAPInvalidCredentialsResult,
    LDAPNoSuchObjectResult,
    LDAPObjectClassViolationResult,
    LDAPOperationResult,
    LDAPUnwillingToPerformResult,
)

from . import __version__, ldap_api, settings

# Main ASGI entry

app = FastAPI(debug=settings.DEBUG, title="LDAP UI", version=__version__)
app.include_router(ldap_api.api)
app.mount("/", StaticFiles(packages=["ldap_ui"], html=True))

app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)


@app.middleware("http")
async def http_headers(request: Request, call_next) -> Response:
    response = await call_next(request)

    # Forbid caching of API responses
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    # Always add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


# API error handling

LDAP_ERROR_TO_STATUS = {
    LDAPEntryAlreadyExistsResult: HTTPStatus.CONFLICT,
    LDAPInsufficientAccessRightsResult: HTTPStatus.FORBIDDEN,
    LDAPInvalidCredentialsResult: HTTPStatus.UNAUTHORIZED,
    LDAPNoSuchObjectResult: HTTPStatus.NOT_FOUND,
    LDAPObjectClassViolationResult: HTTPStatus.BAD_REQUEST,
    LDAPUnwillingToPerformResult: HTTPStatus.FORBIDDEN,
}


def camel_case_split(text: str) -> str:
    "Split camel case string into words"
    words = [[text[0].upper()]]
    for c in text[1:]:
        if words[-1][-1].islower() and c.isupper():
            words.append(list(c))
        else:
            words[-1].append(c)
    return " ".join(["".join(word) for word in words])


@app.exception_handler(LDAPException)
def handle_ldap_error(request: Request, exc: LDAPException) -> Response:
    "General handler for LDAP errors"

    exc_type = type(exc)
    if exc_type is LDAPInvalidCredentialsResult:
        # Return 401 without the WWW-Authenticate header: the header would
        # make the browser open its own native Basic-auth dialog whenever the
        # login form submits invalid credentials. The frontend only needs the
        # status code to reject and show its own error, so the header adds
        # only the unwanted native prompt.
        return Response(status_code=HTTPStatus.UNAUTHORIZED)

    if exc_type not in LDAP_ERROR_TO_STATUS:
        # Unknown error --> log it since FastApi won't do it for us
        logging.getLogger(__name__).exception(
            "Error in %s %s:", request.method, request.url, exc_info=exc
        )

    if isinstance(exc, LDAPOperationResult):
        desc = camel_case_split(exc.description) or "LDAP error"
        msg = f"{desc}: {exc.message}" if exc.message else desc
    else:
        msg = str(exc)
    return JSONResponse(
        {"detail": [msg]},
        status_code=LDAP_ERROR_TO_STATUS.get(
            exc_type, HTTPStatus.INTERNAL_SERVER_ERROR
        ),
    )
