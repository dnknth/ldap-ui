"""
ReST endpoints for LDAP access.

Directory operations are exposed to the frontend
by a hand-knit ReST API, responses are usually converted to JSON.

Asynchronous LDAP operations are used as much as possible.
"""

import base64
import io
import re
from enum import StrEnum
from http import HTTPStatus
from typing import Annotated, AsyncGenerator, cast

from anyio import sleep
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
    ALL,
    ALL_ATTRIBUTES,
    ALL_OPERATIONAL_ATTRIBUTES,
    ASYNC,
    BASE,
    LEVEL,
    MODIFY_ADD,
    MODIFY_DELETE,
    MODIFY_REPLACE,
    Connection,
    SchemaInfo,
    Server,
)
from ldap3.core.exceptions import (
    LDAPInvalidCredentialsResult,
    LDAPOperationResult,
    LDAPResponseTimeoutError,
)
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
from .ldap_helpers import ResponseEntry, empty, get_responses, unique
from .schema import Schema

NO_CONTENT = Response(status_code=HTTPStatus.NO_CONTENT)

# Special fields
PHOTOS = ("jpegPhoto", "thumbnailPhoto")
PASSWORDS = ("userPassword",)

# Special syntaxes
INTEGER = "1.3.6.1.4.1.1466.115.121.1.27"

# Default search filter
ANY = "(objectClass=*)"

URL_PATTERN = re.compile(
    r"""^(?P<scheme>ldap|ldapi|ldaps)://
         (?P<host>[/A-Za-z0-9_.-]*)
         (:(?P<port>[0-9]+))?
         (/(?P<dn>[^?]+))?
         .*""",
    re.IGNORECASE | re.VERBOSE,
)

api = APIRouter(prefix="/api")


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
        while host.endswith("/"):
            # ldap3 is not particularly smart with server URLs
            host = host[:-1]
        url = f"{scheme}://{host}"
        if scheme != "ldapi" and parts["port"]:
            url += f":{parts['port']}"
        return url, parts["dn"]

    raise ValueError(f"Invalid URL: {url}")


async def ldap_connect() -> Connection:
    "Open an anonymous LDAP connection"

    url, base_dn = parse_url(settings.LDAP_URL)
    server = Server(url, get_info=ALL)
    connection = Connection(server, client_strategy=ASYNC, raise_exceptions=True)
    connection.bind()
    dsa_info = connection.server.info

    if not settings.BASE_DN:
        if base_dn:
            settings.BASE_DN = base_dn
        else:
            base_dns = dsa_info.naming_contexts
            assert len(base_dns) == 1, f"No unique base DN: {base_dns}"
            settings.BASE_DN = base_dns[0]

    elif base_dn and base_dn != settings.BASE_DN:
        raise ValueError(f"Contradicting base DNs: {base_dn} vs. {settings.BASE_DN}")

    if not settings.SCHEMA_DN:
        assert dsa_info.schema_entry, "Cannot determine LDAP schema"
        settings.SCHEMA_DN = dsa_info.schema_entry[0]

    if settings.USE_TLS and url.startswith("ldap://"):
        connection.start_tls()

    return connection


async def authenticated(
    authorization: Annotated[str | None, Header()] = None,
) -> AsyncGenerator[Connection, None]:
    "Authenticate against the directory"

    connection = await ldap_connect()

    # Hard-wired credentials
    dn = settings.GET_BIND_DN()
    password = settings.GET_BIND_PASSWORD()

    # Search for basic auth user
    if not dn and authorization:
        username, password = get_basic_credentials(authorization)
        dn = settings.GET_BIND_PATTERN(username) or await anonymous_user_search(
            connection, username
        )

    if not dn:  # Log in
        raise LDAPInvalidCredentialsResult(
            [{"desc": f"Invalid credentials for DN: {dn}"}]
        )

    connection.rebind(user=dn, password=password)
    yield connection
    connection.unbind()


def get_basic_credentials(authorization: str) -> list[str]:
    scheme, credentials = authorization.split(maxsplit=1)
    if scheme.lower() == "basic":
        return base64.b64decode(credentials).decode().split(":", maxsplit=1)

    raise LDAPInvalidCredentialsResult(
        [{"desc": f"Unsupported authorization scheme: {scheme}"}]
    )


async def anonymous_user_search(connection: Connection, username: str) -> str | None:
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
        pass  # No unique result


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

    assert settings.BASE_DN, "An LDAP base DN is required!"
    result = await unique(
        connection,
        connection.search(
            settings.BASE_DN,
            search_filter=ANY,
            search_scope=BASE,
            attributes=ALL_OPERATIONAL_ATTRIBUTES,
        ),
    )
    return [TreeItem.of(result)]


