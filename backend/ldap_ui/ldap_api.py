"""
ReST endpoints for LDAP access.

Directory operations are accessible to the frontend
through a hand-knit API, responses are usually converted to JSON.

Asynchronous LDAP operations are used as much as possible.
"""

import base64
import io
from typing import Any, Optional, Tuple, Union

import ldap
import ldif
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
)
from .schema import frontend_schema

__all__ = ("api",)


NO_CONTENT = Response(status_code=204)

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


@api.route("/tree/{basedn}")
async def tree(request: Request) -> JSONResponse:
    "List directory entries"

    basedn = request.path_params["basedn"]
    scope = ldap.SCOPE_ONELEVEL
    if basedn == "base":
        scope = ldap.SCOPE_BASE
        basedn = settings.BASE_DN

    return JSONResponse(await _tree(request, basedn, scope))


async def _tree(request: Request, basedn: str, scope: int) -> list[dict[str, Any]]:
    "Get all nodes below a DN (including the DN) within the given scope"

    connection = request.state.ldap
    return [
        {
            "dn": dn,
            "structuralObjectClass": attrs["structuralObjectClass"][0].decode(),
            "hasSubordinates": b"TRUE" == attrs["hasSubordinates"][0],
        }
        async for dn, attrs in result(
            connection,
            connection.search(basedn, scope, attrlist=WITH_OPERATIONAL_ATTRS),
        )
    ]


