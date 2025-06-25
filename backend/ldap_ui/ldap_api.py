"""
ReST endpoints for LDAP access.

Directory operations are exposed to the frontend
by a hand-knit ReST API, responses are usually converted to JSON.

Asynchronous LDAP operations are used as much as possible.
"""

import base64
import io
from enum import StrEnum
from http import HTTPStatus
from typing import Annotated, cast

import ldif
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
)
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from ldap import (
    INVALID_CREDENTIALS,  # type: ignore
    SCOPE_BASE,  # type: ignore
    SCOPE_ONELEVEL,  # type: ignore
    SCOPE_SUBTREE,  # type: ignore
)
from ldap.ldapobject import LDAPObject
from ldap.modlist import addModlist, modifyModlist
from ldap.schema import SubSchema
from ldap.schema.models import AttributeType, LDAPSyntax

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
from .ldap_helpers import (
    WITH_OPERATIONAL_ATTRS,
    LdapEntry,
    anonymous_user_search,
    empty,
    get_entry_by_dn,
    get_schema,
    ldap_connect,
    results,
    unique,
)
from .schema import Schema, frontend_schema

NO_CONTENT = Response(status_code=HTTPStatus.NO_CONTENT)

# Special fields
PHOTOS = ("jpegPhoto", "thumbnailPhoto")
PASSWORDS = ("userPassword",)

# Special syntaxes
OCTET_STRING = "1.3.6.1.4.1.1466.115.121.1.40"
INTEGER = "1.3.6.1.4.1.1466.115.121.1.27"

api = APIRouter(prefix="/api")


async def get_root_dse(connection: LDAPObject):
    "Auto-detect base DN and LDAP schema from root DSE"
    result = await unique(
        connection,
        connection.search(
            "",
            SCOPE_BASE,
            attrlist=WITH_OPERATIONAL_ATTRS,
        ),
    )
    if not settings.BASE_DN:
        base_dns = result.attr("namingContexts")
        assert len(base_dns) == 1, f"No unique base DN: {base_dns}"
        settings.BASE_DN = base_dns[0]

    if not settings.SCHEMA_DN:
        schema_dns = result.attr("subschemaSubentry")
        assert schema_dns, "Cannot determine LDAP schema"
        settings.SCHEMA_DN = schema_dns[0]


async def authenticated(
    credentials: Annotated[HTTPBasicCredentials, Depends(HTTPBasic())],
    connection: Annotated[LDAPObject, Depends(ldap_connect)],
) -> LDAPObject:
    "Authenticate against the directory"

    if not settings.BASE_DN or not settings.SCHEMA_DN:
        await get_root_dse(connection)

    # Hard-wired credentials
    dn = settings.GET_BIND_DN()
    password = settings.GET_BIND_PASSWORD()

    # Search for basic auth user
    if not dn:
        password = credentials.password
        dn = settings.GET_BIND_PATTERN(
            credentials.username
        ) or await anonymous_user_search(connection, credentials.username)

    if dn:  # Log in
        await empty(connection, connection.simple_bind(dn, password))
        return connection

    raise INVALID_CREDENTIALS([{"desc": f"Invalid credentials for DN: {dn}"}])


AuthenticatedConnection = Annotated[LDAPObject, Depends(authenticated)]


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
            settings.BASE_DN, SCOPE_BASE, attrlist=WITH_OPERATIONAL_ATTRS
        ),
    )
    return [_tree_item(result, settings.BASE_DN)]


@api.get("/tree/{basedn:path}", tags=[Tag.NAVIGATION], operation_id="get_tree")
async def get_tree(basedn: str, connection: AuthenticatedConnection) -> list[TreeItem]:
    "List directory entries below a DN"

    return [
        _tree_item(entry, basedn)
        async for entry in results(
            connection,
            connection.search(basedn, SCOPE_ONELEVEL, attrlist=WITH_OPERATIONAL_ATTRS),
        )
    ]


def _tree_item(entry: LdapEntry, base_dn: str) -> TreeItem:
    return TreeItem(
        dn=entry.dn,
        structuralObjectClass=entry.attr("structuralObjectClass")[0],
        hasSubordinates=entry.hasSubordinates,
        level=_level(entry.dn) - _level(base_dn),
    )


