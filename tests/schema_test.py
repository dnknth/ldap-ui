import unittest
from json import load
from pathlib import Path

from ldap.schema import SubSchema
from ldap.schema.models import AttributeType, LDAPSyntax, ObjectClass
from ldap_ui.schema import frontend_schema
from ldif import LDIFRecordList

LDIF = Path(__file__).parent / "resources" / "bitnami-schema.ldif"
JSON = Path(__file__).parent / "resources" / "bitnami-schema.json"


class SchemaTest(unittest.TestCase):
    def test_schema(self):
        # Read schema LDIF
        with open(LDIF) as ldif:
            parser = LDIFRecordList(ldif)
            parser.parse()

        # Sanity checks
        self.assertEqual(1, len(parser.all_records))
        dn, attrs = parser.all_records[0]
        self.assertEqual("cn=subschema", dn.lower())

        # Count number of entries for each attribute
        count = {k: len(attrs[k]) for k in attrs.keys()}

        # Convert to LDAP SubSchema
        sub_schema = SubSchema(attrs, check_uniqueness=2)
        self.assertEqual(
            count["attributeTypes"], len(sub_schema.listall(AttributeType))
        )
        self.assertEqual(count["objectClasses"], len(sub_schema.listall(ObjectClass)))
        self.assertEqual(count["ldapSyntaxes"], len(sub_schema.listall(LDAPSyntax)))

        # Convert to JSON schema
        ui_schema = frontend_schema(sub_schema)
        self.assertEqual(count["attributeTypes"], len(ui_schema.attributes))
        self.assertEqual(count["objectClasses"], len(ui_schema.objectClasses))
        self.assertEqual(count["ldapSyntaxes"], len(ui_schema.syntaxes))

        self.assertIn("domain", ui_schema.objectClasses)
        self.assertIn("posixaccount", ui_schema.objectClasses)

        # Dump JSON
        with open(JSON, "r") as json:
            self.assertEqual(ui_schema.model_dump(), load(json))


if __name__ == "__main__":
    unittest.main()
