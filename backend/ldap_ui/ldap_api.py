"""
ReST endpoints for LDAP access.

Directory operations are exposed to the frontend
by a hand-knit ReST API, responses are usually converted to JSON.

Asynchronous LDAP operations are used as much as possible.
"""

import io
import re
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
    Security,
    UploadFile,
)
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBasic
from ldap3 import (
    ALL_ATTRIBUTES,
    BASE,
    LEVEL,
    MODIFY_ADD,
    MODIFY_DELETE,
    MODIFY_REPLACE,
    Connection,
    SchemaInfo,
)
from ldap3.core.exceptions import (
    LDAPInvalidCredentialsResult,
    LDAPInvalidDnError,
    LDAPOperationResult,
)
from ldap3.protocol.rfc3062 import PasswdModifyRequestValue
from ldap3.utils.conv import escape_filter_chars, to_raw
from ldap3.utils.dn import parse_dn, safe_dn
from ldif import LDIFParser

from . import settings
from .entities import (
    RANGE_LIMIT,
    AttributeNames,
    Attributes,
    ChangePasswordRequest,
    Entry,
    ProbeResult,
    Range,
    SearchResult,
    TreeItem,
)
from .ldap_connection import (
    bound,
    ensure_schema,
    find_bind_dn,
    get_basic_credentials,
    ldap_connect,
    open,
    parse_url,
    rate_limit,
    require_base_dn,
    require_schema,
)
from .ldap_helpers import ResponseEntry, empty, get_raw_responses, get_responses, unique
from .probe import run_probe
from .schema import INTEGER, Schema, normalize_dn

# Special fields
PHOTOS = ("jpegPhoto", "thumbnailPhoto")
PASSWORDS = ("userPassword",)

# RFC 2307 password scheme prefixes. A userPassword value without one is
# stored as plaintext, and {CLEARTEXT}/{PLAIN} mark plaintext explicitly:
# neither may ever be exported (#1).
PASSWORD_SCHEME = re.compile(r"^\{[a-z0-9-]+\}", re.IGNORECASE)
PLAINTEXT_SCHEMES = ("CLEARTEXT", "PLAIN")

# Default search filter
ANY = "(objectClass=*)"

# RFC 3062 password modify extended operation
PASSWORD_MODIFY_OID = "1.3.6.1.4.1.4203.1.11.1"

# Safety
SAFE_FILENAME_RE = re.compile(r"[^a-z0-9._-]", re.IGNORECASE)
LDAP_ATTRIBUTE_RE = re.compile(r"^[a-z][a-z0-9-]*$", re.IGNORECASE)
WILDCARD = re.compile(r"\\2A", re.IGNORECASE)


async def authenticated(
    authorization: Annotated[str | None, Header()] = None,
) -> AsyncGenerator[Connection, None]:
    "Authenticate against the directory"

    if not authorization:
        raise LDAPInvalidCredentialsResult([{"desc": "Credentials required"}])

    username, password = get_basic_credentials(authorization)

    if not username:
        raise LDAPInvalidCredentialsResult([{"desc": "Username is required"}])

    # Prevent unauthenticated binds (RFC4513)
    if not password:
        raise LDAPInvalidCredentialsResult(
            [{"desc": "Empty passwords are not allowed."}]
        )

    async with ldap_connect() as connection:
        dn = await find_bind_dn(connection, username)

        if not dn:  # Log in
            await rate_limit()
            raise LDAPInvalidCredentialsResult([{"desc": "Invalid credentials for DN"}])

        async with bound(connection, dn, password):
            await ensure_schema(connection)
            yield connection


async def optional_authenticated(
    authorization: Annotated[str | None, Header()] = None,
) -> AsyncGenerator[Connection | None, None]:
    "Authenticate against the directory, or yield None if no credentials are supplied"

    if not authorization:
        # No credentials: don't even open an anonymous LDAP connection. The
        # probe endpoint must never 401 (which would trigger the browser's
        # native Basic-auth dialog), and an anonymous bind could be rejected
        # by the directory.
        yield None
        return

    username, password = get_basic_credentials(authorization)

    if not username or not password:
        yield None
        return

    async with ldap_connect() as connection:
        dn = await find_bind_dn(connection, username)

        if not dn:  # Log in
            await rate_limit()
            yield None
            return

        async with bound(connection, dn, password):
            yield connection


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


