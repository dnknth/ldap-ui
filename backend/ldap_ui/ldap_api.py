"""
ReST endpoints for LDAP access.

Directory operations are accessible to the frontend
through a hand-knit ReST API, responses are usually converted to JSON.

Asynchronous LDAP operations are used as much as possible.
"""

import base64
import io
from http import HTTPStatus
from typing import Any, Optional, Tuple, Union, cast

import ldif
from ldap import (
    INVALID_CREDENTIALS,  # pyright: ignore[reportAttributeAccessIssue]
    SCOPE_BASE,  # pyright: ignore[reportAttributeAccessIssue]
    SCOPE_ONELEVEL,  # pyright: ignore[reportAttributeAccessIssue]
    SCOPE_SUBTREE,  # pyright: ignore[reportAttributeAccessIssue]
)
from ldap.ldapobject import LDAPObject
from ldap.modlist import addModlist, modifyModlist
from ldap.schema import SubSchema
from ldap.schema.models import AttributeType, LDAPSyntax, ObjectClass
from pydantic import BaseModel, Field, TypeAdapter
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Router

from . import settings
from .ldap_helpers import (
    WITH_OPERATIONAL_ATTRS,
    empty,
    get_entry_by_dn,
    ldap_connect,
    result,
    unique,
)
from .schema import ObjectClass as OC
from .schema import frontend_schema

__all__ = ("api",)


NO_CONTENT = Response(status_code=HTTPStatus.NO_CONTENT.value)

# Special fields
PHOTOS = ("jpegPhoto", "thumbnailPhoto")
PASSWORDS = ("userPassword",)

# Special syntaxes
OCTET_STRING = "1.3.6.1.4.1.1466.115.121.1.40"
INTEGER = "1.3.6.1.4.1.1466.115.121.1.27"

# Starlette router to decorate endpoints
api = Router()


@api.route("/whoami")
async def whoami(request: Request) -> JSONResponse:
    "DN of the current user"
    return JSONResponse(request.state.ldap.whoami_s().replace("dn:", ""))


class TreeItem(BaseModel):
    dn: str
    structuralObjectClass: str
    hasSubordinates: bool
    level: int


@api.route("/tree/{basedn}")
async def tree(request: Request) -> JSONResponse:
    "List directory entries"

    basedn = request.path_params["basedn"]
    base_level = len(basedn.split(","))
    scope = SCOPE_ONELEVEL
    if basedn == "base":
        scope = SCOPE_BASE
        basedn = settings.BASE_DN

    connection = request.state.ldap
    entries = result(
        connection, connection.search(basedn, scope, attrlist=WITH_OPERATIONAL_ATTRS)
    )
    return JSONResponse(
        [
            _tree_item(dn, attrs, base_level, request.app.state.schema).model_dump()
            async for dn, attrs in entries
        ]
    )


def _tree_item(
    dn: str, attrs: dict[str, Any], level: int, schema: SubSchema
) -> TreeItem:
    structuralObjectClass = next(
        iter(
            filter(
                lambda oc: oc.kind == OC.Kind.structural.value,  # pyright: ignore[reportOptionalMemberAccess]
                map(
                    lambda o: schema.get_obj(ObjectClass, o.decode()),
                    attrs["objectClass"],
                ),
            )
        )
    )

    return TreeItem(
        dn=dn,
        structuralObjectClass=structuralObjectClass.names[0],
        hasSubordinates=attrs["hasSubordinates"][0] == b"TRUE"
        if "hasSubordinates" in attrs
        else bool(attrs.get("numSubordinates")),
        level=len(dn.split(",")) - level,
    )


class Meta(BaseModel):
    dn: str
    required: list[str]
    aux: list[str]
    binary: list[str]
    autoFilled: list[str]


class Entry(BaseModel):
    attrs: dict[str, list[str]]
    meta: Meta


def _entry(schema: SubSchema, res: Tuple[str, Any]) -> Entry:
    "Prepare an LDAP entry for transmission"

    dn, attrs = res
    ocs = set([oc.decode() for oc in attrs["objectClass"]])
    must_attrs, _may_attrs = schema.attribute_types(ocs)
    soc = [
        oc.names[0]  # pyright: ignore[reportOptionalMemberAccess]
        for oc in map(lambda o: schema.get_obj(ObjectClass, o), ocs)
        if oc.kind == OC.Kind.structural.value  # pyright: ignore[reportOptionalMemberAccess]
    ]
    aux = set(
        schema.get_obj(ObjectClass, a).names[0]  # pyright: ignore[reportOptionalMemberAccess]
        for a in schema.get_applicable_aux_classes(soc[0])
    )

    # 23 suppress userPassword
    if "userPassword" in attrs:
        attrs["userPassword"] = [b"*****"]

    # Filter out binary attributes
    binary = set()
    for attr in attrs:
        obj = schema.get_obj(AttributeType, attr)

        # Octet strings are not used consistently.
        # Try to decode as text and treat as binary on failure
        if not obj.syntax or obj.syntax == OCTET_STRING:  # pyright: ignore[reportOptionalMemberAccess]
            try:
                for val in attrs[attr]:
                    assert val.decode().isprintable()
            except:  # noqa: E722
                binary.add(attr)

        else:  # Check human-readable flag in schema
            syntax = schema.get_obj(LDAPSyntax, obj.syntax)  # pyright: ignore[reportOptionalMemberAccess]
            if syntax.not_human_readable:  # pyright: ignore[reportOptionalMemberAccess]
                binary.add(attr)

    return Entry(
        attrs={
            k: [
                base64.b64encode(val).decode() if k in binary else val for val in values
            ]
            for k, values in attrs.items()
        },
        meta=Meta(
            dn=dn,
            required=[schema.get_obj(AttributeType, a).names[0] for a in must_attrs],  # pyright: ignore[reportOptionalMemberAccess]
            aux=sorted(aux - ocs),
            binary=sorted(binary),
            autoFilled=[],
        ),
    )


