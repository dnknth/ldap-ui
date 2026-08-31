"""
JSON representation of the LDAP directory schema.

It is used by the frontend for consistency checks, and
to determine how individual attributes should be presented
to the user.
"""

import re
from enum import StrEnum
from typing import Any, Self

from ldap3.core.exceptions import LDAPInvalidDnError
from ldap3.protocol.rfc4512 import (
    AttributeTypeInfo,
    BaseObjectInfo,
    LdapSyntaxInfo,
    ObjectClassInfo,
    SchemaInfo,
)
from ldap3.utils.ciDict import CaseInsensitiveDict
from ldap3.utils.dn import parse_dn
from pydantic import BaseModel, Field, computed_field

# Special syntaxes
OCTET_STRING = "1.3.6.1.4.1.1466.115.121.1.40"
INTEGER = "1.3.6.1.4.1.1466.115.121.1.27"

#
# DN comparison
#

_CHAR_ESCAPE = re.compile(r"\\([,+#;<=>\"\\ ])")
_HEX_ESCAPE = re.compile(r"\\([0-9A-Fa-f]{2})")


def _unescape_rdn(value: str) -> str:
    "Decode RFC 4514 escapes (\\X and \\XX) in an RDN component to the literal character"
    value = _CHAR_ESCAPE.sub(r"\1", value)
    return _HEX_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), value)


def canonical_attribute_type(attr: str, schema: SchemaInfo | None) -> str:
    """
    Resolve an attribute type name to a canonical form via the schema's OID.

    Raises LDAPInvalidDnError when a schema is available and the attribute
    type is not defined in it. Only falls back to the lowercased name when no
    schema is available at all.
    """
    if schema is not None and schema.attribute_types is not None:
        try:
            return schema.attribute_types[attr].oid
        except (KeyError, AttributeError) as exc:
            raise LDAPInvalidDnError(
                f"Unknown attribute type: {attr}"
            ) from exc
    return _unescape_rdn(attr).lower()


def normalize_dn(dn: str, schema: SchemaInfo | None = None) -> list[tuple[str, str]]:
    """
    Structural form of a DN for equality comparison.

    ldap3 ships no DN matching function (its dn helpers only parse/serialize),
    so the DN is decomposed with its RFC 4514 parser and compared component-wise:

    - attribute types are resolved through the directory schema when available,
      so aliases (gn == givenName) and case variants (RFC 4512) match; an
      attribute type not defined in the schema is an invalid DN and raises
      LDAPInvalidDnError;
    - separator (`,`/`+`) ordering is ignored (RFC 4514);
    - `\\X` and `\\XX` escapes are decoded so equivalent encodings compare equal.

    Values are compared case-insensitively: the common DN attribute syntaxes
    (Directory String, IA5 String) match case-insensitively, and resolving the
    exact matching rule per attribute syntax would require the matching rules
    in the schema. This biases toward the components being "the same", which
    keeps is_self fail-closed: a self DN is then treated as self, and the old
    password is required instead of being silently omitted.
    """
    return [
        (canonical_attribute_type(attr, schema), _unescape_rdn(value).lower())
        for attr, value, _ in parse_dn(dn)
    ]


class _Element(BaseModel):
    "Common fields of attributes and object classes"

    oid: str
    names: list[str] = Field(min_length=1)
    desc: str | None = None
    obsolete: bool
    sup: list[str]  # TODO check

    @computed_field
    def name(self) -> str:
        name = self.names[0]
        return name[:1].lower() + name[1:]

    @staticmethod
    def args(info: BaseObjectInfo) -> dict[str, Any]:
        return {
            "oid": info.oid,
            "names": info.name,
            "desc": info.description,
            "obsolete": info.obsolete,
            "sup": sorted(info.superior or []),
        }


class Attribute(_Element):
    class Usage(StrEnum):
        DIRECTORY_OPERATION = "directoryOperation"
        DISTRIBUTED_OPERATION = "distributedOperation"
        DSA_OPERATION = "dSAOperation"
        USER_APPLICATIONS = "userApplications"

    single_value: bool
    no_user_mod: bool
    usage: Usage = Usage.USER_APPLICATIONS
    equality: str | None = None
    syntax: str | None = None
    substr: str | None = None
    ordering: str | None = None

    @classmethod
    def of(cls, attr: AttributeTypeInfo) -> Self:
        return cls(
            single_value=attr.single_value,
            no_user_mod=attr.no_user_modification,
            usage=Attribute.Usage[attr.usage or "USER_APPLICATIONS"],
            # FIXME avoid null values below
            equality=attr.equality[0] if attr.equality else None,
            syntax=attr.syntax,
            substr=attr.substr[0] if hasattr(attr, "substr") else None,
            ordering=attr.ordering[0] if attr.ordering else None,
            **_Element.args(attr),
        )


class ObjectClass(_Element):
    may: list[str]
    must: list[str]
    kind: str

    @classmethod
    def of(cls, oc: ObjectClassInfo) -> Self:
        return cls(
            may=sorted(oc.may_contain),
            must=sorted(oc.must_contain),
            kind=oc.kind.lower(),
            **_Element.args(oc),
        )


class Syntax(BaseModel):
    oid: str
    desc: str
    extensions: list | None = Field(default=None, exclude=True)

    @computed_field
    def not_human_readable(self) -> bool:
        extensions = CaseInsensitiveDict(self.extensions or [])
        return self.oid == OCTET_STRING or (  # FIXME why needs this hard-coding?
            "TRUE" in extensions.get("X-NOT-HUMAN-READABLE", [])
        )

    @classmethod
    def of(cls, syntax: LdapSyntaxInfo) -> Self:
        return cls(
            oid=syntax.oid,
            desc=syntax.description,
            extensions=syntax.extensions,
        )


class Schema(BaseModel):
    attributes: dict[str, Attribute]
    objectClasses: dict[str, ObjectClass]
    syntaxes: dict[str, Syntax]

    @classmethod
    def of(cls, info: SchemaInfo) -> Self:
        "Dump an LDAP schema"
        return cls(
            attributes={
                attr.name[0].lower(): Attribute.of(attr)
                for attr in sorted(
                    info.attribute_types.values(), key=lambda x: x.name[0].lower()
                )
            },
            objectClasses={
                oc.name[0].lower(): ObjectClass.of(oc)
                for oc in sorted(
                    info.object_classes.values(), key=lambda x: x.name[0].lower()
                )
            },
            syntaxes={
                syntax.oid: Syntax.of(syntax) for syntax in info.ldap_syntaxes.values()
            },
        )