AuthenticatedConnection = Annotated[Connection, Depends(authenticated)]


class Tag(StrEnum):
    EDITING = "Editing"
    MISC = "Misc"
    NAVIGATION = "Navigation"


api = APIRouter(prefix="/api", dependencies=[Security(HTTPBasic(auto_error=False))])


@api.get(
    "/tree/base",
    tags=[Tag.NAVIGATION],
    operation_id="get_base_entry",
    include_in_schema=False,  # Overlaps with next endpoint
)
async def get_base_entry(connection: AuthenticatedConnection) -> list[TreeItem]:
    "Get the directory base entry"

    result = await unique(
        connection,
        connection.search(
            require_base_dn(),
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
    return Entry.of(await get_entry_by_dn(connection, dn), require_schema())


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
    validate_attribute_names(attributes)
    entry = await get_entry_by_dn(connection, dn)
    if modifications := get_modifications(entry, attributes, require_schema()):
        # Apply changes and send changed keys back
        await empty(connection, connection.modify(dn, modifications))
    return sorted(modifications)


Modification = tuple[str, list[str]]


def get_modifications(
    entry: ResponseEntry,
    attributes: Attributes,
    schema: SchemaInfo,
) -> dict[str, Modification]:
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
) -> Modification | None:
    values = list(filter(None, values))
    if not values:
        return (MODIFY_DELETE, [])
    if attr not in entry.attributes:
        return (MODIFY_ADD, values)
    if set(entry.raw_attributes[attr]) != set(to_raw(values)):
        return (MODIFY_REPLACE, values)


@api.put(
    "/entry/{dn:path}",
    status_code=HTTPStatus.NO_CONTENT,
    tags=[Tag.EDITING],
    operation_id="put_entry",
)
async def put_entry(
    dn: str, attributes: Attributes, connection: AuthenticatedConnection
) -> None:

    validate_attribute_names(attributes)
    if attributes := {
        attr: list(filter(None, attributes[attr]))
        for attr in attributes
        if attr not in PHOTOS
    }:
        await empty(connection, connection.add(dn, attributes=attributes))


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

    # Validate the RDN: a single attribute=value pair. parse_dn rejects
    # malformed RDNs (unescaped special characters) and splits on unescaped
    # commas, so a crafted value like "a=b,dc=evil" cannot escape the parent.
    try:
        new_rdn = parse_dn(rdn)
    except LDAPInvalidDnError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, f"Invalid RDN: {rdn}") from exc

    if len(new_rdn) != 1:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            "RDN must be a single attribute=value pair",
        )

    # Build the new DN from the parsed components, dropping the old first RDN.
    # Reconstructing with safe_dn escapes each RDN component (commas, special
    # characters) instead of concatenating raw strings.
    try:
        parent = parse_dn(dn)[1:]
    except LDAPInvalidDnError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, f"Invalid DN: {dn}") from exc

    if not parent:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Entry has no parent")

    new_dn = safe_dn([f"{part[0]}={part[1]}" for part in [*new_rdn, *parent]])

    # The new entry must carry the renamed attribute's value so the RDN and
    # the attribute stay consistent: renaming cn=test → sn=baz must yield a
    # new entry whose sn is "baz", not the old value ("test").
    attrs = dict(entry.raw_attributes)
    renamed_attr = new_rdn[0][0].lower()
    attrs[renamed_attr] = [new_rdn[0][1].encode()]

    await empty(connection, connection.add(new_dn, attributes=attrs))
    try:
        await empty(connection, connection.delete(dn))
    except LDAPOperationResult:
        # Cannot delete Entry with subordinates -> Undo
        await empty(connection, connection.delete(new_dn))
        raise


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