def _entry(schema: SubSchema, res: Tuple[str, Any]) -> dict[str, Any]:
    "Prepare an LDAP entry for transmission"

    dn, attrs = res
    ocs = set([oc.decode() for oc in attrs["objectClass"]])
    must_attrs, _may_attrs = schema.attribute_types(ocs)
    soc = [
        oc.names[0]
        for oc in map(lambda o: schema.get_obj(ObjectClass, o), ocs)
        if oc.kind == 0
    ]
    aux = set(
        schema.get_obj(ObjectClass, a).names[0]
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
        if not obj.syntax or obj.syntax == OCTET_STRING:
            try:
                for val in attrs[attr]:
                    assert val.decode().isprintable()
            except:  # noqa: E722
                binary.add(attr)

        else:  # Check human-readable flag in schema
            syntax = schema.get_obj(LDAPSyntax, obj.syntax)
            if syntax.not_human_readable:
                binary.add(attr)

    return {
        "attrs": {
            k: [
                base64.b64encode(val).decode() if k in binary else val.decode()
                for val in values
            ]
            for k, values in attrs.items()
        },
        "meta": {
            "dn": dn,
            "required": [schema.get_obj(AttributeType, a).names[0] for a in must_attrs],
            "aux": sorted(aux - ocs),
            "binary": sorted(binary),
            "hints": {},  # FIXME obsolete?
            "autoFilled": [],
        },
    }


Entry = TypeAdapter(dict[str, list[bytes]])


@api.route("/entry/{dn}", methods=("GET", "POST", "DELETE", "PUT"))
async def entry(request: Request) -> Response:
    "Edit directory entries"

    dn = request.path_params["dn"]
    connection = request.state.ldap

    if request.method == "GET":
        return JSONResponse(
            _entry(request.app.state.schema, await get_entry_by_dn(connection, dn))
        )

    if request.method == "DELETE":
        for entry in reversed(
            sorted(await _tree(request, dn, ldap.SCOPE_SUBTREE), key=_dn_order)
        ):
            await empty(connection, connection.delete(entry["dn"]))
        return NO_CONTENT

    # Copy JSON payload into a dictionary of non-empty byte strings
    json = Entry.validate_json(await request.body())
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


@api.route("/blob/{attr}/{index:int}/{dn}", methods=("GET", "DELETE", "PUT"))
async def blob(request: Request) -> Response:
    "Handle binary attributes"

    attr = request.path_params["attr"]
    index = request.path_params["index"]
    dn = request.path_params["dn"]
    connection = request.state.ldap

    _dn, attrs = await get_entry_by_dn(connection, dn)

    if request.method == "GET":
        if attr not in attrs or len(attrs[attr]) <= index:
            raise HTTPException(404, f"Attribute {attr} not found for DN {dn}")

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
                data = await blob.read(blob.size)
                if attr in attrs:
                    await empty(
                        connection,
                        connection.modify(
                            dn, [(1, attr, None), (0, attr, data + attrs[attr])]
                        ),
                    )
                else:
                    await empty(connection, connection.modify(dn, [(0, attr, data)]))
        return NO_CONTENT

    if request.method == "DELETE":
        if attr not in attrs or len(attrs[attr]) <= index:
            raise HTTPException(404, f"Attribute {attr} not found for DN {dn}")
        await empty(connection, connection.modify(dn, [(1, attr, None)]))
        data = attrs[attr][:index] + attrs[attr][index + 1 :]
        if data:
            await empty(connection, connection.modify(dn, [(0, attr, data)]))
        return NO_CONTENT


@api.route("/ldif/{dn}")
async def ldifDump(request: Request) -> PlainTextResponse:
    "Dump an entry as LDIF"

    dn = request.path_params["dn"]
    out = io.StringIO()
    writer = ldif.LDIFWriter(out)
    connection = request.state.ldap

    async for dn, attrs in result(
        connection, connection.search(dn, ldap.SCOPE_SUBTREE)
    ):
        writer.unparse(dn, attrs)

    file_name = dn.split(",")[0].split("=")[1]
    return PlainTextResponse(
        out.getvalue(),
        headers={"Content-Disposition": f'attachment; filename="{file_name}.ldif"'},
    )


class LDIFReader(ldif.LDIFParser):
    def __init__(self, input: str, con: LDAPObject):
        ldif.LDIFParser.__init__(self, io.BytesIO(input))
        self.count = 0
        self.con = con

    def handle(self, dn: str, entry: dict[str, Any]):
        self.con.add_s(dn, addModlist(entry))
        self.count += 1


@api.route("/ldif", methods=("POST",))
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


@api.route("/rename/{dn}", methods=("POST",))
async def rename(request: Request) -> JSONResponse:
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


@api.route("/entry/password/{dn}", methods=("POST",))
async def passwd(request: Request) -> JSONResponse:
    "Update passwords"

    dn = request.path_params["dn"]
    args = PasswordRequest.validate_json(await request.body())

    if type(args) is CheckPasswordRequest:
        with ldap_connect() as con:
            try:
                con.simple_bind_s(dn, args.check)
                return JSONResponse(True)
            except ldap.INVALID_CREDENTIALS:
                return JSONResponse(False)

    else:
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
            return JSONResponse(None)


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
        connection, connection.search(settings.BASE_DN, ldap.SCOPE_SUBTREE, query)
    ):
        res.append({"dn": dn, "name": _cn(attrs) or dn})
        if len(res) >= settings.SEARCH_MAX:
            break
    return JSONResponse(res)


def _dn_order(node):
    "Reverse DN parts for tree ordering"
    return tuple(reversed(node["dn"].lower().split(",")))


@api.route("/subtree/{dn}")
async def subtree(request: Request) -> JSONResponse:
    "List the subtree below a DN"

    dn = request.path_params["dn"]
    result, start = [], len(dn.split(","))
    for node in sorted(await _tree(request, dn, ldap.SCOPE_SUBTREE), key=_dn_order):
        if node["dn"] == dn:
            continue
        node["level"] = len(node["dn"].split(",")) - start
        result.append(node)
    return JSONResponse(result)


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
                    ldap.SCOPE_SUBTREE,
                    f"({attribute}=*)",
                    attrlist=(attribute,),
                ),
            )
            if obj and obj.syntax == INTEGER
        ]
    )

    if not values:
        raise HTTPException(404, f"No values found for attribute {attribute}")

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
    return JSONResponse(frontend_schema(request.app.state.schema))