def _level(dn: str) -> int:
    return len(dn.split(","))


@api.get("/entry/{dn:path}", tags=[Tag.EDITING], operation_id="get_entry")
async def get_entry(dn: str, connection: AuthenticatedConnection) -> Entry:
    "Retrieve a directory entry by DN"
    return _entry(
        await get_entry_by_dn(connection, dn),
        await get_schema(connection),
    )


def _entry(entry: LdapEntry, schema: SubSchema) -> Entry:
    "Decode an LDAP entry for transmission"

    binary = sorted(
        set(attr for attr in entry.attrs if _is_binary(entry, attr, schema))
    )
    return Entry(
        attrs={
            k: ["*****"]  # 23 suppress userPassword
            if k == "userPassword"
            else [base64.b64encode(val).decode() for val in entry.attrs[k]]
            if k in binary
            else entry.attr(k)
            for k in sorted(entry.attrs)
        },
        dn=entry.dn,
        binary=binary,
        autoFilled=[],
        changed=[],
    )


def _is_binary(entry: LdapEntry, attr: str, schema: SubSchema) -> bool:
    "Guess whether an attribute has binary content"

    # Octet strings are not used consistently in schemata.
    # Try to decode as text and treat as binary on failure
    attr_type = schema.get_obj(AttributeType, attr)
    if not attr_type.syntax or attr_type.syntax == OCTET_STRING:  # type: ignore
        try:
            return any(not val.isprintable() for val in entry.attr(attr))
        except UnicodeDecodeError:
            return True

    # Check human-readable flag
    return schema.get_obj(LDAPSyntax, attr_type.syntax).not_human_readable  # type: ignore


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
            async for entry in results(
                connection,
                connection.search(dn, SCOPE_SUBTREE),
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
    schema = await get_schema(connection)

    expected = {
        attr: _nonempty_byte_strings(attributes, attr)
        for attr in attributes
        if attr not in PASSWORDS
        and (
            attr not in entry.attrs
            or not _is_binary(
                entry, attr, schema
            )  # FIXME Handle binary attributes properly
        )
    }

    actual = {attr: v for attr, v in entry.attrs.items() if attr in expected}
    modlist = modifyModlist(actual, expected)
    if modlist:  # Apply changes and send changed keys back
        await empty(connection, connection.modify(dn, modlist))
    return list(sorted(set(m[1] for m in modlist)))


def _nonempty_byte_strings(attributes: Attributes, attr: str) -> list[bytes]:
    return [s.encode() for s in filter(None, attributes[attr])]


@api.put("/entry/{dn:path}", tags=[Tag.EDITING], operation_id="put_entry")
async def put_entry(
    dn: str, attributes: Attributes, connection: AuthenticatedConnection
) -> AttributeNames:
    modlist = addModlist(
        {
            attr: _nonempty_byte_strings(attributes, attr)
            for attr in attributes
            if attr not in PHOTOS
        }
    )
    if modlist:
        await empty(connection, connection.add(dn, modlist))
    return ["dn"]  # Dummy


@api.post(
    "/rename/{dn:path}",
    status_code=HTTPStatus.NO_CONTENT,
    tags=[Tag.EDITING],
    operation_id="post_rename_entry",
)
async def rename_entry(
    dn: str, rdn: Annotated[str, Body()], connection: AuthenticatedConnection
) -> None:
    "Rename an entry"
    await empty(connection, connection.rename(dn, rdn, delold=0))


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

    if attr not in entry.attrs or len(entry.attrs[attr]) <= index:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"Attribute {attr} not found for DN {dn}"
        )

    return Response(
        entry.attrs[attr][index],
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
    entry = await get_entry_by_dn(connection, dn)
    data = await blob.read(cast(int, blob.size))
    if attr in entry.attrs:
        await empty(
            connection,
            connection.modify(
                dn, [(1, attr, None), (0, attr, entry.attrs[attr] + [data])]
            ),
        )
    else:
        await empty(connection, connection.modify(dn, [(0, attr, [data])]))


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
    if attr not in entry.attrs or len(entry.attrs[attr]) <= index:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, f"Attribute {attr} not found for DN {dn}"
        )
    await empty(connection, connection.modify(dn, [(1, attr, None)]))
    data = entry.attrs[attr][:index] + entry.attrs[attr][index + 1 :]
    if data:
        await empty(connection, connection.modify(dn, [(0, attr, data)]))


