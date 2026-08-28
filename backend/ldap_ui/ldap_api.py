"""
ReST endpoints for LDAP access.

Directory operations are exposed to the frontend
by a hand-knit ReST API, responses are usually converted to JSON.

Asynchronous LDAP operations are used as much as possible.
"""

import base64
import io
import re
from binascii import Error as BinasciiError
from collections.abc import AsyncGenerator
from enum import StrEnum
from http import HTTPStatus
from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import PlainTextResponse
from ldap3 import (
    ALL_ATTRIBUTES,
    BASE,
    LEVEL,
    MODIFY_ADD,
    MODIFY_DELETE,
    MODIFY_REPLACE,
    NONE,
    Connection,
    SchemaInfo,
)
from ldap3.core.exceptions import LDAPInvalidCredentialsResult, LDAPOperationResult
from ldap3.utils.conv import escape_filter_chars, to_raw
from ldap3.utils.dn import parse_dn, safe_dn
from ldif import LDIFParser

from . import settings
from .entities import (
    AttributeNames,
    Attributes,
    ChangePasswordRequest,
    Entry,
    Range,
    SearchResult,
    TreeItem,
)
from .ldap_connection import bound, ldap_connect, open, parse_url
from .ldap_helpers import ResponseEntry, empty, get_raw_responses, get_responses, unique
from .schema import INTEGER, Schema

NO_CONTENT = Response(status_code=HTTPStatus.NO_CONTENT)

# Special fields
PHOTOS = ("jpegPhoto", "thumbnailPhoto")
PASSWORDS = ("userPassword",)

# Default search filter
ANY = "(objectClass=*)"

# Safety
SAFE_FILENAME_RE = re.compile(r"[^a-z0-9._-]", re.IGNORECASE)
LDAP_ATTRIBUTE_RE = re.compile(r"^[a-z][a-z0-9-]*$", re.IGNORECASE)
WILDCARD = re.compile(r"\\2A", re.IGNORECASE)

# Schema cache
SCHEMA: SchemaInfo | None = None


api = APIRouter(prefix="/api")


async def authenticated(
    connection: Annotated[Connection, Depends(ldap_connect)],
    authorization: Annotated[str | None, Header()] = None,
) -> AsyncGenerator[Connection, None]:
    "Authenticate against the directory"

    # Hard-wired credentials
    dn = settings.GET_BIND_DN()
    password = settings.GET_BIND_PASSWORD()

    # Search for basic auth user
    if not dn and authorization:
        username, password = get_basic_credentials(authorization)

        if username is None or username == "":
            raise LDAPInvalidCredentialsResult([{"desc": "Username is required"}])

        # Prevent unauthenticated binds (RFC4513)
        if password is None or password == "":
            raise LDAPInvalidCredentialsResult(
                [{"desc": "Empty passwords are not allowed."}]
            )

        dn = settings.GET_BIND_PATTERN(username) or await anonymous_user_search(
            connection, username
        )

    if not dn:  # Log in
        connection.unbind()
        raise LDAPInvalidCredentialsResult(
            [{"desc": f"Invalid credentials for DN: {dn}"}]
        )

    async with bound(connection, dn, password):
        global SCHEMA
        if SCHEMA is None:
            SCHEMA = await get_schema(connection)

        yield connection


def get_basic_credentials(authorization: str) -> tuple[str, str]:
    """
    Parse a HTTP Basic Authorization header.

    Raises LDAPInvalidCredentialsResult for malformed headers.
    """
    try:
        scheme, credentials = authorization.split(maxsplit=1)
    except ValueError:
        raise LDAPInvalidCredentialsResult([{"desc": "Malformed Authorization header"}])

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
    if not username:
        return None

    try:
        bind_user = await unique(
            connection,
            connection.search(
                settings.BASE_DN,
                search_filter=settings.GET_BIND_DN_FILTER(username),
            ),
        )
        return bind_user.dn
    except HTTPException:
        pass


def build_content_disposition(filename: str) -> dict[str, str]:
    """
    Build a RFC6266 compliant Content-Disposition header.
    """

    safe = SAFE_FILENAME_RE.sub("_", filename)[:255]

    return {
        "Content-Disposition": f'attachment; filename="{safe}"; '
        f"filename*=UTF-8''{quote(filename)}",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }


async def get_schema(connection: Connection) -> SchemaInfo:
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


AuthenticatedConnection = Annotated[Connection, Depends(authenticated)]


class Tag(StrEnum):
    EDITING = "Editing"
    MISC = "Misc"
    NAVIGATION = "Navigation"