def validate_attribute_names(attributes: Attributes) -> None:
    "Validate every attribute name in a request, rejecting malformed ones"
    for attribute in attributes:
        validate_attribute_name(attribute)


async def get_blob_values(
    connection: Connection, dn: str, attr: str, index: int
) -> list[bytes]:
    "Fetch the binary values of an attribute, validating the attribute and index"

    validate_attribute_name(attr)
    entry = await get_entry_by_dn(connection, dn)

    if attr not in entry.raw_attributes or len(entry.raw_attributes[attr]) <= index:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"Attribute {attr} not found for DN {dn}"
        )

    return entry.raw_attributes[attr]


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
    values = await get_blob_values(connection, dn, attr, index)
    data = values[:index] + values[index + 1 :]
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
    connection = open(url, "NO_INFO")

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
    if not args.new1:
        await empty(
            connection, connection.modify(dn, {"userPassword": (MODIFY_DELETE, [])})
        )
        return

    # Changing your own password requires the old one: the password-modify
    # extended operation skips verification when the old password is omitted,
    # which would turn this endpoint into a silent password reset. The old
    # password stays optional for administrative changes on other entries.
    if is_self(connection, dn) and not args.old:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            "The old password is required to change your own password",
        )

    # Issue the password-modify extended op asynchronously (the blocking
    # modify_password() would stall the event loop); failures raise out of
    # get_response() and are surfaced by the error handler.
    value = PasswdModifyRequestValue()
    if connection.check_names:
        value["userIdentity"] = safe_dn(dn)
    else:
        value["userIdentity"] = dn
    if args.old:
        value["oldPasswd"] = args.old
    value["newPasswd"] = args.new1

    msgid = connection.extended(PASSWORD_MODIFY_OID, value)
    await empty(connection, msgid)


def is_self(connection: Connection, dn: str) -> bool:
    "Is the given DN the currently authenticated user?"
    if not connection.user:
        return False
    try:
        return normalize_dn(connection.user, require_schema()) == normalize_dn(
            dn, require_schema()
        )
    except LDAPInvalidDnError:
        return False


def is_hashed_password(value: bytes | str) -> bool:
    """
    Whether an LDAP userPassword value is a hash rather than plaintext.

    A hash carries an RFC 2307 scheme prefix ({SSHA}, {SHA}, {MD5}, {CRYPT},
    ...). Values without a prefix, or with an explicit {CLEARTEXT}/{PLAIN}
    prefix, are plaintext and must never be exported.
    """
    text = (
        value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    )
    match = PASSWORD_SCHEME.match(text)
    if not match:
        return False
    return match.group(0)[1:-1].upper() not in PLAINTEXT_SCHEMES


def sanitize_export_entries(entries: list[dict]) -> list[dict]:
    """
    Prepare LDAP search response entries for LDIF export (#1).

    userPassword values are exported only if they are hashes; plaintext
    passwords are never exported, even when the directory stores them that
    way. Other sensitive attributes (userPKCS12) are exported as-is.
    """
    result = []
    for entry in entries:
        if not (isinstance(entry, dict) and entry.get("type") == "searchResEntry"):
            result.append(entry)
            continue
        raw = entry.get("raw_attributes") or {}
        filtered = dict(raw)
        changed = False
        for attr in list(filtered):
            if attr.lower() == "userpassword":
                values = filtered[attr]
                values = values if isinstance(values, list) else [values]
                kept = [v for v in values if is_hashed_password(v)]
                if len(kept) != len(values):
                    changed = True
                if kept:
                    filtered[attr] = kept
                else:
                    del filtered[attr]
        if changed:
            entry = dict(entry)
            entry["raw_attributes"] = filtered
        result.append(entry)
    return result


