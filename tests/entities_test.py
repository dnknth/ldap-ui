import unittest
from unittest.mock import MagicMock

from ldap_ui.entities import Entry, TreeItem
from ldap_ui.ldap_helpers import ResponseEntry
from ldap_ui.schema import OCTET_STRING


def _make_attr_type(no_user_mod=False, syntax=None):
    m = MagicMock()
    m.no_user_modification = no_user_mod
    m.syntax = syntax
    return m


def _make_ldap_syntax(oid: str, description: str, extensions=None):
    """Create a mock LdapSyntaxInfo-like object for schema.ldap_syntaxes."""
    m = MagicMock()
    m.oid = oid
    m.description = description
    m.extensions = extensions or []
    return m


class EntryTest(unittest.TestCase):
    """Entry.of() — convert a raw LDAP ResponseEntry into an API Entry."""

    def _schema(self, attrs: dict, syntaxes: dict | None = None):
        schema = MagicMock()
        schema.attribute_types = {
            name: _make_attr_type(**cfg) for name, cfg in attrs.items()
        }
        schema.ldap_syntaxes = {oid: syn for oid, syn in (syntaxes or {}).items()}
        return schema

    def test_masks_password(self):
        """userPassword values must be replaced with '*****'."""
        schema = self._schema({"userPassword": {}, "cn": {}})

        entry = ResponseEntry(
            raw_dn=b"cn=Alice,dc=example,dc=com",
            dn="cn=Alice,dc=example,dc=com",
            attributes={"cn": "Alice"},
            raw_attributes={
                "userPassword": [b"secret123"],
                "cn": [b"Alice"],
            },
            type="searchResultEntry",
        )

        result = Entry.of(entry, schema)
        self.assertEqual(result.dn, "cn=Alice,dc=example,dc=com")
        self.assertEqual(result.attrs["userPassword"], ["*****"])
        self.assertEqual(result.attrs["cn"], ["Alice"])

    def test_filters_non_modifiable_attributes(self):
        """Attributes with no_user_mod=True must be excluded from attrs."""
        schema = self._schema({"entryUUID": {"no_user_mod": True}, "cn": {}})

        entry = ResponseEntry(
            raw_dn=b"cn=Bob,dc=example,dc=com",
            dn="cn=Bob,dc=example,dc=com",
            attributes={"cn": "Bob"},
            raw_attributes={
                "entryUUID": [b"abc-123"],
                "cn": [b"Bob"],
            },
            type="searchResultEntry",
        )

        result = Entry.of(entry, schema)
        self.assertNotIn("entryUUID", result.attrs)
        self.assertEqual(result.attrs["cn"], ["Bob"])

    def test_binary_attribute_base64_encoded(self):
        """Binary attributes (not_human_readable syntax) must be base64 encoded."""
        syn = _make_ldap_syntax(
            OCTET_STRING, "JPEG Photo", extensions=[("X-NOT-HUMAN-READABLE", ["TRUE"])]
        )
        schema = self._schema(
            {"jpegPhoto": {"syntax": OCTET_STRING}, "cn": {}},
            {OCTET_STRING: syn},
        )

        entry = ResponseEntry(
            raw_dn=b"cn=Charlie,dc=example,dc=com",
            dn="cn=Charlie,dc=example,dc=com",
            attributes={"cn": "Charlie"},
            raw_attributes={
                "jpegPhoto": [b"\xff\xd8\xff\xe0"],
                "cn": [b"Charlie"],
            },
            type="searchResultEntry",
        )

        import base64

        result = Entry.of(entry, schema)
        self.assertEqual(
            result.attrs["jpegPhoto"],
            [base64.b64encode(b"\xff\xd8\xff\xe0").decode()],
        )
        self.assertEqual(result.attrs["cn"], ["Charlie"])
        self.assertIn("jpegPhoto", result.binary)

    def test_unknown_attribute_raises(self):
        """If an attribute is not in the schema, is_binary raises ValueError.
        Note: This is a known limitation — Entry.of() does not gracefully skip
        attributes that are absent from the schema."""
        schema = self._schema({"cn": {}})

        entry = ResponseEntry(
            raw_dn=b"cn=test,dc=example,dc=com",
            dn="cn=test,dc=example,dc=com",
            attributes={"cn": "test"},
            raw_attributes={
                "unknownAttr": [b"value"],
                "cn": [b"test"],
            },
            type="searchResultEntry",
        )

        with self.assertRaises(ValueError):
            Entry.of(entry, schema)

    def test_binary_list_only_modifiable_binary_attrs(self):
        """binary field must list only binary attributes that are modifiable."""
        syn = _make_ldap_syntax(
            OCTET_STRING, "JPEG Photo", extensions=[("X-NOT-HUMAN-READABLE", ["TRUE"])]
        )
        schema = self._schema(
            {
                "jpegPhoto": {"syntax": OCTET_STRING},
                "userPassword": {},
                "cn": {},
            },
            {OCTET_STRING: syn},
        )

        entry = ResponseEntry(
            raw_dn=b"cn=Eve,dc=example,dc=com",
            dn="cn=Eve,dc=example,dc=com",
            attributes={"cn": "Eve"},
            raw_attributes={
                "jpegPhoto": [b"\xff\xd8"],
                "userPassword": [b"secret"],
                "cn": [b"Eve"],
            },
            type="searchResultEntry",
        )

        result = Entry.of(entry, schema)
        self.assertEqual(result.binary, ["jpegPhoto"])

    def test_printable_text_not_binary(self):
        """Printable text in octet-string syntax should NOT be treated as binary."""
        syn = _make_ldap_syntax(OCTET_STRING, "Directory String")
        schema = self._schema(
            {"description": {"syntax": OCTET_STRING}},
            {OCTET_STRING: syn},
        )

        entry = ResponseEntry(
            raw_dn=b"cn=test,dc=example,dc=com",
            dn="cn=test,dc=example,dc=com",
            attributes={"description": "Hello, World!"},
            raw_attributes={"description": [b"Hello, World!"]},
            type="searchResultEntry",
        )

        result = Entry.of(entry, schema)
        self.assertNotIn("description", result.binary)
        self.assertEqual(result.attrs["description"], ["Hello, World!"])

    def test_attrs_sorted(self):
        """Attribute keys must be sorted alphabetically."""
        schema = self._schema({"cn": {}, "sn": {}, "uid": {}})

        entry = ResponseEntry(
            raw_dn=b"uid=1001,dc=example,dc=com",
            dn="uid=1001,dc=example,dc=com",
            attributes={"uid": "1001"},
            raw_attributes={
                "uid": [b"1001"],
                "cn": [b"Frank"],
                "sn": [b"Smith"],
            },
            type="searchResultEntry",
        )

        result = Entry.of(entry, schema)
        keys = list(result.attrs.keys())
        self.assertEqual(keys, sorted(keys))

    def test_non_printable_octet_string_binary(self):
        """Non-printable content in octet-string syntax must be binary."""
        syn = _make_ldap_syntax(OCTET_STRING, "Directory String")
        schema = self._schema(
            {"userCertificate": {"syntax": OCTET_STRING}},
            {OCTET_STRING: syn},
        )

        entry = ResponseEntry(
            raw_dn=b"cn=Dave,dc=example,dc=com",
            dn="cn=Dave,dc=example,dc=com",
            attributes={"cn": "Dave"},
            raw_attributes={"userCertificate": [b"\x00\x01\x02\x03"]},
            type="searchResultEntry",
        )

        result = Entry.of(entry, schema)
        self.assertIn("userCertificate", result.binary)

    def test_unicode_decode_error_is_binary(self):
        """Content that fails UTF-8 decoding must be binary."""
        syn = _make_ldap_syntax(OCTET_STRING, "JPEG Photo")
        schema = self._schema(
            {"jpegPhoto": {"syntax": OCTET_STRING}},
            {OCTET_STRING: syn},
        )

        entry = ResponseEntry(
            raw_dn=b"cn=test,dc=example,dc=com",
            dn="cn=test,dc=example,dc=com",
            attributes={},
            raw_attributes={"jpegPhoto": [b"\xff\xfe\x00\x01"]},
            type="searchResultEntry",
        )

        result = Entry.of(entry, schema)
        self.assertIn("jpegPhoto", result.binary)

    def test_syntax_not_in_ldap_syntaxes_is_binary(self):
        """If syntax OID is not in ldap_syntaxes map, it's treated as binary."""
        schema = self._schema({"photo": {"syntax": "1.2.3.4"}}, {})

        entry = ResponseEntry(
            raw_dn=b"cn=test,dc=example,dc=com",
            dn="cn=test,dc=example,dc=com",
            attributes={},
            raw_attributes={"photo": [b"data"]},
            type="searchResultEntry",
        )

        result = Entry.of(entry, schema)
        self.assertIn("photo", result.binary)


class TreeItemTest(unittest.TestCase):
    """TreeItem.of() — convert a ResponseEntry into a TreeItem."""

    def test_basic_conversion(self):
        """TreeItem must extract dn, structuralObjectClass, and hasSubordinates."""
        entry = ResponseEntry(
            raw_dn=b"cn=alice,dc=example,dc=com",
            dn="cn=alice,dc=example,dc=com",
            attributes={"structuralObjectClass": "person"},
            raw_attributes={"hasSubordinates": [b"TRUE"]},
            type="searchResultEntry",
        )

        item = TreeItem.of(entry)
        self.assertEqual(item.dn, "cn=alice,dc=example,dc=com")
        self.assertEqual(item.structuralObjectClass, "person")
        self.assertTrue(item.hasSubordinates)

    def test_no_subordinates(self):
        """TreeItem with no subordinates."""
        entry = ResponseEntry(
            raw_dn=b"cn=bob,dc=example,dc=com",
            dn="cn=bob,dc=example,dc=com",
            attributes={"structuralObjectClass": "person"},
            raw_attributes={},
            type="searchResultEntry",
        )

        item = TreeItem.of(entry)
        self.assertFalse(item.hasSubordinates)


if __name__ == "__main__":
    unittest.main()
