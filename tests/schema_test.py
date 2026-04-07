import json
import unittest
from pathlib import Path

from ldap3 import SchemaInfo
from ldap_ui.schema import Schema

SCHEMA_INFO = Path(__file__).parent / "resources" / "schema.json"
UI_SCHEMA = Path(__file__).parent / "resources" / "ui-schema.json"


class SchemaTest(unittest.TestCase):
    def test_schema(self):
        info_json = SCHEMA_INFO.read_text()
        info_dict = json.loads(info_json)

        # Count number of entries for each attribute
        count = {k: len(v) for k, v in info_dict["raw"].items()}

        # Read offline schema
        schema_info = SchemaInfo.from_json(info_json)
        self.assertTrue(schema_info.is_valid())

        self.assertEqual(count["attributeTypes"], len(schema_info.attribute_types))
        self.assertEqual(count["objectClasses"], len(schema_info.object_classes))
        self.assertEqual(count["ldapSyntaxes"], len(schema_info.ldap_syntaxes))

        # Convert to JSON schema
        ui_schema = Schema.of(schema_info)
        self.assertEqual(count["attributeTypes"], len(ui_schema.attributes))
        self.assertEqual(count["objectClasses"], len(ui_schema.objectClasses))
        self.assertEqual(count["ldapSyntaxes"], len(ui_schema.syntaxes))

        self.assertIn("domain", ui_schema.objectClasses)
        self.assertIn("posixaccount", ui_schema.objectClasses)

        # Dump JSON
        # UI_SCHEMA.write_text(json.dumps(ui_schema.model_dump(), indent=2, sort_keys=True))
        self.assertEqual(ui_schema.model_dump(), json.loads(UI_SCHEMA.read_text()))


if __name__ == "__main__":
    unittest.main()
