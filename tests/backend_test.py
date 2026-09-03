import asyncio
import io
import unittest
from base64 import b64decode
from http import HTTPStatus
from typing import cast

import httpx2
from anyio import Lock
from fastapi.testclient import TestClient
from ldap3 import SchemaInfo
from ldap3.core.connection import Connection
from ldap3.core.exceptions import LDAPInvalidDnError
from ldap_ui import ldap_api, settings
from ldap_ui.app import app
from ldap_ui.entities import Attributes, Range
from ldap_ui.ldap_api import (
    bounded_range,
    is_hashed_password,
    sanitize_export_entries,
)
from ldap_ui.schema import Schema, normalize_dn
from ldif import LDIFParser
from testcontainers.core.config import testcontainers_config
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

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


def setUpModule():
    # Give Docker more time to spin up the LDAP container on slow hosts:
    # the default 120 s timeout is often too short.
    testcontainers_config.max_tries = 240

    # Skip testcontainers/ryuk: its port-mapping readiness race is flaky on
    # Docker Desktop (the port is not yet mapped even though the container is
    # running). The tests clean up their own container in tearDownClass.
    testcontainers_config.ryuk_disabled = True


class LdapMixin:
    LDAP = DockerContainer("dnknth/ldap-demo").with_exposed_ports(389)

    @classmethod
    def setUpClass(cls):
        cls.LDAP.waiting_for(LogMessageWaitStrategy("slapd starting")).start()
        settings.LDAP_URL = f"ldap://127.0.0.1:{cls.LDAP.get_exposed_port(389)}"

    @classmethod
    def tearDownClass(cls):
        cls.LDAP.stop()


def parse_ldif(ldif: bytes) -> dict[str, Attributes]:
    return {
        k: dict(v)
        for k, v in LDIFParser(io.BytesIO(ldif)).parse()
        if k is not None
    }


def normalize_entry(attributes: Attributes) -> Attributes:
    return {
        key: values
        for key, values in attributes.items()
        if key != "userPassword"  # jittery hashed value
    }


class NormalizeDnTest(unittest.TestCase):
    "Unit tests for normalize_dn (#2) — no directory required"

    def test_normalize_dn_case_insensitive(self):
        # Attribute types and values match case-insensitively (RFC 4512/4514).
        self.assertEqual(
            normalize_dn("CN=Admin,OU=People,DC=demo,DC=com"),
            normalize_dn("cn=admin,ou=people,dc=demo,dc=com"),
        )

    def test_normalize_dn_distinct(self):
        self.assertNotEqual(
            normalize_dn("cn=admin,dc=demo"),
            normalize_dn("cn=other,dc=demo"),
        )

    def test_normalize_dn_value_case(self):
        # Name values are matched case-insensitively (the common directory
        # equality behavior for cn/uid etc.).
        self.assertEqual(
            normalize_dn("Cn=Fred Flintstone,O=Flintstones"),
            normalize_dn("cn=FRED FLINTSTONE,o=flintstones"),
        )

    def test_normalize_dn_escape_equivalence(self):
        # RFC 4514: \\, and \\2C are equivalent encodings of the same value.
        self.assertEqual(
            normalize_dn("cn=John\\, Doe,ou=People,dc=demo"),
            normalize_dn("cn=John\\2C Doe,ou=People,dc=demo"),
        )

    def test_normalize_dn_attribute_alias(self):
        # Attribute aliases (gn == givenName) resolve through the schema's
        # CaseInsensitiveWithAliasDict (CASE_INSENSITIVE_SCHEMA_NAMES defaults
        # to True); without a schema they fall back to the lowercased name and
        # do not match.
        schema = SchemaInfo(
            "cn=schema",
            {
                "attributeTypes": [
                    "( 2.5.4.42 NAME ( 'givenName' 'gn' ) SUP name )"
                ]
            },
            {},
        )
        self.assertEqual(
            normalize_dn("gn=Fred", schema),
            normalize_dn("givenName=Fred", schema),
        )
        self.assertNotEqual(
            normalize_dn("gn=Fred"),
            normalize_dn("givenName=Fred"),
        )

    def test_normalize_dn_unknown_attribute_type(self):
        # An attribute type not defined in the schema is an invalid DN: it
        # raises LDAPInvalidDnError, which is_self catches and treats as
        # "not self" (fail-closed), requiring the old password.
        schema = SchemaInfo(
            "cn=schema",
            {
                "attributeTypes": [
                    "( 2.5.4.42 NAME ( 'givenName' 'gn' ) SUP name )"
                ]
            },
            {},
        )
        with self.assertRaises(LDAPInvalidDnError):
            normalize_dn("zzz=whatever", schema)