async def get_entry_by_dn(
    connection: Connection,
    dn: str,
) -> ResponseEntry:
    "Asynchronously retrieve an LDAP entry by its DN"

    return await unique(
        connection,
        connection.search(
            dn,
            search_filter=ANY,
            search_scope=BASE,
            attributes=ALL_ATTRIBUTES,
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
                attributes=ALL_OPERATIONAL_ATTRIBUTES,
            ),
        )
    ]


@api.get("/entry/{dn:path}", tags=[Tag.EDITING], operation_id="get_entry")
async def get_entry(dn: str, connection: AuthenticatedConnection) -> Entry:
    "Retrieve a directory entry by DN"
    return Entry.of(
        await get_entry_by_dn(connection, dn),
        connection.server.schema,
    )


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
    if modifications := get_modifications(entry, attributes, connection.server.schema):
        # Apply changes and send changed keys back
        await empty(connection, connection.modify(dn, modifications))
    return sorted(modifications)


Modification = tuple[str, list[str]]


def get_modifications(
    entry: ResponseEntry,
    attributes: Attributes,
    schema: SchemaInfo,
) -> dict[str, list[Modification]]:
    attributes = {
        attr: list(filter(None, (attributes[attr])))
        for attr in attributes
        if attr not in PASSWORDS
        and (
            attr not in entry.raw_attributes
            # FIXME Handle binary attributes properly
            or not entry.is_binary(attr, schema)
        )
    }

    modifications = {}
    for attr, values in attributes.items():
        if not values:
            modifications[attr] = (MODIFY_DELETE, [])
        elif attr not in entry.attributes:
            modifications[attr] = (MODIFY_ADD, values)
        else:
            new_values = {s.encode("UTF-8") for s in values}
            old_values = set(entry.raw_attributes[attr])
            if new_values != old_values:
                modifications[attr] = (MODIFY_REPLACE, values)
    return modifications


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

    parent_dn = dn.split(",", 1)[1]
    new_dn = f"{rdn},{parent_dn}"
    await empty(connection, connection.add(new_dn, attributes=entry.raw_attributes))
    try:
        await empty(connection, connection.delete(dn))
    except LDAPOperationResult:
        # Cannot delete Entry with subordinates -> Undo
        await empty(connection, connection.delete(new_dn))
        raise


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
    data = await blob.read(cast(int, blob.size))
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
    dn: str, check: Annotated[str, Body()], connection: AuthenticatedConnection
) -> bool:
    "Verify a password"

    try:
        connection.rebind(user=dn, password=check)
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
    assert type(msgid) is int, "Expected async operation"
    while True:
        try:
            entries, result = connection.get_response(msgid, timeout=0)
            out.write("# ")
            out.writelines(connection.response_to_ldif(entries))
            break
        except LDAPResponseTimeoutError:
            await sleep(0.01)

    file_name = dn.split(",")[0].split("=")[1]
    return PlainTextResponse(
        out.getvalue(),
        headers={"Content-Disposition": f'attachment; filename="{file_name}.ldif"'},
    )


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

    parser = LDIFParser(io.BytesIO(await request.body()))
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
        if "(" not in query:
            query = f"({query})"
    else:  # Build default query
        if "*" in query:  # disable implicit prefix searches
            query = "(|%s)" % "".join(
                p.replace("*", "") % query for p in settings.SEARCH_PATTERNS
            )
        else:
            query = "(|%s)" % "".join(p % query for p in settings.SEARCH_PATTERNS)

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
                    root_dn, search_filter=ANY, attributes=ALL_OPERATIONAL_ATTRIBUTES
                ),
            )
            if root_dn != entry.dn
        ],
        key=lambda item: tuple(reversed(item.dn.lower().split(","))),
    )


@api.get("/range/{attribute}", tags=[Tag.MISC], operation_id="get_range")
async def attribute_range(attribute: str, connection: AuthenticatedConnection) -> Range:
    "List all values for a numeric attribute of an objectClass like uidNumber or gidNumber"

    schema = connection.server.schema
    obj = schema.attribute_types[attribute]

    values = set(
        [
            int(entry.attributes[attribute])
            async for entry in get_responses(
                connection,
                connection.search(
                    settings.BASE_DN,
                    search_filter=f"({attribute}=*)",
                    attributes=(attribute,),
                ),
            )
            if obj and obj.syntax == INTEGER
        ]
    )

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
    assert settings.SCHEMA_DN, "An LDAP schema DN is required!"
    return Schema.of(connection.server.schema)
