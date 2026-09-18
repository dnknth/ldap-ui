import io
import unittest
from base64 import b64decode
from http import HTTPStatus
from typing import cast

import httpx2
from anyio import Lock, create_task_group, sleep
from fastapi.testclient import TestClient
from ldap3 import SchemaInfo
from ldap3.core.connection import Connection
from ldap3.core.exceptions import LDAPInvalidDnError
from ldap_ui import ldap_api, ldap_connection, probe, settings
from ldap_ui.app import app
from ldap_ui.entities import Attributes, Range
from ldap_ui.ldap_api import (
    bounded_range,
    is_hashed_password,
    sanitize_export_entries,
)
from ldap_ui.schema import Schema, normalize_dn
from ldif import LDIFParser

from tests import mock_ldap

_ORIG_OPEN = ldap_connection.open
_ORIG_API_OPEN = ldap_api.open
_ORIG_CONFIG = settings.config
_ORIG_LDAP_URL = settings.LDAP_URL
_ORIG_BASE_DN = settings.BASE_DN
_ORIG_SCHEMA_DN = settings.SCHEMA_DN

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


class LdapMixin:
    """Base class wiring the tests to the in-process mock directory.

    Each test class starts from a freshly rebuilt directory (so modifications
    never leak between classes) and replaces the app's connection factory
    (``ldap_connection.open`` / its re-export in ``ldap_api``) with the mock.
    The developer's ``.env`` is deliberately ignored: BASE_DN/SCHEMA_DN are
    forced to auto-detection against the mock root DSE, and BIND_PATTERN is
    neutralized so login always runs in search mode.
    """

    @classmethod
    def setUpClass(cls):
        mock_ldap.reset()
        settings.LDAP_URL = "ldap://127.0.0.1:389"
        # Force auto-detection against the mock directory: a developer's .env
        # (e.g. BASE_DN=dc=foo) would otherwise make every search 404 with
        # "No Such Object".
        settings.BASE_DN = None
        settings.SCHEMA_DN = None
        # Neutralize a developer's BIND_PATTERN (and keep every other setting
        # lookup deterministic): login must resolve users by search.
        settings.config = lambda k, default=None: None  # type: ignore[assignment]
        ldap_connection.open = mock_ldap.mock_open
        ldap_api.open = mock_ldap.mock_open
        ldap_connection.SCHEMA = None

    @classmethod
    def tearDownClass(cls):
        # Restore the module state setUpClass changed, so classes that run
        # later (e.g. ProbeTest's dead-port URL) see the pre-test settings.
        ldap_connection.open = _ORIG_OPEN
        ldap_api.open = _ORIG_API_OPEN
        settings.config = _ORIG_CONFIG
        settings.LDAP_URL = _ORIG_LDAP_URL
        settings.BASE_DN = _ORIG_BASE_DN
        settings.SCHEMA_DN = _ORIG_SCHEMA_DN
        ldap_connection.SCHEMA = None


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
        """Attribute types and values match case-insensitively (RFC 4512/4514)."""
        self.assertEqual(
            normalize_dn("CN=Admin,OU=People,DC=demo,DC=com"),
            normalize_dn("cn=admin,ou=people,dc=demo,dc=com"),
        )

    def test_normalize_dn_distinct(self):
        """Different names normalize to different DNs."""
        self.assertNotEqual(
            normalize_dn("cn=admin,dc=demo"),
            normalize_dn("cn=other,dc=demo"),
        )

    def test_normalize_dn_value_case(self):
        """Name values are matched case-insensitively (the common directory
        equality behavior for cn/uid etc.)."""
        self.assertEqual(
            normalize_dn("Cn=Fred Flintstone,O=Flintstones"),
            normalize_dn("cn=FRED FLINTSTONE,o=flintstones"),
        )

    def test_normalize_dn_escape_equivalence(self):
        """RFC 4514: \\, and \\2C are equivalent encodings of the same value."""
        self.assertEqual(
            normalize_dn("cn=John\\, Doe,ou=People,dc=demo"),
            normalize_dn("cn=John\\2C Doe,ou=People,dc=demo"),
        )

    def test_normalize_dn_attribute_alias(self):
        """Schema aliases (gn == givenName) resolve through the schema's
        CaseInsensitiveWithAliasDict; without a schema they fall back to the
        lowercased name and do not match."""
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
        """An attribute type not in the schema is an invalid DN: it raises
        LDAPInvalidDnError, which is_self treats as "not self" (fail-closed),
        requiring the old password."""
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
        """Endpoints are printable when all values fit in the window."""
        self.assertEqual(
            Range(min=3, max=5, next=6), bounded_range({3, 4, 5})
        )

    def test_bounded_range_fills_gap(self):
        """The window fills the gap between min and max."""
        self.assertEqual(
            Range(min=1, max=4, next=2), bounded_range({1, 3, 4})
        )

    def test_bounded_range_clamps_high_values(self):
        """Values beyond the limit clamp to the upper bound."""
        self.assertEqual(
            Range(min=1, max=60000, next=2),
            bounded_range({1, 60001}),
        )

    def test_bounded_range_all_values_outside_bound(self):
        """All values exceed the limit: the window collapses onto the upper
        bound instead of allocating an unbounded range."""
        self.assertEqual(
            Range(min=60000, max=60000, next=60000),
            bounded_range({100001, 200001}),
        )

    def test_bounded_range_negative_values(self):
        """Negative values clamp to the lower bound of zero."""
        self.assertEqual(
            Range(min=0, max=3, next=0), bounded_range({-5, 1, 2, 3})
        )

    def test_bounded_range_all_negative_collapses_to_zero(self):
        """All-negative input collapses onto zero."""
        self.assertEqual(
            Range(min=0, max=0, next=0), bounded_range({-100, -200})
        )

    def test_bounded_range_full_window(self):
        """A full window has no free value: 'next' stays at the upper bound
        and never exceeds RANGE_LIMIT."""
        self.assertEqual(
            Range(min=0, max=2, next=2), bounded_range({0, 1, 2, 3, 4}, limit=2)
        )