class RangeTest(unittest.TestCase):
    "Unit tests for bounded_range (#4) — no directory required"

    def test_bounded_range_printable(self):
        self.assertEqual(
            Range(min=3, max=5, next=6), bounded_range({3, 4, 5})
        )

    def test_bounded_range_fills_gap(self):
        self.assertEqual(
            Range(min=1, max=4, next=2), bounded_range({1, 3, 4})
        )

    def test_bounded_range_clamps_high_values(self):
        self.assertEqual(
            Range(min=1, max=60000, next=2),
            bounded_range({1, 60001}),
        )

    def test_bounded_range_all_values_outside_bound(self):
        # Every value exceeds the limit: the window collapses onto the upper
        # bound instead of allocating an unbounded range.
        self.assertEqual(
            Range(min=60000, max=60000, next=60000),
            bounded_range({100001, 200001}),
        )

    def test_bounded_range_negative_values(self):
        self.assertEqual(
            Range(min=0, max=3, next=0), bounded_range({-5, 1, 2, 3})
        )

    def test_bounded_range_all_negative_collapses_to_zero(self):
        self.assertEqual(
            Range(min=0, max=0, next=0), bounded_range({-100, -200})
        )

    def test_bounded_range_full_window(self):
        # A full window has no free value: 'next' falls back to the upper
        # bound and never exceeds RANGE_LIMIT.
        self.assertEqual(
            Range(min=0, max=2, next=2), bounded_range({0, 1, 2, 3, 4}, limit=2)
        )


class StripSensitiveTest(unittest.TestCase):
    "Unit tests for sanitize_export_entries / is_hashed_password (#1) — no directory"

    def entry(self, raw):
        return [{"type": "searchResEntry", "dn": "cn=x", "raw_attributes": raw}]

    def test_is_hashed_password(self):
        self.assertTrue(is_hashed_password(b"{SSHA}abc"))
        self.assertTrue(is_hashed_password(b"{SHA}def"))
        self.assertTrue(is_hashed_password("{MD5}ghi"))
        self.assertFalse(is_hashed_password(b"plaintext"))
        self.assertFalse(is_hashed_password(b"{CLEARTEXT}plain"))
        self.assertFalse(is_hashed_password(b"{PLAIN}plain"))

    def test_default_strips_sensitive(self):
        entries = self.entry(
            {
                "userPassword": [b"{SSHA}abc"],
                "userPKCS12": [b"pkcs"],
                "cn": [b"x"],
            }
        )
        result = sanitize_export_entries(entries, include_sensitive=False)
        self.assertEqual(result[0]["raw_attributes"], {"cn": [b"x"]})

    def test_sensitive_keeps_hashed_password(self):
        entries = self.entry(
            {"userPassword": [b"{SSHA}abc"], "cn": [b"x"]}
        )
        result = sanitize_export_entries(entries, include_sensitive=True)
        self.assertEqual(result[0]["raw_attributes"], {"userPassword": [b"{SSHA}abc"], "cn": [b"x"]})

    def test_sensitive_never_exports_plaintext(self):
        # Plaintext passwords are dropped even when explicitly requested (#1).
        entries = self.entry(
            {"userPassword": [b"secret"], "cn": [b"x"]}
        )
        result = sanitize_export_entries(entries, include_sensitive=True)
        self.assertEqual(result[0]["raw_attributes"], {"cn": [b"x"]})

    def test_sensitive_mixed_values(self):
        # Hashed values are kept, plaintext ones are dropped.
        entries = self.entry(
            {"userPassword": [b"{SSHA}abc", b"plain"], "cn": [b"x"]}
        )
        result = sanitize_export_entries(entries, include_sensitive=True)
        self.assertEqual(result[0]["raw_attributes"], {"userPassword": [b"{SSHA}abc"], "cn": [b"x"]})

    def test_cleartext_scheme_never_exported(self):
        entries = self.entry(
            {"userPassword": [b"{CLEARTEXT}plain"], "cn": [b"x"]}
        )
        result = sanitize_export_entries(entries, include_sensitive=True)
        self.assertEqual(result[0]["raw_attributes"], {"cn": [b"x"]})

    def test_base64_encoded_plaintext_never_exported(self):
        # Even when the value would be emitted as base64 in the LDIF (output
        # encoding relies on the raw value), a plaintext password is dropped.
        entries = self.entry(
            {"userPassword": [b"plain"], "cn": [b"x"]}
        )
        result = sanitize_export_entries(entries, include_sensitive=True)
        self.assertEqual(result[0]["raw_attributes"], {"cn": [b"x"]})

    def test_preserves_non_sensitive(self):
        entries = self.entry({"cn": [b"x"]})
        result = sanitize_export_entries(entries, include_sensitive=True)
        self.assertIs(result[0], entries[0])