Attributes = TypeAdapter(dict[str, list[bytes]])


@api.route("/entry/{dn}", methods=["GET", "POST", "DELETE", "PUT"])
async def entry(request: Request) -> Response:
    "Edit directory entries"

    dn = request.path_params["dn"]
    connection = request.state.ldap

    if request.method == "GET":
        return JSONResponse(
            _entry(
                request.app.state.schema, await get_entry_by_dn(connection, dn)
            ).model_dump()
        )

    if request.method == "DELETE":
        for entry_dn in sorted(
            [
                dn
                async for dn, _attrs in result(
                    connection,
                    connection.search(dn, SCOPE_SUBTREE),
                )
            ],
            key=len,
            reverse=True,
        ):
            await empty(connection, connection.delete(entry_dn))
        return NO_CONTENT

    # Copy JSON payload into a dictionary of non-empty byte strings
    json = Attributes.validate_json(await request.body())
    req = {
        k: [s for s in filter(None, v)]
        for k, v in json.items()
        if k not in PHOTOS and (k not in PASSWORDS or request.method == "PUT")
    }

    if request.method == "POST":
        # Get previous values from directory
        res = await get_entry_by_dn(connection, dn)
        mods = {k: v for k, v in res[1].items() if k in req}
        modlist = modifyModlist(mods, req)

        if modlist:  # Apply changes and send changed keys back
            await empty(connection, connection.modify(dn, modlist))
        return JSONResponse({"changed": sorted(set(m[1] for m in modlist))})

    if request.method == "PUT":
        # Create new object
        modlist = addModlist(req)
        if modlist:
            await empty(connection, connection.add(dn, modlist))
        return JSONResponse({"changed": ["dn"]})  # Dummy

    raise HTTPException(HTTPStatus.METHOD_NOT_ALLOWED)


@api.route("/blob/{attr}/{index:int}/{dn}", methods=["GET", "DELETE", "PUT"])
async def blob(request: Request) -> Response:
    "Handle binary attributes"

    attr = request.path_params["attr"]
    index = request.path_params["index"]
    dn = request.path_params["dn"]
    connection = request.state.ldap

    _dn, attrs = await get_entry_by_dn(connection, dn)

    if request.method == "GET":
        if attr not in attrs or len(attrs[attr]) <= index:
            raise HTTPException(
                HTTPStatus.NOT_FOUND.value, f"Attribute {attr} not found for DN {dn}"
            )

        return Response(
            attrs[attr][index],
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{attr}-{index:d}.bin"'
            },
        )

    if request.method == "PUT":
        async with request.form() as form_data:
            blob = form_data["blob"]
            if type(blob) is UploadFile:
                data = await blob.read(cast(int, blob.size))
                if attr in attrs:
                    await empty(
                        connection,
                        connection.modify(
                            dn, [(1, attr, None), (0, attr, attrs[attr] + [data])]
                        ),
                    )
                else:
                    await empty(connection, connection.modify(dn, [(0, attr, [data])]))
        return NO_CONTENT

    if request.method == "DELETE":
        if attr not in attrs or len(attrs[attr]) <= index:
            raise HTTPException(
                HTTPStatus.NOT_FOUND.value, f"Attribute {attr} not found for DN {dn}"
            )
        await empty(connection, connection.modify(dn, [(1, attr, None)]))
        data = attrs[attr][:index] + attrs[attr][index + 1 :]
        if data:
            await empty(connection, connection.modify(dn, [(0, attr, data)]))
        return NO_CONTENT

    raise HTTPException(HTTPStatus.METHOD_NOT_ALLOWED)


@api.route("/ldif/{dn}")
async def ldifDump(request: Request) -> PlainTextResponse:
    "Dump an entry as LDIF"

    dn = request.path_params["dn"]
    out = io.StringIO()
    writer = ldif.LDIFWriter(out)
    connection = request.state.ldap

    async for dn, attrs in result(connection, connection.search(dn, SCOPE_SUBTREE)):
        writer.unparse(dn, attrs)

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

    def handle(self, dn: str, entry: dict[str, Any]):
        self.con.add_s(dn, addModlist(entry))
        self.count += 1