@api.post(
    "/check-password/{dn:path}", tags=[Tag.EDITING], operation_id="post_check_password"
)
async def check_password(
    dn: str, check: Annotated[str, Body()], connection: AuthenticatedConnection
) -> bool:
    "Verify a password"

    try:
        connection.simple_bind_s(dn, check)
        return True
    except INVALID_CREDENTIALS:
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
        await empty(
            connection,
            connection.passwd(dn, args.old or None, args.new1),
        )
    else:
        await empty(connection, connection.modify(dn, [(1, "userPassword", None)]))


@api.get(
    "/ldif/{dn:path}",
    include_in_schema=False,  # Used as a link target, no API call
)
async def export_ldif(dn: str, connection: AuthenticatedConnection) -> Response:
    "Dump an entry as LDIF"

    out = io.StringIO()
    writer = ldif.LDIFWriter(out)

    async for entry in results(connection, connection.search(dn, SCOPE_SUBTREE)):
        writer.unparse(dn, entry.attrs)

    file_name = dn.split(",")[0].split("=")[1]
    return PlainTextResponse(
        out.getvalue(),
        headers={"Content-Disposition": f'attachment; filename="{file_name}.ldif"'},
    )


class LDIFReader(ldif.LDIFParser):
    def __init__(self, input: bytes, con: LDAPObject):
        ldif.LDIFParser.__init__(self, io.BytesIO(input))
        self.count = 0
        self.con = con

    def handle(self, dn: str, entry: Attributes):
        self.con.add_s(dn, addModlist(entry))
        self.count += 1


@api.post(
    "/ldif",
    tags=[Tag.EDITING],
    operation_id="post_ldif",
    status_code=HTTPStatus.NO_CONTENT,
)
async def upload_ldif(
    ldif: Annotated[str, Body()], connection: AuthenticatedConnection
) -> None:
    "Import LDIF"

    reader = LDIFReader(ldif.encode(), connection)
    try:
        reader.parse()
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
        query = "(|%s)" % "".join(p % query for p in settings.SEARCH_PATTERNS)

    # Collect results
    res = []
    async for entry in results(
        connection, connection.search(settings.BASE_DN, SCOPE_SUBTREE, query)
    ):
        res.append(
            SearchResult(
                dn=entry.dn,
                name=entry.attr("cn")[0] if "cn" in entry.attrs else entry.dn,
            )
        )
        if len(res) >= settings.SEARCH_MAX:
            break
    return res


@api.get("/whoami", tags=[Tag.MISC], operation_id="get_who_am_i")
async def whoami(connection: AuthenticatedConnection) -> str:
    "DN of the current user"
    return connection.whoami_s().replace("dn:", "")


@api.get("/subtree/{root_dn:path}", tags=[Tag.MISC], operation_id="get_subtree")
async def list_subtree(
    root_dn: str, connection: AuthenticatedConnection
) -> list[TreeItem]:
    "List the subtree below a DN"

    return sorted(
        [
            _tree_item(entry, root_dn)
            async for entry in results(
                connection,
                connection.search(
                    root_dn, SCOPE_SUBTREE, attrlist=WITH_OPERATIONAL_ATTRS
                ),
            )
            if root_dn != entry.dn
        ],
        key=lambda item: tuple(reversed(item.dn.lower().split(","))),
    )


@api.get("/range/{attribute}", tags=[Tag.MISC], operation_id="get_range")
async def attribute_range(attribute: str, connection: AuthenticatedConnection) -> Range:
    "List all values for a numeric attribute of an objectClass like uidNumber or gidNumber"

    schema = await get_schema(connection)
    obj = schema.get_obj(AttributeType, attribute)

    values = set(
        [
            int(entry.attrs[attribute][0])
            async for entry in results(
                connection,
                connection.search(
                    settings.BASE_DN,
                    SCOPE_SUBTREE,
                    f"({attribute}=*)",
                    attrlist=(attribute,),
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
    return frontend_schema(await get_schema(connection))