class BindPatternTest(unittest.TestCase):
    "Unit tests for GET_BIND_PATTERN (#181) — no directory required"

    def _bind(self, pattern: str | None, username: str) -> str | None:
        "Apply the given BIND_PATTERN to username, isolating settings.config."
        orig = settings.config
        try:
            settings.config = (
                lambda k, default=None: pattern
                if k == "BIND_PATTERN"
                else orig(k, default=None)
            )
            return settings.GET_BIND_PATTERN(username)
        finally:
            settings.config = orig

    def test_unset_returns_none(self):
        self.assertIsNone(self._bind(None, "admin"))

    def test_malformed_pattern_raises(self):
        with self.assertRaises(ValueError):
            self._bind("no-placeholder", "admin")
        with self.assertRaises(ValueError):
            self._bind("cn=%s%s,o=x", "admin")

    def test_full_dn_unescaped(self):
        # Regression for #181: with BIND_PATTERN=%s, a full DN used to be
        # mangled by escape_rdn (the '=' and ',' got escaped), producing an
        # invalid bind DN. A parseable DN must be inserted unchanged.
        self.assertEqual(
            self._bind("%s", "cn=admin,o=Flintstones"),
            "cn=admin,o=Flintstones",
        )

    def test_partial_dn_unescaped(self):
        # BIND_PATTERN=%s,ou=... with a partial RDN (cn=admin) keeps its
        # structure; the suffix is appended.
        self.assertEqual(
            self._bind("%s,o=Flintstones", "cn=admin"),
            "cn=admin,o=Flintstones",
        )

    def test_bare_value_interpolated(self):
        self.assertEqual(
            self._bind("cn=%s,o=Flintstones", "admin"),
            "cn=admin,o=Flintstones",
        )

    def test_bare_value_escaped(self):
        # A bare value that is not a DN is escaped per RFC 4514 so it cannot
        # inject a stray attribute into the RDN.
        self.assertEqual(
            self._bind("cn=%s,o=Flintstones", "a+b"),
            "cn=a\\+b,o=Flintstones",
        )


class SchemaCacheTest(unittest.IsolatedAsyncioTestCase):
    "Ensure the schema is fetched only once under concurrency (#4)"

    def monkeypatch_schema(self):
        schema = SchemaInfo(
            "cn=schema",
            {"attributeTypes": ["( 2.5.4.42 NAME ( 'givenName' 'gn' ) SUP name )"]},
            {},
        )
        calls = [0]

        async def fake_get_schema(connection):
            calls[0] += 1
            await asyncio.sleep(0.01)  # widen the race window
            return schema

        original = (
            ldap_api.SCHEMA,
            ldap_api._SCHEMA_LOCK,
            ldap_api.get_schema,
        )
        ldap_api.SCHEMA = None
        ldap_api._SCHEMA_LOCK = Lock()
        ldap_api.get_schema = fake_get_schema
        return calls, original

    async def test_ensure_schema_fetches_once(self):
        calls, (schema, lock, get_schema) = self.monkeypatch_schema()
        connection = cast(Connection, object())  # unused by the fake
        try:
            results = await asyncio.gather(
                *[ldap_api.ensure_schema(connection) for _ in range(20)]
            )
        finally:
            ldap_api.SCHEMA, ldap_api._SCHEMA_LOCK, ldap_api.get_schema = (
                schema,
                lock,
                get_schema,
            )
        self.assertEqual(calls[0], 1)
        self.assertEqual(len(results), 20)