@api.get(
    "/tree/base",
    tags=[Tag.NAVIGATION],
    operation_id="get_base_entry",
    include_in_schema=False,  # Overlaps with next endpoint
)
async def get_base_entry(connection: AuthenticatedConnection) -> list[TreeItem]:
    "Get the directory base entry"

    if not settings.BASE_DN:
        raise ValueError("An LDAP base DN is required!")
    result = await unique(
        connection,
        connection.search(
            settings.BASE_DN,
            search_filter=ANY,
            search_scope=BASE,
            get_operational_attributes=True,
        ),
    )
    return [TreeItem.of(result)]


async def get_entry_by_dn(
    connection: Connection, dn: str, with_operational_attributes=False
) -> ResponseEntry:
    "Asynchronously retrieve an LDAP entry by its DN"

    return await unique(
        connection,
        connection.search(
            dn,
            search_filter=ANY,
            search_scope=BASE,
            attributes=ALL_ATTRIBUTES,
            get_operational_attributes=with_operational_attributes,
        ),
    )


@api.get("/tree/{basedn:path}", tags=[Tag.NAVIGATION], operation_id="get_tree")
async def get_tree(basedn: str, connection: AuthenticatedConnection) -> list[TreeItem]:
    "List directory entries below a DN"

    return [
        TreeItem.of(entry)
        async for entry in get_responses(
            connection,
            connection.search(
                basedn,
                search_filter=ANY,
                search_scope=LEVEL,
                get_operational_attributes=True,
            ),
        )
    ]


@api.get("/entry/{dn:path}", tags=[Tag.EDITING], operation_id="get_entry")
async def get_entry(dn: str, connection: AuthenticatedConnection) -> Entry:
    "Retrieve a directory entry by DN"
    return Entry.of(await get_entry_by_dn(connection, dn), SCHEMA)


@api.delete(
    "/entry/{dn:path}",
    status_code=HTTPStatus.NO_CONTENT,
    tags=[Tag.EDITING],
    operation_id="delete_entry",
)
async def delete_entry(dn: str, connection: AuthenticatedConnection) -> None:
    for entry_dn in sorted(
        [
            entry.dn
            async for entry in get_responses(
                connection,
                connection.search(dn, search_filter=ANY),
            )
        ],
        key=len,
        reverse=True,
    ):
        await empty(connection, connection.delete(entry_dn))


@api.post("/entry/{dn:path}", tags=[Tag.EDITING], operation_id="post_entry")
async def post_entry(
    dn: str, attributes: Attributes, connection: AuthenticatedConnection
) -> AttributeNames:
    entry = await get_entry_by_dn(connection, dn)
    if modifications := get_modifications(entry, attributes, SCHEMA):
        # Apply changes and send changed keys back
        await empty(connection, connection.modify(dn, modifications))
    return sorted(modifications)


Modification = tuple[str, list[str]]


def get_modifications(
    entry: ResponseEntry,
    attributes: Attributes,
    schema: SchemaInfo,
) -> dict[str, list[Modification]]:
    return {
        attr: modification
        for attr in attributes
        if (
            attr not in PASSWORDS
            and entry.is_updateable(attr, schema)
            and (modification := get_modification(attr, attributes[attr], entry))
            is not None
        )
    }


def get_modification(
    attr: str, values: list[str], entry: ResponseEntry
) -> Modification:
    values = list(filter(None, values))
    if not values:
        return (MODIFY_DELETE, [])
    elif attr not in entry.attributes:
        return (MODIFY_ADD, values)
    elif set(entry.raw_attributes[attr]) != set(to_raw(values)):
        return (MODIFY_REPLACE, values)


@api.put("/entry/{dn:path}", tags=[Tag.EDITING], operation_id="put_entry")
async def put_entry(
    dn: str, attributes: Attributes, connection: AuthenticatedConnection
) -> AttributeNames:

    if attributes := {
        attr: list(filter(None, attributes[attr]))
        for attr in attributes
        if attr not in PHOTOS
    }:
        await empty(connection, connection.add(dn, attributes=attributes))
    return ["dn"]  # Dummy


@api.post(
    "/rename/{dn:path}",
    status_code=HTTPStatus.NO_CONTENT,
    tags=[Tag.EDITING],
    operation_id="post_rename_entry",
)
async def rename_entry(
    dn: str,
    rdn: Annotated[str, Body()],
    connection: AuthenticatedConnection,
) -> None:
    "Rename an entry"
    entry = await get_entry_by_dn(connection, dn)

    try:
        new_dn = f"{rdn},{parent_dn(dn)}"
    except ValueError as exc:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            str(exc),
        ) from exc

    await empty(connection, connection.add(new_dn, attributes=entry.raw_attributes))
    try:
        await empty(connection, connection.delete(dn))
    except LDAPOperationResult:
        # Cannot delete Entry with subordinates -> Undo
        await empty(connection, connection.delete(new_dn))
        raise


