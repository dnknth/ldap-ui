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
from ldap import (  # type: ignore
    ALREADY_EXISTS,  # type: ignore
    INSUFFICIENT_ACCESS,  # type: ignore
    INVALID_CREDENTIALS,  # type: ignore
    NO_SUCH_OBJECT,  # type: ignore
    OBJECT_CLASS_VIOLATION,  # type: ignore
    UNWILLING_TO_PERFORM,  # type: ignore  # type: ignore
    LDAPError,  # type: ignore
)

from . import __version__, ldap_api, settings

# Main ASGI entry

app = FastAPI(debug=settings.DEBUG, title="LDAP UI", version=__version__)
app.include_router(ldap_api.api)
app.mount("/", StaticFiles(packages=["ldap_ui"], html=True))

app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)


@app.middleware("http")
async def cache_buster(request: Request, call_next) -> Response:
    "Forbid caching of API responses"
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# API error handling

LDAP_ERROR_TO_STATUS = {
    ALREADY_EXISTS: HTTPStatus.CONFLICT,
    INSUFFICIENT_ACCESS: HTTPStatus.FORBIDDEN,
    INVALID_CREDENTIALS: HTTPStatus.UNAUTHORIZED,
    NO_SUCH_OBJECT: HTTPStatus.NOT_FOUND,
    OBJECT_CLASS_VIOLATION: HTTPStatus.BAD_REQUEST,
    UNWILLING_TO_PERFORM: HTTPStatus.FORBIDDEN,
}


@app.exception_handler(LDAPError)
def handle_ldap_error(request: Request, exc: LDAPError) -> Response:
    "General handler for LDAP errors"

    exc_type = type(exc)
    if exc_type is UNWILLING_TO_PERFORM:
        logging.critical("Need BIND_DN or BIND_PATTERN to authenticate")

    if exc_type is INVALID_CREDENTIALS:
        return Response(
            status_code=HTTPStatus.UNAUTHORIZED,
            headers={
                "WWW-Authenticate": 'Basic realm="Please log in", charset="UTF-8"'
            },
        )

    if exc_type not in LDAP_ERROR_TO_STATUS:
        # Unknown error --> log it since FastApi won't do it for us
        logging.exception("Error in %s %s:", request.method, request.url, exc_info=exc)

    cause = exc.args[0] if exc.args else {}
    desc = cause.get("desc", "LDAP error").capitalize()
    msg = f"{desc}" if "info" not in cause else f"{desc}: {cause['info'].capitalize()}"
    return JSONResponse(
        {"detail": [msg]},
        status_code=LDAP_ERROR_TO_STATUS.get(
            exc_type, HTTPStatus.INTERNAL_SERVER_ERROR
        ),
    )