class ReadOnlyTest(LdapMixin, unittest.TestCase):
    "Test directory read access"

    client = TestClient(app)

    def assertHTTPStatus(
        self, result: httpx2.Response, status_code=HTTPStatus.OK
    ) -> None:
        self.assertEqual(result.status_code, status_code, result.text)

    def test_get_whoami(self):
        with self.client:
            result = self.client.get("/api/whoami", auth=AUTH)
            self.assertHTTPStatus(result)
            self.assertEqual(ADMIN_DN.lower(), result.json().lower())

    def test_get_whoami_anonymous(self):
        # whoami is a soft endpoint: without credentials it returns an empty
        # DN (200) rather than a 401 challenge, so the frontend probe never
        # triggers the browser's native Basic-auth popup.
        with self.client:
            result = self.client.get("/api/whoami")
            self.assertHTTPStatus(result)
            self.assertEqual("", result.json())

    def test_get_whoami_unknown_user_soft(self):
        # whoami is a soft endpoint: an unknown user is reported as no user
        # (200 + empty DN), never a 401 challenge.
        with self.client:
            result = self.client.get("/api/whoami", auth=("ghost", "password"))
            self.assertHTTPStatus(result)
            self.assertEqual("", result.json())

    def test_get_schema_unknown_user(self):
        # On authenticated endpoints, a user that does not exist must be
        # rejected with a 401 (rate-limited, #2).
        with self.client:
            result = self.client.get("/api/schema", auth=("ghost", "password"))
            self.assertHTTPStatus(result, HTTPStatus.UNAUTHORIZED)

    def test_get_schema_wrong_password(self):
        # A real user with the wrong password must also be rejected.
        with self.client:
            result = self.client.get("/api/schema", auth=(AUTH[0], "wrong"))
            self.assertHTTPStatus(result, HTTPStatus.UNAUTHORIZED)

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

    def test_default_search(self):
        with self.client:
            result = self.client.get("/api/search/fred", auth=AUTH)
            self.assertHTTPStatus(result)
            self.assertEqual(1, len(result.json()))
            self.assertEqual(FRED_DN, result.json()[0]["dn"])

    def test_attribute_search(self):
        with self.client:
            result = self.client.get("/api/search/gn=fred", auth=AUTH)
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


class LoginModeTest(LdapMixin, unittest.TestCase):
    "End-to-end login for every authentication mode documented in the README"

    client = TestClient(app)

    def setUp(self):
        self._orig_config = settings.config

    def tearDown(self):
        settings.config = self._orig_config

    def _set_bind_pattern(self, pattern: str | None):
        settings.config = (
            lambda k, default=None: pattern
            if k == "BIND_PATTERN"
            else self._orig_config(k, default=None)
        )

    def _whoami(self, user: str, password: str) -> httpx2.Response:
        with self.client:
            return self.client.get("/api/whoami", auth=(user, password))

    def test_search_mode(self):
        # No BIND_PATTERN: the anonymous search finds uid=admin and binds.
        self._set_bind_pattern(None)
        result = self._whoami("admin", "bedrock")
        self.assertEqual(200, result.status_code, result.text)
        self.assertEqual(ADMIN_DN.lower(), result.json().lower())

    def test_full_dn_bind_pattern(self):
        # BIND_PATTERN=%s: the user name is the full bind DN itself (#181).
        self._set_bind_pattern("%s")
        result = self._whoami(ADMIN_DN, "bedrock")
        self.assertEqual(200, result.status_code, result.text)
        self.assertEqual(ADMIN_DN.lower(), result.json().lower())

    def test_full_dn_bind_pattern_wrong_password(self):
        # Under BIND_PATTERN=%s a wrong password is plain bad credentials
        # (401), not a 500 invalid-DN crash (#181).
        self._set_bind_pattern("%s")
        result = self._whoami(ADMIN_DN, "wrong")
        self.assertEqual(
            HTTPStatus.UNAUTHORIZED, result.status_code, result.text
        )

    def test_partial_dn_bind_pattern(self):
        # BIND_PATTERN=%s,o=Flintstones: a partial RDN (cn=admin) is suffixed.
        self._set_bind_pattern(f"%s,{BASE_DN}")
        result = self._whoami("cn=admin", "bedrock")
        self.assertEqual(200, result.status_code, result.text)
        self.assertEqual(ADMIN_DN.lower(), result.json().lower())

    def test_attribute_value_bind_pattern(self):
        # BIND_PATTERN=cn=%s,o=Flintstones: a bare value fills the RDN.
        self._set_bind_pattern(f"cn=%s,{BASE_DN}")
        result = self._whoami("admin", "bedrock")
        self.assertEqual(200, result.status_code, result.text)
        self.assertEqual(ADMIN_DN.lower(), result.json().lower())