@api.get(
    "/ldif/{dn:path}",
    include_in_schema=False,  # Downloaded via the authenticated client, not an API call
)
async def export_ldif(dn: str, connection: AuthenticatedConnection) -> Response:
    "Dump an entry as LDIF"

    out = io.StringIO()

    msgid = connection.search(dn, search_filter=ANY, attributes=ALL_ATTRIBUTES)
    async for entries in get_raw_responses(connection, msgid):
        out.write("# ")
        entries = sanitize_export_entries(entries)
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

    # Reject early on the declared size before buffering the body, so a large
    # upload cannot spike memory past MAX_LDIF_SIZE even if the limit is small.
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.MAX_LDIF_SIZE:
        raise HTTPException(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE, detail="LDIF too large"
        )

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


def first_value(entry: ResponseEntry, attr: str) -> str | None:
    """
    Return the first value of an attribute as text, if present.

    The response exposes both decoded (`attributes`) and raw byte
    (`raw_attributes`) values; either may be empty depending on how the
    search was requested.
    """
    for value in entry.attributes.get(attr) or entry.raw_attributes.get(attr) or ():
        return value.decode() if isinstance(value, bytes) else str(value)
    return None


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
        connection, connection.search(require_base_dn(), search_filter=query)
    ):
        res.append(
            SearchResult(
                dn=entry.dn,
                name=first_value(entry, "cn") or entry.dn,
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
async def whoami(
    connection: Annotated[Connection | None, Depends(optional_authenticated)],
) -> str:
    "DN of the current user"
    return connection.user if connection else ""


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
    """List all values for a numeric attribute of an objectClass like uidNumber or gidNumber.

    The returned range is bounded to 0..60000: min/max are clamped into that window,
    and 'next' is a free value within it (or the upper bound when the window is full).
    """

    validate_attribute_name(attribute)
    obj = require_schema().attribute_types[attribute]

    values = {
        int(entry.raw_attributes[attribute][0])
        async for entry in get_responses(
            connection,
            connection.search(
                require_base_dn(),
                search_filter=f"({attribute}=*)",
                attributes=(attribute,),
            ),
        )
        if obj.syntax == INTEGER
    }

    if not values:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"No values found for attribute {attribute}"
        )

    return bounded_range(values)


def bounded_range(values: set[int], limit: int = RANGE_LIMIT) -> Range:
    """
    Compute the numeric range of the given values, bounded to 0..limit.

    The bound keeps the next-free computation from allocating an unbounded
    set of integers spanning directory data (#4), and guarantees the response
    always satisfies the Range model constraints (min/max/next in 0..RANGE_LIMIT).
    If every value lies outside the bound, the window collapses onto the
    nearest edge (0 or the limit).
    """

    minimum, maximum = min(values), max(values)
    minimum = max(0, minimum)
    maximum = min(limit, maximum)
    if minimum > maximum:  # Every value is outside the bound
        minimum = maximum = limit if maximum >= 0 else 0
    unused = set(range(minimum, maximum + 2)) - values
    return Range(
        min=minimum,
        max=maximum,
        next=min(unused) if unused else maximum,
    )


@api.get("/probe", tags=[Tag.MISC], operation_id="probe", response_model=ProbeResult)
async def probe() -> ProbeResult:
    "Probe the LDAP directory connectivity and configuration."
    return await run_probe()


@api.get(
    "/health",
    tags=[Tag.MISC],
    operation_id="health",
    response_model=ProbeResult,
    responses={
        HTTPStatus.SERVICE_UNAVAILABLE: {
            "description": "The LDAP directory is unreachable or not usable",
            "model": ProbeResult,
        }
    },
)
async def health(response: Response) -> ProbeResult:
    "Probe the LDAP directory; 503 when it is unreachable or not usable."
    result = await run_probe()
    if not result.ok:
        response.status_code = HTTPStatus.SERVICE_UNAVAILABLE
    return result


@api.get(
    "/schema",
    tags=[Tag.MISC],
    operation_id="get_schema",
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def ldap_schema(connection: AuthenticatedConnection) -> Schema:
    "Dump the LDAP schema as JSON"
    return Schema.of(require_schema())