def parent_dn(dn: str) -> str:
    """
    Return the parent DN.

    Works correctly even with escaped commas.
    """

    parsed = parse_dn(dn)

    if len(parsed) < 2:
        raise ValueError("DN has no parent")

    return safe_dn(["{}={}{}".format(*part) for part in parsed[1:]])


@api.get(
    "/blob/{attr}/{index}/{dn:path}",
    tags=[Tag.EDITING],
    operation_id="get_blob",
    include_in_schema=False,  # Not used in UI, images are transferred inline
)
async def get_blob(
    attr: str, index: int, dn: str, connection: AuthenticatedConnection
) -> Response:
    "Retrieve a binary attribute"

    validate_attribute_name(attr)
    entry = await get_entry_by_dn(connection, dn)

    if attr not in entry.raw_attributes or len(entry.raw_attributes[attr]) <= index:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"Attribute {attr} not found for DN {dn}"
        )

    return Response(
        entry.raw_attributes[attr][index],
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{attr}-{index:d}.bin"'},
    )


def validate_attribute_name(attribute: str) -> None:
    """
    Validate a user-supplied LDAP attribute name.

    Prevent malformed filters such as:

        (cn=foo)
        (uid=bar)
    """

    if not LDAP_ATTRIBUTE_RE.fullmatch(attribute):
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, detail=f"Invalid LDAP attribute: {attribute}"
        )


@api.put(
    "/blob/{attr}/{index}/{dn:path}",
    status_code=HTTPStatus.NO_CONTENT,
    tags=[Tag.EDITING],
    operation_id="put_blob",
)
async def put_blob(
    attr: str,
    index: int,
    dn: str,
    blob: Annotated[UploadFile, File()],
    connection: AuthenticatedConnection,
) -> None:
    "Upload a binary attribute"
    validate_attribute_name(attr)
    data = await blob.read(settings.MAX_BLOB_SIZE)
    if len(data) >= settings.MAX_BLOB_SIZE:
        raise HTTPException(413, "Blob too large")
    await empty(
        connection,
        connection.modify(dn, {attr: (MODIFY_ADD, [data])}),
    )


@api.delete(
    "/blob/{attr}/{index}/{dn:path}",
    status_code=HTTPStatus.NO_CONTENT,
    tags=[Tag.EDITING],
    operation_id="delete_blob",
)
async def delete_blob(
    attr: str, index: int, dn: str, connection: AuthenticatedConnection
) -> None:
    "Remove a binary attribute"
    validate_attribute_name(attr)
    entry = await get_entry_by_dn(connection, dn)
    if attr not in entry.raw_attributes or len(entry.raw_attributes[attr]) <= index:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"Attribute {attr} not found for DN {dn}"
        )
    data = entry.raw_attributes[attr][:index] + entry.raw_attributes[attr][index + 1 :]
    await empty(connection, connection.modify(dn, {attr: (MODIFY_REPLACE, data)}))


@api.post(
    "/check-password/{dn:path}", tags=[Tag.EDITING], operation_id="post_check_password"
)
async def check_password(
    dn: str,
    check: Annotated[str, Body()],
    _auth: AuthenticatedConnection,  # Always demand authentication
) -> bool:
    "Verify a password"

    url, _ = parse_url(settings.LDAP_URL)
    connection = open(url, NONE)

    try:
        async with bound(connection, dn, check):
            return True
    except LDAPInvalidCredentialsResult:
        return False


@api.post(
    "/change-password/{dn:path}",
    tags=[Tag.EDITING],
    operation_id="post_change_password",
    status_code=HTTPStatus.NO_CONTENT,
)
async def change_password(
    dn: str, args: ChangePasswordRequest, connection: AuthenticatedConnection
) -> None:
    "Update passwords"
    if args.new1:
        connection.extend.standard.modify_password(dn, args.old or None, args.new1)
    else:
        await empty(
            connection, connection.modify(dn, {"userPassword": (MODIFY_DELETE, [])})
        )


@api.get(
    "/ldif/{dn:path}",
    include_in_schema=False,  # Used as a link target, no API call
)
async def export_ldif(dn: str, connection: AuthenticatedConnection) -> Response:
    "Dump an entry as LDIF"

    out = io.StringIO()

    msgid = connection.search(dn, search_filter=ANY, attributes=ALL_ATTRIBUTES)
    async for entries in get_raw_responses(connection, msgid):
        out.write("# ")
        out.writelines(connection.response_to_ldif(entries))

    file_name = first_rdn_value(dn)
    return PlainTextResponse(
        out.getvalue(), headers=build_content_disposition(f"{file_name}.ldif")
    )