@api.route("/ldif", methods=["POST"])
async def ldifUpload(
    request: Request,
) -> Response:
    "Import LDIF"

    reader = LDIFReader(await request.body(), request.state.ldap)
    try:
        reader.parse()
        return NO_CONTENT
    except ValueError as e:
        return Response(e.args[0], status_code=422)


Rdn = TypeAdapter(str)


@api.route("/rename/{dn}", methods=["POST"])
async def rename(request: Request) -> Response:
    "Rename an entry"

    dn = request.path_params["dn"]
    rdn = Rdn.validate_json(await request.body())
    connection = request.state.ldap
    await empty(connection, connection.rename(dn, rdn, delold=0))
    return NO_CONTENT


class ChangePasswordRequest(BaseModel):
    old: str
    new1: str


class CheckPasswordRequest(BaseModel):
    check: str = Field(min_length=1)


PasswordRequest = TypeAdapter(Union[ChangePasswordRequest, CheckPasswordRequest])


@api.route("/entry/password/{dn}", methods=["POST"])
async def passwd(request: Request) -> Response:
    "Update passwords"

    dn = request.path_params["dn"]
    args = PasswordRequest.validate_json(await request.body())

    if type(args) is CheckPasswordRequest:
        with ldap_connect() as con:
            try:
                con.simple_bind_s(dn, args.check)
                return JSONResponse(True)
            except INVALID_CREDENTIALS:
                return JSONResponse(False)

    elif type(args) is ChangePasswordRequest:
        connection = request.state.ldap
        if args.new1:
            await empty(
                connection,
                connection.passwd(dn, args.old or None, args.new1),
            )
            _dn, attrs = await get_entry_by_dn(connection, dn)
            return JSONResponse(attrs["userPassword"][0].decode())

        else:
            await empty(connection, connection.modify(dn, [(1, "userPassword", None)]))
            return NO_CONTENT

    raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY)


def _cn(entry: dict) -> Optional[str]:
    "Try to extract a CN"
    if "cn" in entry and entry["cn"]:
        return entry["cn"][0].decode()


@api.route("/search/{query:path}")
async def search(request: Request) -> JSONResponse:
    "Search the directory"

    query = request.path_params["query"]
    if len(query) < settings.SEARCH_QUERY_MIN:
        return JSONResponse([])

    if "=" in query:  # Search specific attributes
        if "(" not in query:
            query = f"({query})"
    else:  # Build default query
        query = "(|%s)" % "".join(p % query for p in settings.SEARCH_PATTERNS)

    # Collect results
    res = []
    connection = request.state.ldap
    async for dn, attrs in result(
        connection, connection.search(settings.BASE_DN, SCOPE_SUBTREE, query)
    ):
        res.append({"dn": dn, "name": _cn(attrs) or dn})
        if len(res) >= settings.SEARCH_MAX:
            break
    return JSONResponse(res)


@api.route("/subtree/{dn}")
async def subtree(request: Request) -> JSONResponse:
    "List the subtree below a DN"

    root_dn = request.path_params["dn"]
    start = len(root_dn.split(","))
    connection = request.state.ldap
    return JSONResponse(
        sorted(
            [
                _tree_item(dn, attrs, start, request.app.state.schema).model_dump()
                async for dn, attrs in result(
                    connection,
                    connection.search(root_dn, SCOPE_SUBTREE),
                )
                if root_dn != dn
            ],
            key=lambda item: tuple(reversed(item["dn"].lower().split(","))),
        )
    )


@api.route("/range/{attribute}")
async def attribute_range(request: Request) -> JSONResponse:
    "List all values for a numeric attribute of an objectClass like uidNumber or gidNumber"

    attribute = request.path_params["attribute"]
    connection = request.state.ldap
    obj = request.app.state.schema.get_obj(AttributeType, attribute)

    values = set(
        [
            int(attrs[attribute][0])
            async for dn, attrs in result(
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
            HTTPStatus.NOT_FOUND.value, f"No values found for attribute {attribute}"
        )

    minimum, maximum = min(values), max(values)
    return JSONResponse(
        {
            "min": minimum,
            "max": maximum,
            "next": min(set(range(minimum, maximum + 2)) - values),
        }
    )


@api.route("/schema")
async def json_schema(request: Request) -> JSONResponse:
    "Dump the LDAP schema as JSON"
    if getattr(request.app.state, "schema", None) is None:
        connection = request.state.ldap
        # See: https://hub.packtpub.com/python-ldap-applications-part-4-ldap-schema/
        _dn, sub_schema = await unique(
            connection,
            connection.search(
                settings.SCHEMA_DN,
                SCOPE_BASE,
                attrlist=WITH_OPERATIONAL_ATTRS,
            ),
        )
        request.app.state.schema = SubSchema(sub_schema, check_uniqueness=2)

    schema = frontend_schema(request.app.state.schema)
    return JSONResponse(schema.model_dump())
