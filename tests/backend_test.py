import io
import unittest
from base64 import b64decode
from http import HTTPStatus

import httpx
from fastapi.testclient import TestClient
from ldap_ui.app import app
from ldap_ui.entities import Attributes
from ldap_ui.schema import Schema
from ldif import LDIFParser

AUTH = ("admin", "bedrock")

BASE_DN = "o=Flintstones"
ADMIN_DN = f"cn=admin,{BASE_DN}"
TEST_DN = f"cn=test,{BASE_DN}"
FRED_DN = f"cn=Fred Flintstone,ou=People,{BASE_DN}"

TEST_PERSON = {
    "cn": ["test"],
    "sn": ["test"],
    "objectClass": ["inetOrgPerson"],
    "userPassword": ["test"],
}

TEST_LDIF = b"""
dn: cn=test,o=Flintstones
cn: test
sn: test
objectClass: inetOrgPerson
userPassword: test
"""

JPEG = b64decode(
    b"/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
)


def parse_ldif(ldif: bytes) -> dict[str, Attributes]:
    return {k: dict(v) for k, v in LDIFParser(io.BytesIO(ldif)).parse()}


def normalize_entry(attributes: Attributes) -> Attributes:
    return {
        key: values
        for key, values in attributes.items()
        if key != "userPassword"  # jittery hashed value
    }


class ReadOnlyTest(unittest.TestCase):
    "Test directory read access"

    client = TestClient(app)

    def assertHTTPStatus(
        self, result: httpx.Response, status_code=HTTPStatus.OK
    ) -> None:
        self.assertEqual(result.status_code, status_code, result.text)

    def test_get_whoami(self):
        with self.client:
            result = self.client.get("/api/whoami", auth=AUTH)
            self.assertHTTPStatus(result)
            self.assertEqual(ADMIN_DN.lower(), result.json().lower())

    def test_get_schema(self):
        with self.client:
            result = self.client.get("/api/schema", auth=AUTH)
            self.assertHTTPStatus(result)

            schema = Schema.model_validate(result.json())
            self.assertTrue(schema.attributes)
            self.assertTrue(schema.objectClasses)
            self.assertTrue(schema.syntaxes)

    def test_get_tree_base(self):
        with self.client:
            result = self.client.get("/api/tree/base", auth=AUTH)
            self.assertHTTPStatus(result)
            entries = result.json()
            self.assertEqual(1, len(entries))
            self.assertEqual(BASE_DN, entries[0]["dn"])

    def test_get_tree_flintstones(self):
        with self.client:
            result = self.client.get("/api/tree/o=Flintstones", auth=AUTH)
            self.assertHTTPStatus(result)
            self.assertGreaterEqual(len(result.json()), 4)

    def test_search_fred(self):
        with self.client:
            result = self.client.get("/api/search/fred", auth=AUTH)
            self.assertHTTPStatus(result)
            self.assertEqual(1, len(result.json()))
            self.assertEqual(FRED_DN, result.json()[0]["dn"])

    def test_verify_password(self):
        with self.client:
            result = self.client.post(
                "/api/check-password/cn=admin,o=Flintstones",
                auth=AUTH,
                json=AUTH[1],
            )
            self.assertHTTPStatus(result)
            self.assertEqual(True, result.json())

    def test_get_subtree(self):
        with self.client:
            result = self.client.get("/api/subtree/ou=Pets,o=Flintstones", auth=AUTH)
            self.assertHTTPStatus(result)
            self.assertEqual(2, len(result.json()))

    def test_get_range(self):
        with self.client:
            result = self.client.get("/api/range/uidNumber", auth=AUTH)
            self.assertHTTPStatus(result)
            range = result.json()
            self.assertTrue("min" in range and "max" in range and "next" in range)

    def test_get_invalid_range(self):
        with self.client:
            result = self.client.get("/api/range/cn", auth=AUTH)
            self.assertHTTPStatus(result, HTTPStatus.NOT_FOUND)


