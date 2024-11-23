import unittest
import warnings
from http import HTTPStatus

from ldap_ui.app import app
from starlette.testclient import TestClient

AUTH = ("admin", "bedrock")

ADMIN_DN = "cn=admin,dc=flintstones,dc=com"
FRED_DN = "cn=Fred Flintstone,ou=People,dc=flintstones,dc=com"

JPEG = (
    b"\xff\xd8\xff\xdb\x00C\x00\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01"
    b"\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01"
    b"\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01"
    b"\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\xff\xc2\x00\x0b\x08\x00\x01"
    b"\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\xff\xda\x00\x08\x01\x01\x00"
    b"\x00\x00\x01?\xff\xd9"
)

LDIF = """
dn: cn=test,dc=flintstones,dc=com
cn: test
objectClass: organizationalRole
objectClass: simpleSecurityObject
userPassword: test
"""


class BackendSmokeTest(unittest.TestCase):
    "Trigger all HTTP methods on every endpoint"

    def setUp(self):
        "Ignore ResourceWarning from test setup"
        warnings.simplefilter("ignore", ResourceWarning)

    def test_000_get_whoami(self):
        with TestClient(app) as client:
            result = client.get("/api/whoami", auth=AUTH)
            self.assertEqual(result.status_code, HTTPStatus.OK.value)
            self.assertEqual(result.json(), ADMIN_DN)

    def test_005_get_schema(self):
        with TestClient(app) as client:
            result = client.get("/api/schema", auth=AUTH)
            self.assertEqual(result.status_code, HTTPStatus.OK.value)

            schema = result.json()
            self.assertTrue(
                "attributes" in schema
                and "objectClasses" in schema
                and "syntaxes" in schema
            )

    def test_010_get_tree_base(self):
        with TestClient(app) as client:
            result = client.get("/api/tree/base", auth=AUTH)
            self.assertEqual(result.status_code, HTTPStatus.OK.value)
            self.assertEqual(len(result.json()), 1)

    def test_020_get_tree_flintstones(self):
        with TestClient(app) as client:
            result = client.get("/api/tree/dc=flintstones,dc=com", auth=AUTH)
            self.assertEqual(result.status_code, HTTPStatus.OK.value)
            self.assertGreaterEqual(len(result.json()), 4)

    def test_030_search_fred(self):
        with TestClient(app) as client:
            result = client.get("/api/search/fred", auth=AUTH)
            self.assertEqual(result.status_code, HTTPStatus.OK.value)
            self.assertEqual(len(result.json()), 1)
            self.assertEqual(result.json()[0]["dn"], FRED_DN)

    def test_040_put_entry(self):
        with TestClient(app) as client:
            result = client.put(
                "/api/entry/cn=foo,ou=People,dc=flintstones,dc=com",
                auth=AUTH,
                content='{"objectClass":["inetOrgPerson"],"cn":["foo"],"sn":["bar"]}',
            )
            self.assertEqual(result.status_code, HTTPStatus.OK.value)
            self.assertEqual(result.json(), {"changed": ["dn"]})

    def test_050_put_entry_again(self):
        with TestClient(app) as client:
            result = client.put(
                "/api/entry/cn=foo,ou=People,dc=flintstones,dc=com",
                auth=AUTH,
                content='{"objectClass":["inetOrgPerson"],"cn":["foo"],"sn":["bar"]}',
            )
            self.assertEqual(result.status_code, HTTPStatus.INTERNAL_SERVER_ERROR.value)
            self.assertEqual(result.text, "Already exists")

    def test_060_modify_entry(self):
        with TestClient(app) as client:
            result = client.post(
                "/api/entry/cn=foo,ou=People,dc=flintstones,dc=com",
                auth=AUTH,
                content='{"objectClass":["inetOrgPerson"],"cn":["foo"],"sn":["baz"]}',
            )
            self.assertEqual(result.status_code, HTTPStatus.OK.value)
            self.assertEqual(result.json(), {"changed": ["sn"]})

    def test_070_put_image_to_entry(self):
        with TestClient(app) as client:
            result = client.put(
                "/api/blob/jpegPhoto/0/cn=foo,ou=People,dc=flintstones,dc=com",
                auth=AUTH,
                files={"blob": JPEG},
            )
            self.assertEqual(result.status_code, HTTPStatus.NO_CONTENT.value)

    def test_080_get_uploaded_image(self):
        with TestClient(app) as client:
            result = client.get(
                "/api/blob/jpegPhoto/0/cn=foo,ou=People,dc=flintstones,dc=com",
                auth=AUTH,
            )
            self.assertEqual(result.status_code, HTTPStatus.OK.value)
            self.assertEqual(result.content, JPEG)
            self.assertEqual(
                result.headers["Content-Disposition"],
                'attachment; filename="jpegPhoto-0.bin"',
            )

    def test_090_delete_image_from_entry(self):
        with TestClient(app) as client:
            result = client.delete(
                "/api/blob/jpegPhoto/0/cn=foo,ou=People,dc=flintstones,dc=com",
                auth=AUTH,
            )
            self.assertEqual(result.status_code, HTTPStatus.NO_CONTENT.value)

    def test_100_delete_image_from_entry_again(self):
        with TestClient(app) as client:
            result = client.delete(
                "/api/blob/jpegPhoto/0/cn=foo,ou=People,dc=flintstones,dc=com",
                auth=AUTH,
            )
            self.assertEqual(result.status_code, HTTPStatus.NOT_FOUND.value)

    def test_110_delete_entry(self):
        with TestClient(app) as client:
            result = client.delete(
                "/api/entry/cn=foo,ou=People,dc=flintstones,dc=com",
                auth=AUTH,
            )
            self.assertEqual(result.status_code, HTTPStatus.NO_CONTENT.value)

    def test_120_post_ldif(self):
        with TestClient(app) as client:
            result = client.post("/api/ldif", auth=AUTH, content=LDIF)
            self.assertEqual(result.status_code, HTTPStatus.NO_CONTENT.value)

    def test_130_compare_ldif(self):
        with TestClient(app) as client:
            result = client.get("/api/ldif/cn=test,dc=flintstones,dc=com", auth=AUTH)
            self.assertEqual(result.status_code, HTTPStatus.OK.value)
            self.assertEqual(result.content.decode().strip(), LDIF.strip())

    def test_140_change_password(self):
        with TestClient(app) as client:
            result = client.post(
                "/api/entry/password/cn=test,dc=flintstones,dc=com",
                auth=AUTH,
                content='{"old":"test","new1":"abc"}',
            )
            self.assertEqual(result.status_code, HTTPStatus.OK.value)

    def test_150_verify_password(self):
        with TestClient(app) as client:
            result = client.post(
                "/api/entry/password/cn=test,dc=flintstones,dc=com",
                auth=AUTH,
                content='{"check":"abc"}',
            )
            self.assertEqual(result.status_code, HTTPStatus.OK.value)
            self.assertEqual(result.json(), True)

    def test_160_rename_ldif(self):
        with TestClient(app) as client:
            result = client.post(
                "/api/rename/cn=test,dc=flintstones,dc=com",
                auth=AUTH,
                content='"objectClass=organizationalRole"',
            )
            self.assertEqual(result.status_code, HTTPStatus.NO_CONTENT.value)

    def test_170_delete_ldif(self):
        with TestClient(app) as client:
            result = client.delete(
                "/api/entry/objectClass=organizationalRole,dc=flintstones,dc=com",
                auth=AUTH,
            )
            self.assertEqual(result.status_code, HTTPStatus.NO_CONTENT.value)

    def test_180_verify_removed(self):
        with TestClient(app) as client:
            result = client.get(
                "/api/entry/objectClass=organizationalRole,dc=flintstones,dc=com",
                auth=AUTH,
            )
            self.assertEqual(result.status_code, HTTPStatus.NOT_FOUND.value)
            self.assertEqual(
                result.text,
                "DN not found: objectClass=organizationalRole,dc=flintstones,dc=com",
            )

    def test_190_get_subtree(self):
        with TestClient(app) as client:
            result = client.get("/api/subtree/ou=Pets,dc=flintstones,dc=com", auth=AUTH)
            self.assertEqual(result.status_code, HTTPStatus.OK.value)
            self.assertEqual(len(result.json()), 2)

    def test_200_get_range(self):
        with TestClient(app) as client:
            result = client.get("/api/range/uidNumber", auth=AUTH)
            self.assertEqual(result.status_code, HTTPStatus.OK.value)
            range = result.json()
            self.assertTrue("min" in range and "max" in range and "next" in range)

    def test_210_get_invalid_range(self):
        with TestClient(app) as client:
            result = client.get("/api/range/cn", auth=AUTH)
            self.assertEqual(result.status_code, HTTPStatus.NOT_FOUND.value)


if __name__ == "__main__":
    unittest.main()