def first_rdn_value(dn: str) -> str:
    """
    Return the value of the first RDN.

    Example:

        cn=John Doe,ou=People,dc=example,dc=com

    returns

        John Doe
    """

    parsed = parse_dn(dn)

    if not parsed:
        raise ValueError("Invalid Distinguished Name")

    #
    # ldap3 returns tuples like:
    #
    # ('cn', 'John Doe', ',')
    #
    return parsed[0][1]


@api.put(
    "/ldif",
    tags=[Tag.EDITING],
    operation_id="put_ldif",
    status_code=HTTPStatus.NO_CONTENT,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/binary": {
                    "schema": {
                        "title": "LDIF data",
                        "type": "string",
                        "format": "binary",
                    }
                }
            }
        }
    },
)
async def upload_ldif(request: Request, connection: AuthenticatedConnection) -> None:
    "Import LDIF"

    body = await request.body()

    if len(body) > settings.MAX_LDIF_SIZE:
        raise HTTPException(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE, detail="LDIF too large"
        )

    parser = LDIFParser(io.BytesIO(body))
    try:
        for dn, record in parser.parse():
            await empty(connection, connection.add(dn, attributes=record))
    except ValueError as e:
        raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, e.args[0])


@api.get("/search/{query:path}", tags=[Tag.NAVIGATION], operation_id="search")
async def search(query: str, connection: AuthenticatedConnection) -> list[SearchResult]:
    "Search the directory"
    if len(query) < settings.SEARCH_QUERY_MIN:
        return []

    if "=" in query:  # Search specific attributes
        # Validate: split on first '=' and escape the value portion
        attr, _, val = query.partition("=")
        validate_attribute_name(attr)

        val = escape_search_value(val, allow_wildcards=True)
        query = f"({attr}={val})"
    else:  # Build default query
        escaped = escape_search_value(query)
        if "*" in query:
            # use exact match patterns (strip the implicit wildcard suffix)
            query = "(|{})".format(
                "".join(p.replace("*", "") % escaped for p in settings.SEARCH_PATTERNS)
            )
        else:
            query = "(|{})".format(
                "".join(p % escaped for p in settings.SEARCH_PATTERNS)
            )

    # Collect results
    res = []
    async for entry in get_responses(
        connection, connection.search(settings.BASE_DN, search_filter=query)
    ):
        res.append(
            SearchResult(
                dn=entry.dn,
                name=entry.attr("cn")[0] if "cn" in entry.attributes else entry.dn,
            )
        )
        if len(res) >= settings.SEARCH_MAX:
            break
    return res


def escape_search_value(value: str, allow_wildcards: bool = False) -> str:
    """
    Escape an LDAP search filter value according to RFC4515.

    Wildcards may optionally be preserved.
    """
    escaped = escape_filter_chars(value)
    return WILDCARD.sub("*", escaped) if allow_wildcards else escaped


@api.get("/whoami", tags=[Tag.MISC], operation_id="get_who_am_i")
async def whoami(connection: AuthenticatedConnection) -> str:
    "DN of the current user"
    return connection.user


@api.get("/subtree/{root_dn:path}", tags=[Tag.MISC], operation_id="get_subtree")
async def list_subtree(
    root_dn: str, connection: AuthenticatedConnection
) -> list[TreeItem]:
    "List the subtree below a DN"

    return sorted(
        [
            TreeItem.of(entry)
            async for entry in get_responses(
                connection,
                connection.search(
                    root_dn,
                    search_filter=ANY,
                    attributes=ALL_ATTRIBUTES,
                    get_operational_attributes=True,
                ),
            )
            if root_dn != entry.dn
        ],
        key=lambda item: tuple(reversed(item.dn.lower().split(","))),
    )


@api.get("/range/{attribute}", tags=[Tag.MISC], operation_id="get_range")
async def attribute_range(attribute: str, connection: AuthenticatedConnection) -> Range:
    "List all values for a numeric attribute of an objectClass like uidNumber or gidNumber"

    validate_attribute_name(attribute)
    obj = SCHEMA.attribute_types[attribute]

    values = {
        int(entry.raw_attributes[attribute][0])
        async for entry in get_responses(
            connection,
            connection.search(
                settings.BASE_DN,
                search_filter=f"({attribute}=*)",
                attributes=(attribute,),
            ),
        )
        if obj and obj.syntax == INTEGER
    }

    if not values:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"No values found for attribute {attribute}"
        )

    minimum, maximum = min(values), max(values)
    return Range(
        min=minimum,
        max=maximum,
        next=min(set(range(minimum, maximum + 2)) - values),
    )


@api.get(
    "/schema",
    tags=[Tag.MISC],
    operation_id="get_schema",
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def ldap_schema(connection: AuthenticatedConnection) -> Schema:
    "Dump the LDAP schema as JSON"
    if SCHEMA is None:
        raise ValueError("An LDAP schema is required!")
    return Schema.of(SCHEMA)