class StripSensitiveTest(unittest.TestCase):
    "Unit tests for sanitize_export_entries / is_hashed_password (#1) — no directory"

    def entry(self, raw):
        return [{"type": "searchResEntry", "dn": "cn=x", "raw_attributes": raw}]

    def test_is_hashed_password(self):
        """Hashed schemes are recognized; plaintext and CLEARTEXT/PLAIN are not."""
        self.assertTrue(is_hashed_password(b"{SSHA}abc"))
        self.assertTrue(is_hashed_password(b"{SHA}def"))
        self.assertTrue(is_hashed_password("{MD5}ghi"))
        self.assertFalse(is_hashed_password(b"plaintext"))
        self.assertFalse(is_hashed_password(b"{CLEARTEXT}plain"))
        self.assertFalse(is_hashed_password(b"{PLAIN}plain"))

    def test_sensitive_kept_including_pkcs12(self):
        """Hashed passwords and userPKCS12 survive sanitization."""
        entries = self.entry(
            {
                "userPassword": [b"{SSHA}abc"],
                "userPKCS12": [b"pkcs"],
                "cn": [b"x"],
            }
        )
        result = sanitize_export_entries(entries)
        self.assertEqual(
            result[0]["raw_attributes"],
            {"userPassword": [b"{SSHA}abc"], "userPKCS12": [b"pkcs"], "cn": [b"x"]},
        )

    def test_sensitive_keeps_hashed_password(self):
        """A hashed password is kept."""
        entries = self.entry({"userPassword": [b"{SSHA}abc"], "cn": [b"x"]})
        result = sanitize_export_entries(entries)
        self.assertEqual(
            result[0]["raw_attributes"], {"userPassword": [b"{SSHA}abc"], "cn": [b"x"]}
        )

    def test_never_exports_plaintext(self):
        """Plaintext passwords are always dropped, even if the directory
        stores them that way (#1)."""
        entries = self.entry({"userPassword": [b"secret"], "cn": [b"x"]})
        result = sanitize_export_entries(entries)
        self.assertEqual(result[0]["raw_attributes"], {"cn": [b"x"]})

    def test_mixed_values(self):
        """Hashed values are kept, plaintext ones are dropped."""
        entries = self.entry(
            {"userPassword": [b"{SSHA}abc", b"plain"], "cn": [b"x"]}
        )
        result = sanitize_export_entries(entries)
        self.assertEqual(
            result[0]["raw_attributes"], {"userPassword": [b"{SSHA}abc"], "cn": [b"x"]}
        )

    def test_cleartext_scheme_never_exported(self):
        """CLEARTEXT-scheme passwords are never exported."""
        entries = self.entry({"userPassword": [b"{CLEARTEXT}plain"], "cn": [b"x"]})
        result = sanitize_export_entries(entries)
        self.assertEqual(result[0]["raw_attributes"], {"cn": [b"x"]})

    def test_base64_encoded_plaintext_never_exported(self):
        """A plaintext password is dropped even when the LDIF emission would
        base64-encode its raw value."""
        entries = self.entry({"userPassword": [b"plain"], "cn": [b"x"]})
        result = sanitize_export_entries(entries)
        self.assertEqual(result[0]["raw_attributes"], {"cn": [b"x"]})

    def test_preserves_non_sensitive(self):
        """Entries without sensitive attributes pass through unchanged."""
        entries = self.entry({"cn": [b"x"]})
        result = sanitize_export_entries(entries)
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
        """With no BIND_PATTERN set the username is not rewritten (None)."""
        self.assertIsNone(self._bind(None, "admin"))

    def test_malformed_pattern_raises(self):
        """Patterns without a %s placeholder, or with more than one, raise."""
        with self.assertRaises(ValueError):
            self._bind("no-placeholder", "admin")
        with self.assertRaises(ValueError):
            self._bind("cn=%s%s,o=x", "admin")

    def test_full_dn_unescaped(self):
        """Regression for #181: a full DN is inserted unchanged instead of
        being mangled by escape_rdn (the '=' and ',' got escaped)."""
        self.assertEqual(
            self._bind("%s", "cn=admin,o=Flintstones"),
            "cn=admin,o=Flintstones",
        )

    def test_partial_dn_unescaped(self):
        """A partial RDN (cn=admin) keeps its structure; the suffix is appended."""
        self.assertEqual(
            self._bind("%s,o=Flintstones", "cn=admin"),
            "cn=admin,o=Flintstones",
        )

    def test_bare_value_interpolated(self):
        """A bare value fills the %s placeholder."""
        self.assertEqual(
            self._bind("cn=%s,o=Flintstones", "admin"),
            "cn=admin,o=Flintstones",
        )

    def test_bare_value_escaped(self):
        """A non-DN bare value is RFC 4514-escaped so it cannot inject a
        stray attribute into the RDN."""
        self.assertEqual(
            self._bind("cn=%s,o=Flintstones", "a+b"),
            "cn=a\\+b,o=Flintstones",
        )