class ModificationTest(unittest.TestCase):
    client = TestClient(app)

    def assertHTTPStatus(
        self, result: httpx.Response, status_code=HTTPStatus.OK
    ) -> None:
        self.assertEqual(result.status_code, status_code, result.text)

    def assertEntryEqual(self, dn: str, attrs: Attributes) -> None:
        result = self.client.get(f"/api/entry/{dn}", auth=AUTH)
        self.assertHTTPStatus(result)
        self.assertDictEqual(
            normalize_entry(attrs),
            normalize_entry(result.json()["attrs"]),
        )

    def test_010_put_entry(self):
        with self.client:
            result = self.client.put(
                f"/api/entry/{TEST_DN}",
                auth=AUTH,
                json=TEST_PERSON,
            )
            if not result.status_code == HTTPStatus.CONFLICT:  # stale previous test run
                self.assertHTTPStatus(result)
                self.assertEqual(["dn"], result.json())
            self.assertEntryEqual(TEST_DN, TEST_PERSON)

    def test_020_put_entry_again(self):
        with self.client:
            result = self.client.put(
                f"/api/entry/{TEST_DN}",
                auth=AUTH,
                json={
                    "cn": ["test"],
                    "sn": ["bar"],
                    "objectClass": ["inetOrgPerson"],
                },
            )
            self.assertHTTPStatus(result, HTTPStatus.CONFLICT)
            self.assertEqual({"detail": ["Entry Already Exists"]}, result.json())

    def test_030_modify_entry(self):
        with self.client:
            attrs = {
                "cn": ["test"],
                "sn": ["baz"],
                "objectClass": ["inetOrgPerson"],
            }
            result = self.client.post(
                f"/api/entry/{TEST_DN}",
                auth=AUTH,
                json=attrs,
            )
            self.assertHTTPStatus(result)
            self.assertEqual(result.json(), ["sn"])
            self.assertEntryEqual(TEST_DN, attrs)

    def test_040_put_image_to_entry(self):
        with self.client:
            result = self.client.put(
                f"/api/blob/jpegPhoto/0/{TEST_DN}",
                auth=AUTH,
                files={"blob": JPEG},
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)

    def test_050_get_uploaded_image(self):
        with self.client:
            result = self.client.get(
                f"/api/blob/jpegPhoto/0/{TEST_DN}",
                auth=AUTH,
            )
            self.assertHTTPStatus(result)
            self.assertEqual(JPEG, result.content)
            self.assertEqual(
                'attachment; filename="jpegPhoto-0.bin"',
                result.headers["Content-Disposition"],
            )

    def test_060_delete_image_from_entry(self):
        with self.client:
            result = self.client.delete(
                f"/api/blob/jpegPhoto/0/{TEST_DN}",
                auth=AUTH,
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)

    def test_070_delete_image_from_entry_again(self):
        with self.client:
            result = self.client.delete(f"/api/blob/jpegPhoto/0/{TEST_DN}", auth=AUTH)
            self.assertHTTPStatus(result, HTTPStatus.NOT_FOUND)

    def test_080_change_password(self):
        with self.client:
            result = self.client.post(
                f"/api/change-password/{TEST_DN}",
                auth=AUTH,
                json={"old": "test", "new1": "abc"},
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)

    def test_090_remove_password(self):
        with self.client:
            result = self.client.post(
                f"/api/change-password/{TEST_DN}",
                auth=AUTH,
                json={"old": "test", "new1": ""},
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)

    def test_100_rename_entry(self):
        with self.client:
            result = self.client.post(
                f"/api/rename/{TEST_DN}",
                auth=AUTH,
                json="sn=baz",
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)
            self.assertEntryEqual

    def test_110_delete_entry(self):
        with self.client:
            result = self.client.delete(
                f"/api/entry/sn=baz,{BASE_DN}",
                auth=AUTH,
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)

    def test_120_put_ldif(self):
        with self.client:
            result = self.client.put("/api/ldif", auth=AUTH, content=TEST_LDIF)
            if result.status_code != HTTPStatus.CONFLICT:  # stale previous test run?
                self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)
            self.assertEntryEqual(TEST_DN, TEST_PERSON)

    def test_130_compare_ldif(self):
        with self.client:
            result = self.client.get(f"/api/ldif/{TEST_DN}", auth=AUTH)
            self.assertHTTPStatus(result)
            self.assertDictEqual(
                {
                    dn: normalize_entry(attrs)
                    for dn, attrs in parse_ldif(TEST_LDIF).items()
                },
                {
                    dn: normalize_entry(attrs)
                    for dn, attrs in parse_ldif(result.content).items()
                },
            )

    def test_140_delete_ldif(self):
        with self.client:
            result = self.client.delete(
                f"/api/entry/{TEST_DN}",
                auth=AUTH,
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)


if __name__ == "__main__":
    unittest.main()
