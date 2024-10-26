"""
JSON-serializable representation of the LDAP directory schema.

It is used by the frontend for consistency checks, and
to determine how individual attributes should be presented
to the user.
"""

from typing import Any, Generator

from ldap.schema import SubSchema
from ldap.schema.models import AttributeType, LDAPSyntax, ObjectClass

__all__ = ("frontend_schema",)


# Object class constants
SCHEMA_OC_KIND = {
    0: "structural",
    1: "abstract",
    2: "auxiliary",
}

# Attribute usage constants
SCHEMA_ATTR_USAGE = {
    0: "userApplications",
    1: "directoryOperation",
    2: "distributedOperation",
    3: "dSAOperation",
}


def element(obj) -> dict:
    "Basic information about an schema element"
    name = obj.names[0]
    return {
        "oid": obj.oid,
        "name": name[:1].lower() + name[1:],
        "names": obj.names,
        "desc": obj.desc,
        "obsolete": bool(obj.obsolete),
        "sup": sorted(obj.sup),
    }


def object_class_dict(obj) -> dict:
    "Additional information about an object class"
    r = element(obj)
    r.update(
        {
            "may": sorted(obj.may),
            "must": sorted(obj.must),
            "kind": SCHEMA_OC_KIND[obj.kind],
        }
    )
    return r


def attribute_dict(obj) -> dict:
    "Additional information about an attribute"
    r = element(obj)
    r.update(
        {
            "single_value": bool(obj.single_value),
            "no_user_mod": bool(obj.no_user_mod),
            "usage": SCHEMA_ATTR_USAGE[obj.usage],
            # FIXME avoid null values below
            "equality": obj.equality,
            "syntax": obj.syntax,
            "substr": obj.substr,
            "ordering": obj.ordering,
        }
    )
    return r


def syntax_dict(obj) -> dict:
    "Information about an attribute syntax"
    return {
        "oid": obj.oid,
        "desc": obj.desc,
        "not_human_readable": bool(obj.not_human_readable),
    }


def lowercase_dict(attr: str, items) -> dict:
    "Create an dictionary with lowercased keys extracted from a given attribute"
    return {obj[attr].lower(): obj for obj in items}


def extract_type(
    sub_schema: SubSchema, schema_class: Any
) -> Generator[Any, None, None]:
    "Get non-obsolete objects from the schema for a type"

    for oid in sub_schema.listall(schema_class):
        obj = sub_schema.get_obj(schema_class, oid)
        if schema_class is LDAPSyntax or not obj.obsolete:
            yield obj


# See: https://www.python-ldap.org/en/latest/reference/ldap-schema.html
def frontend_schema(sub_schema: SubSchema) -> dict[Any]:
    "Dump an LDAP SubSchema"

    return dict(
        attributes=lowercase_dict(
            "name",
            sorted(
                map(
                    attribute_dict,
                    extract_type(sub_schema, AttributeType),
                ),
                key=lambda x: x["name"],
            ),
        ),
        objectClasses=lowercase_dict(
            "name",
            sorted(
                map(
                    object_class_dict,
                    extract_type(sub_schema, ObjectClass),
                ),
                key=lambda x: x["name"],
            ),
        ),
        syntaxes=lowercase_dict(
            "oid", map(syntax_dict, extract_type(sub_schema, LDAPSyntax))
        ),
    )