class ProbeTest(unittest.TestCase):
    "Test the /api/probe LDAP connectivity probe — no directory required"

    client = TestClient(app)

    def setUp(self):
        self._orig_ldap_url = settings.LDAP_URL

    def tearDown(self):
        # Restore, so we don't leak the dead-port URL into other test classes.
        settings.LDAP_URL = self._orig_ldap_url

    def test_probe_unreachable(self):
        """A closed port reports ok=false with a diagnostic but still a 200,
        so the frontend can read the details.

        The probe runs once at lifespan startup, so the URL is set before
        entering the client (the endpoint serves the cached result)."""
        settings.LDAP_URL = "ldap://127.0.0.1:1/"
        with self.client:
            result = self.client.get("/api/probe")
            self.assertEqual(result.status_code, HTTPStatus.OK)  # 200
            body = result.json()
            self.assertFalse(body["ok"])
            messages = [d["message"] for d in body["diagnostics"]]
            self.assertTrue(
                any("Cannot connect" in m for m in messages),
                messages,
            )

    def test_probe_invalid_url(self):
        """An unparseable URL is reported as unreachable but still a 200."""
        settings.LDAP_URL = "not-a-url"
        with self.client:
            result = self.client.get("/api/probe")
            self.assertEqual(result.status_code, HTTPStatus.OK)
            body = result.json()
            self.assertFalse(body["ok"])
            messages = [d["message"] for d in body["diagnostics"]]
            self.assertTrue(
                any("Cannot connect" in m for m in messages),
                messages,
            )

    def test_probe_insecure_tls_warning(self):
        """INSECURE_TLS=1 surfaces a "certificate checking is disabled"
        warning diagnostic."""
        settings.LDAP_URL = "ldaps://127.0.0.1:1/"
        settings.INSECURE_TLS = True
        old = settings.config("INSECURE_TLS", default=False)
        try:
            with self.client:
                body = self.client.get("/api/probe").json()
        finally:
            settings.INSECURE_TLS = old
        self.assertTrue(
            any(
                d["severity"] == "warning"
                and "TLS certificate checking is disabled" in d["message"]
                for d in body["diagnostics"]
            )
        )

    def test_probe_bind_pattern_warning(self):
        """A malformed BIND_PATTERN surfaces an error diagnostic."""
        old_config = settings.config
        try:
            settings.config = lambda k, default=None: "bad-pattern"
            with self.client:
                body = self.client.get("/api/probe").json()
        finally:
            settings.config = old_config
        self.assertTrue(
            any(
                d["severity"] == "error"
                and "BIND_PATTERN setting is malformed" in d["message"]
                for d in body["diagnostics"]
            )
        )

    def test_probe_refreshes_when_stale(self):
        """A cached result past PROBE_TTL triggers a fresh probe instead of
        serving the stale snapshot, so a directory that comes up later is
        picked up on refresh."""
        settings.LDAP_URL = "ldap://127.0.0.1:1/"
        with self.client:
            self.assertFalse(self.client.get("/api/probe").json()["ok"])
            at_before = probe._startup_probe_at
            # Force the cache past its TTL without waiting PROBE_TTL seconds.
            probe._startup_probe_at -= probe.PROBE_TTL + 1
            self.client.get("/api/probe")
            # A stale cache re-probes, which advances the cached timestamp.
            self.assertGreater(probe._startup_probe_at, at_before)



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
            await sleep(0.01)  # widen the race window
            return schema

        original = (
            ldap_connection.SCHEMA,
            ldap_connection._SCHEMA_LOCK,
            ldap_connection.get_schema,
        )
        ldap_connection.SCHEMA = None
        ldap_connection._SCHEMA_LOCK = Lock()
        ldap_connection.get_schema = fake_get_schema
        return calls, original

    async def test_ensure_schema_fetches_once(self):
        """Concurrent ensure_schema() calls fetch the schema exactly once."""
        calls, (schema, lock, get_schema) = self.monkeypatch_schema()
        connection = cast(Connection, object())  # unused by the fake
        results: list[SchemaInfo] = []

        async def _ensure() -> None:
            results.append(await ldap_api.ensure_schema(connection))

        try:
            # anyio has no gather(); a task group runs the calls concurrently
            # and the count assertion is what matters (not ordering/results).
            async with create_task_group() as tg:
                for _ in range(20):
                    tg.start_soon(_ensure)
        finally:
            ldap_connection.SCHEMA, ldap_connection._SCHEMA_LOCK, ldap_connection.get_schema = (
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
        """whoami with credentials returns the bound DN."""
        with self.client:
            result = self.client.get("/api/whoami", auth=AUTH)
            self.assertHTTPStatus(result)
            self.assertEqual(ADMIN_DN.lower(), result.json().lower())

    def test_get_whoami_anonymous(self):
        """whoami is a soft endpoint: without credentials it returns an empty
        DN (200) rather than a 401 challenge, so the frontend probe never
        triggers the browser's native Basic-auth popup."""
        with self.client:
            result = self.client.get("/api/whoami")
            self.assertHTTPStatus(result)
            self.assertEqual("", result.json())

    def test_get_whoami_unknown_user_soft(self):
        """whoami is a soft endpoint: an unknown user is reported as no user
        (200 + empty DN), never a 401 challenge."""
        with self.client:
            result = self.client.get("/api/whoami", auth=("ghost", "password"))
            self.assertHTTPStatus(result)
            self.assertEqual("", result.json())

    def test_get_schema_unknown_user(self):
        """On authenticated endpoints, a user that does not exist must be
        rejected with a 401 (rate-limited, #2)."""
        with self.client:
            result = self.client.get("/api/schema", auth=("ghost", "password"))
            self.assertHTTPStatus(result, HTTPStatus.UNAUTHORIZED)

    def test_get_schema_wrong_password(self):
        """A real user with the wrong password must also be rejected."""
        with self.client:
            result = self.client.get("/api/schema", auth=(AUTH[0], "wrong"))
            self.assertHTTPStatus(result, HTTPStatus.UNAUTHORIZED)

    def test_get_schema(self):
        """The schema endpoint returns attribute, objectClass, and syntax info."""
        with self.client:
            result = self.client.get("/api/schema", auth=AUTH)
            self.assertHTTPStatus(result)

            schema = Schema.model_validate(result.json())
            self.assertTrue(schema.attributes)
            self.assertTrue(schema.objectClasses)
            self.assertTrue(schema.syntaxes)

    def test_get_tree_base(self):
        """The tree at the base DN lists only the naming-context entry."""
        with self.client:
            result = self.client.get("/api/tree/base", auth=AUTH)
            self.assertHTTPStatus(result)
            entries = result.json()
            self.assertEqual(1, len(entries))
            self.assertEqual(BASE_DN, entries[0]["dn"])

    def test_get_tree_flintstones(self):
        """The tree under o=Flintstones lists the top-level entries."""
        with self.client:
            result = self.client.get("/api/tree/o=Flintstones", auth=AUTH)
            self.assertHTTPStatus(result)
            self.assertGreaterEqual(len(result.json()), 4)

    def test_default_search(self):
        """A bare query searches common attributes (cn/mail/uid/sn)."""
        with self.client:
            result = self.client.get("/api/search/fred", auth=AUTH)
            self.assertHTTPStatus(result)
            self.assertEqual(1, len(result.json()))
            self.assertEqual(FRED_DN, result.json()[0]["dn"])

    def test_attribute_search(self):
        """An 'gn=' query resolves the schema alias and finds the person."""
        with self.client:
            result = self.client.get("/api/search/gn=fred", auth=AUTH)
            self.assertHTTPStatus(result)
            self.assertEqual(1, len(result.json()))
            self.assertEqual(FRED_DN, result.json()[0]["dn"])

    def test_verify_password(self):
        """The password check succeeds with correct credentials."""
        with self.client:
            result = self.client.post(
                "/api/check-password/cn=admin,o=Flintstones",
                auth=AUTH,
                json=AUTH[1],
            )
            self.assertHTTPStatus(result)
            self.assertEqual(True, result.json())

    def test_get_subtree(self):
        """The subtree of ou=Pets lists the two pet entries."""
        with self.client:
            result = self.client.get("/api/subtree/ou=Pets,o=Flintstones", auth=AUTH)
            self.assertHTTPStatus(result)
            self.assertEqual(2, len(result.json()))

    def test_get_range(self):
        """The numeric range for uidNumber reports min/max/next."""
        with self.client:
            result = self.client.get("/api/range/uidNumber", auth=AUTH)
            self.assertHTTPStatus(result)
            range = result.json()
            self.assertTrue("min" in range and "max" in range and "next" in range)

    def test_get_invalid_range(self):
        """A range for a non-numeric attribute returns 404."""
        with self.client:
            result = self.client.get("/api/range/cn", auth=AUTH)
            self.assertHTTPStatus(result, HTTPStatus.NOT_FOUND)

    def test_get_unknown_range(self):
        """A range for a name not in the schema is a 404, not a 500."""
        with self.client:
            result = self.client.get("/api/range/zzz", auth=AUTH)
            self.assertHTTPStatus(result, HTTPStatus.NOT_FOUND)

    def test_get_empty_integer_range(self):
        """A range for an integer attribute (shadowMax) no entry carries is a
        404, exercising the empty-values branch of a numeric attribute."""
        with self.client:
            result = self.client.get("/api/range/shadowMax", auth=AUTH)
            self.assertHTTPStatus(result, HTTPStatus.NOT_FOUND)


class LoginModeTest(LdapMixin, unittest.TestCase):
    "End-to-end login for every authentication mode documented in the README"

    client = TestClient(app)

    def setUp(self):
        self._orig_config = settings.config
        self._orig_bind_as_user = settings.BIND_AS_USER

    def tearDown(self):
        settings.config = self._orig_config
        settings.BIND_AS_USER = self._orig_bind_as_user

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
        """No BIND_PATTERN: the anonymous search finds uid=admin and binds."""
        self._set_bind_pattern(None)
        result = self._whoami("admin", "bedrock")
        self.assertEqual(200, result.status_code, result.text)
        self.assertEqual(ADMIN_DN.lower(), result.json().lower())

    def test_full_dn_bind_pattern(self):
        """BIND_PATTERN=%s: the user name is the full bind DN itself (#181)."""
        self._set_bind_pattern("%s")
        result = self._whoami(ADMIN_DN, "bedrock")
        self.assertEqual(200, result.status_code, result.text)
        self.assertEqual(ADMIN_DN.lower(), result.json().lower())

    def test_full_dn_bind_pattern_wrong_password(self):
        """Under BIND_PATTERN=%s a wrong password is plain bad credentials
        (401), not a 500 invalid-DN crash (#181)."""
        self._set_bind_pattern("%s")
        result = self._whoami(ADMIN_DN, "wrong")
        self.assertEqual(
            HTTPStatus.UNAUTHORIZED, result.status_code, result.text
        )

    def test_partial_dn_bind_pattern(self):
        """BIND_PATTERN=%s,o=Flintstones: a partial RDN (cn=admin) is suffixed."""
        self._set_bind_pattern(f"%s,{BASE_DN}")
        result = self._whoami("cn=admin", "bedrock")
        self.assertEqual(200, result.status_code, result.text)
        self.assertEqual(ADMIN_DN.lower(), result.json().lower())

    def test_attribute_value_bind_pattern(self):
        """BIND_PATTERN=cn=%s,o=Flintstones: a bare value fills the RDN."""
        self._set_bind_pattern(f"cn=%s,{BASE_DN}")
        result = self._whoami("admin", "bedrock")
        self.assertEqual(200, result.status_code, result.text)
        self.assertEqual(ADMIN_DN.lower(), result.json().lower())

    def test_bind_as_user(self):
        # In BIND_AS_USER mode, BIND_PATTERN resolves the DN before opening
        # the connection. The initial bind therefore uses the login user's
        # own credentials and needs no anonymous or service-account bind.
        settings.BIND_AS_USER = True
        self._set_bind_pattern(f"cn=%s,{BASE_DN}")
        result = self._whoami("admin", "bedrock")
        self.assertEqual(200, result.status_code, result.text)
        self.assertEqual(ADMIN_DN.lower(), result.json().lower())

    def test_bind_as_user_wrong_password(self):
        settings.BIND_AS_USER = True
        self._set_bind_pattern(f"cn=%s,{BASE_DN}")
        result = self._whoami("admin", "wrong")
        self.assertEqual(HTTPStatus.UNAUTHORIZED, result.status_code, result.text)

    def test_bind_as_user_requires_bind_pattern(self):
        """BIND_AS_USER without BIND_PATTERN is a server config problem:
        a clean 503 on login, not an opaque ValueError 500."""
        settings.BIND_AS_USER = True
        self._set_bind_pattern(None)
        result = self._whoami("admin", "bedrock")
        self.assertEqual(
            HTTPStatus.SERVICE_UNAVAILABLE, result.status_code, result.text
        )

    def test_bind_as_user_malformed_bind_pattern(self):
        """BIND_AS_USER with a BIND_PATTERN missing its %s placeholder is
        misconfiguration: also surfaced as a 503, not a 500."""
        settings.BIND_AS_USER = True
        self._set_bind_pattern("cn=admin")
        result = self._whoami("admin", "bedrock")
        self.assertEqual(
            HTTPStatus.SERVICE_UNAVAILABLE, result.status_code, result.text
        )


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
        """PUT creates the entry with the given attributes (204)."""
        with self.client:
            result = self.client.put(
                f"/api/entry/{TEST_DN}",
                auth=AUTH,
                json=TEST_PERSON,
            )
            if result.status_code != HTTPStatus.CONFLICT:  # stale previous test run
                self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)
            self.assertEntryEqual(TEST_DN, TEST_PERSON)

    def test_020_put_entry_again(self):
        """PUT on an existing DN rejects with 409 Entry Already Exists."""
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
        """POST modifies the entry and reports the changed attributes."""
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
        """A JPEG blob uploads into jpegPhoto (204)."""
        with self.client:
            result = self.client.put(
                f"/api/blob/jpegPhoto/0/{TEST_DN}",
                auth=AUTH,
                files={"blob": JPEG},
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)

    def test_060_delete_image_from_entry(self):
        """Deleting the image removes it (204)."""
        with self.client:
            result = self.client.delete(
                f"/api/blob/jpegPhoto/0/{TEST_DN}",
                auth=AUTH,
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)

    def test_070_delete_image_from_entry_again(self):
        """Deleting the image a second time reports 404."""
        with self.client:
            result = self.client.delete(f"/api/blob/jpegPhoto/0/{TEST_DN}", auth=AUTH)
            self.assertHTTPStatus(result, HTTPStatus.NOT_FOUND)

    def test_080_change_password(self):
        """The password changes when the old one is correct (204)."""
        with self.client:
            result = self.client.post(
                f"/api/change-password/{TEST_DN}",
                auth=AUTH,
                json={"old": "test", "new1": "abc"},
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)

    def test_090_remove_password(self):
        """An empty new password removes the stored password."""
        with self.client:
            result = self.client.post(
                f"/api/change-password/{TEST_DN}",
                auth=AUTH,
                json={"old": "test", "new1": ""},
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)

    def test_091_self_change_password_requires_old(self):
        """Changing your own password demands the old one (#2): the directory's
        password-modify operation silently skips verification when the old
        password is omitted."""
        with self.client:
            result = self.client.post(
                f"/api/change-password/{ADMIN_DN}",
                auth=AUTH,
                json={"old": "", "new1": "whatever"},
            )
            self.assertHTTPStatus(result, HTTPStatus.BAD_REQUEST)

    def test_092_change_password_failure_surfaced(self):
        """A failed password change is reported, not silently swallowed as 204."""
        with self.client:
            result = self.client.post(
                "/api/change-password/cn=ghost,o=Flintstones",
                auth=AUTH,
                json={"old": "", "new1": "whatever"},
            )
            self.assertHTTPStatus(result, HTTPStatus.NOT_FOUND)

    def test_095_reject_rdn_injection(self):
        """RDN validation (#1): crafted or malformed RDNs are rejected
        without mutating the entry."""
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
        """Malformed attribute names in modifications are rejected with a 400
        instead of being passed to the directory (#5)."""
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
        """Renaming moves the entry and updates the RDN attribute's value."""
        with self.client:
            result = self.client.post(
                f"/api/rename/{TEST_DN}",
                auth=AUTH,
                json="sn=baz",
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)
            # The renamed attribute must carry the new value (matching the DN),
            # not the old one from before the rename.
            renamed = self.client.get(f"/api/entry/sn=baz,{BASE_DN}", auth=AUTH)
            self.assertHTTPStatus(renamed)
            self.assertEqual(renamed.json()["attrs"]["sn"], ["baz"])

    def test_110_delete_entry(self):
        """The renamed entry can be deleted (204)."""
        with self.client:
            result = self.client.delete(
                f"/api/entry/sn=baz,{BASE_DN}",
                auth=AUTH,
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)

    def test_120_put_ldif(self):
        """Uploading the LDIF imports the entry (204)."""
        with self.client:
            result = self.client.put("/api/ldif", auth=AUTH, content=TEST_LDIF)
            if result.status_code != HTTPStatus.CONFLICT:  # stale previous test run?
                self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)
            self.assertEntryEqual(TEST_DN, TEST_PERSON)

    def test_130_compare_ldif(self):
        """The LDIF export round-trips the uploaded entry."""
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

    def test_131_ldif_never_exports_plaintext_password(self):
        """#1: the test password is stored in plaintext, so LDIF export must
        omit it; hashed values are exported (covered by StripSensitiveTest)."""
        with self.client:
            result = self.client.get(f"/api/ldif/{TEST_DN}", auth=AUTH)
            self.assertHTTPStatus(result)
            dn_attrs = parse_ldif(result.content).get(TEST_DN)
            self.assertTrue(dn_attrs is not None)
            assert dn_attrs is not None  # typing narrow
            self.assertNotIn("userPassword", dn_attrs)

    def test_140_delete_ldif(self):
        """The imported entry deletes cleanly (204)."""
        with self.client:
            result = self.client.delete(
                f"/api/entry/{TEST_DN}",
                auth=AUTH,
            )
            self.assertHTTPStatus(result, HTTPStatus.NO_CONTENT)


if __name__ == "__main__":
    unittest.main()