class ModificationTest(LdapMixin, unittest.TestCase):
    client = TestClient(app)

    def assertHTTPStatus(
        self, result: httpx2.Response, status_code=HTTPStatus.OK
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
            if result.status_code != HTTPStatus.CONFLICT:  # stale previous test run
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

    def test_091_self_change_password_requires_old(self):
        # Changing your own password demands the old one (#2): the directory's
        # password-modify operation silently skips verification when the old
        # password is omitted.
        with self.client:
            result = self.client.post(
                f"/api/change-password/{ADMIN_DN}",
                auth=AUTH,
                json={"old": "", "new1": "whatever"},
            )
            self.assertHTTPStatus(result, HTTPStatus.BAD_REQUEST)

    def test_092_change_password_failure_surfaced(self):
        # A failed password change is reported, not silently swallowed as 204.
        with self.client:
            result = self.client.post(
                "/api/change-password/cn=ghost,o=Flintstones",
                auth=AUTH,
                json={"old": "", "new1": "whatever"},
            )
            self.assertHTTPStatus(result, HTTPStatus.NOT_FOUND)

    def test_095_reject_rdn_injection(self):
        # RDN validation (#1): crafted or malformed RDNs must be rejected
        # without mutating the entry.
        for rdn in ("cn=a,dc=evil", "cn=a+sn=b", "cn="):
            with self.client:
                result = self.client.post(
                    f"/api/rename/{TEST_DN}", auth=AUTH, json=rdn
                )
                self.assertHTTPStatus(result, HTTPStatus.BAD_REQUEST)
        self.assertStillAt(TEST_DN)

    def assertStillAt(self, dn: str) -> None:
        with self.client:
            result = self.client.get(f"/api/entry/{dn}", auth=AUTH)
            self.assertHTTPStatus(result)

    def test_095_reject_invalid_attribute_name(self):
        # #5: malformed attribute names in entry modifications are rejected
        # with a 400 instead of being passed to the directory.
        with self.client:
            result = self.client.post(
                f"/api/entry/{TEST_DN}",
                auth=AUTH,
                json={"(cn=foo)": ["x"]},
            )
            self.assertHTTPStatus(result, HTTPStatus.BAD_REQUEST)
            result = self.client.put(
                f"/api/entry/{TEST_DN}",
                auth=AUTH,
                json={"(uid=bar)": ["y"]},
            )
            self.assertHTTPStatus(result, HTTPStatus.BAD_REQUEST)

    def test_100_rename_entry(self):
        with self.client:
            result = self.client.post(
                f"/api/rename/{TEST_DN}",
                auth=AUTH,
                json="sn=baz",
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)

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

    def test_131_ldif_hides_password_by_default(self):
        # #1: LDIF export excludes userPassword unless explicitly requested.
        with self.client:
            result = self.client.get(f"/api/ldif/{TEST_DN}", auth=AUTH)
            self.assertHTTPStatus(result)
            dn_attrs = parse_ldif(result.content).get(TEST_DN)
            self.assertTrue(dn_attrs is not None)
            assert dn_attrs is not None  # typing narrow
            self.assertNotIn("userPassword", dn_attrs)

    def test_132_ldif_never_exports_plaintext_password(self):
        # #1: even with include_sensitive, a plaintext-stored userPassword
        # (no RFC 2307 scheme prefix) is never exported.
        with self.client:
            result = self.client.get(
                f"/api/ldif/{TEST_DN}", params={"include_sensitive": "true"}, auth=AUTH
            )
            self.assertHTTPStatus(result)
            dn_attrs = parse_ldif(result.content).get(TEST_DN)
            self.assertTrue(dn_attrs is not None)
            assert dn_attrs is not None  # typing narrow
            self.assertNotIn("userPassword", dn_attrs)

    def test_140_delete_ldif(self):
        with self.client:
            result = self.client.delete(
                f"/api/entry/{TEST_DN}",
                auth=AUTH,
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)


if __name__ == "__main__":
    unittest.main()
