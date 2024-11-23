"""
JSON-serializable representation of the LDAP directory schema.

It is used by the frontend for consistency checks, and
to determine how individual attributes should be presented
to the user.
"""

from enum import IntEnum
from typing import Generator, Optional, TypeVar, Union, cast

from ldap.schema import SubSchema
from ldap.schema.models import AttributeType
from ldap.schema.models import LDAPSyntax as LDAPSyntaxType
from ldap.schema.models import ObjectClass as ObjectClassType
from pydantic import BaseModel, Field, field_serializer

__all__ = ("frontend_schema", "Attribute", "ObjectClass")

T = TypeVar("T")


class Element(BaseModel):
    "Common attributes od schema elements"

    oid: str
    name: str
    names: list[str] = Field(min_length=1)
    desc: Optional[str]
    obsolete: bool
    sup: list[str]  # TODO check


def element(obj: Union[AttributeType, ObjectClassType]) -> Element:
    name = obj.names[0]
    return Element(
        oid=obj.oid,
        name=name[:1].lower() + name[1:],
        names=obj.names,
        desc=obj.desc,
        obsolete=bool(obj.obsolete),
        sup=sorted(obj.sup),
    )


class ObjectClass(Element):
    class Kind(IntEnum):
        structural = 0
        abstract = 1
        auxiliary = 2

    may: list[str]
    must: list[str]
    kind: Kind

    @field_serializer("kind")
    def serialize_kind(self, kind: Kind, _info) -> str:
        return kind.name


class Attribute(Element):
    class Usage(IntEnum):
        userApplications = 0
        directoryOperation = 1
        distributedOperation = 2
        dSAOperation = 3

    single_value: bool
    no_user_mod: bool
    usage: Usage
    equality: Optional[str]
    syntax: Optional[str]
    substr: Optional[str]
    ordering: Optional[str]

    @field_serializer("usage")
    def serialize_kind(self, usage: Usage, _info) -> str:
        return usage.name


class Syntax(BaseModel):
    oid: str
    desc: str
    not_human_readable: bool


def lowercase_dict(attr: str, items: list[T]) -> dict[str, T]:
    "Create an dictionary with lowercased keys extracted from a given attribute"
    return {getattr(obj, attr).lower(): obj for obj in items}


def extract_type(
    sub_schema: SubSchema, schema_class: type[T]
) -> Generator[T, None, None]:
    "Get non-obsolete objects from the schema for a type"

    for oid in sub_schema.listall(schema_class):
        obj = sub_schema.get_obj(schema_class, oid)
        if schema_class is LDAPSyntaxType or not obj.obsolete:  # pyright: ignore[reportOptionalMemberAccess]
            yield cast(T, obj)


class Schema(BaseModel):
    attributes: dict[str, Attribute]
    objectClasses: dict[str, ObjectClass]
    syntaxes: dict[str, Syntax]


# See: https://www.python-ldap.org/en/latest/reference/ldap-schema.html
def frontend_schema(sub_schema: SubSchema) -> Schema:
    "Dump an LDAP SubSchema"

    return Schema(
        attributes=lowercase_dict(
            "name",
            sorted(
                (
                    Attribute(
                        single_value=bool(attr.single_value),
                        no_user_mod=bool(attr.no_user_mod),
                        usage=Attribute.Usage(attr.usage),
                        # FIXME avoid null values below
                        equality=attr.equality,
                        syntax=attr.syntax,
                        substr=attr.substr,
                        ordering=attr.ordering,
                        **element(attr).model_dump(),
                    )
                    for attr in extract_type(sub_schema, AttributeType)
                ),
                key=lambda x: x.name,
            ),
        ),
        objectClasses=lowercase_dict(
            "name",
            sorted(
                (
                    ObjectClass(
                        may=sorted(oc.may),
                        must=sorted(oc.must),
                        kind=ObjectClass.Kind(oc.kind),
                        **element(oc).model_dump(),
                    )
                    for oc in extract_type(sub_schema, ObjectClassType)
                ),
                key=lambda x: x.name,
            ),
        ),
        syntaxes=lowercase_dict(
            "oid",
            [
                Syntax(
                    oid=stx.oid,
                    desc=stx.desc,
                    not_human_readable=bool(stx.not_human_readable),
                )
                for stx in extract_type(sub_schema, LDAPSyntaxType)
            ],
        ),
    )
