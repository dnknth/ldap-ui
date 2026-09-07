import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from ldap3.core.exceptions import (
    LDAPInappropriateAuthenticationResult,
    LDAPInvalidCredentialsResult,
    LDAPNoSuchObjectResult,
    LDAPResponseTimeoutError,
)
from ldap_ui import ldap_api, ldap_connection, ldap_helpers, probe, settings


class StartTlsOrderingTest(unittest.IsolatedAsyncioTestCase):
    """`ldap_connect()` must negotiate StartTLS before it binds.

    Binding first would expose the bind and the root DSE lookup in clear
    text, and directories that require confidentiality (e.g. OpenLDAP
    `olcSecurity: tls=1`) reject any operation attempted before TLS is in
    place. See RFC 4513, §3.1.1 (StartTLS Request Sequencing).
    """

    async def _operation_order(self, ldap_url: str) -> list[str]:
        "Record the order of connection operations for the given URL."

        order: list[str] = []
        connection = MagicMock(name="Connection")
        for op in ("open", "start_tls", "bind"):
            getattr(connection, op).side_effect = lambda *args, _op=op, **kwargs: (
                order.append(_op)
            )

        # Pin BASE_DN/SCHEMA_DN so the root DSE auto-detection is skipped and
        # the test stays focused on the connection setup sequence.
        with (
            patch.object(ldap_connection, "Connection", return_value=connection),
            patch.object(settings, "LDAP_URL", ldap_url),
            patch.object(settings, "USE_TLS", True),
            patch.object(settings, "BASE_DN", "o=Flintstones"),
            patch.object(settings, "SCHEMA_DN", "cn=Subschema"),
        ):
            async with ldap_connection.ldap_connect():
                pass

        return order

    async def test_starttls_precedes_bind(self):
        order = await self._operation_order("ldap://ldap.example.com")
        self.assertIn("start_tls", order, "StartTLS was not negotiated")
        self.assertIn("bind", order)
        self.assertLess(
            order.index("start_tls"),
            order.index("bind"),
            "bind() must not run before StartTLS is established",
        )

    async def test_ldaps_skips_starttls(self):
        # ldaps:// is wrapped in TLS from the first byte, so an explicit
        # StartTLS would be a protocol error.
        order = await self._operation_order("ldaps://ldap.example.com")
        self.assertNotIn("start_tls", order)
        self.assertIn("bind", order)


class InitialBindCredentialsTest(unittest.TestCase):
    """`open()` forwards optional credentials to ldap3.Connection."""

    def _open(
        self,
        bind_dn: str | None = None,
        bind_password: str | None = None,
    ):
        with patch.object(ldap_connection, "Connection") as connection_cls:
            ldap_connection.open(
                "ldap://ldap.example.com",
                "NO_INFO",
                bind_dn,
                bind_password,
            )
        return connection_cls.call_args.kwargs

    def test_anonymous_by_default(self):
        kwargs = self._open()
        self.assertIsNone(kwargs["user"])
        self.assertIsNone(kwargs["password"])

    def test_uses_supplied_credentials(self):
        kwargs = self._open("uid=fred,o=Flintstones", "secret")
        self.assertEqual(kwargs["user"], "uid=fred,o=Flintstones")
        self.assertEqual(kwargs["password"], "secret")


class LdapConnectResolutionTest(unittest.IsolatedAsyncioTestCase):
    """`ldap_connect()` resolves base/schema best-effort and never raises:
    it leaves the settings unset when the directory is ambiguous or
    contradicts the configuration (diagnosing those is /api/probe's job)."""

    def _connection(self, naming_contexts, schema_entry=None):
        server = MagicMock(name="Server")
        server.info.naming_contexts = naming_contexts
        # ldap3 exposes schema_entry as a list (entry DN at [0])
        server.info.schema_entry = schema_entry or []
        connection = MagicMock(name="Connection")
        connection.server.info = server.info
        return connection

    async def _connect(self, **overrides) -> tuple[str | None, str | None]:
        settings_patch = {
            "LDAP_URL": "ldap://ldap.example.com/",
            "BASE_DN": None,
            "SCHEMA_DN": None,
        }
        settings_patch.update(overrides)
        # `ldap_connect` reads the real `settings` module and calls the
        # patched `Connection` constructor; mirror the settings attrs so the
        # resolution logic sees what each test intends. Return the resolved
        # base/schema as they were seen inside the patch, before teardown.
        with (
            patch.object(
                ldap_connection,
                "Connection",
                side_effect=lambda *a, **k: self._connection(
                    settings_patch["_naming_contexts"],
                    settings_patch.get("_schema_entry"),
                ),
            ),
            patch.object(settings, "LDAP_URL", settings_patch["LDAP_URL"]),
            patch.object(settings, "BASE_DN", settings_patch["BASE_DN"]),
            patch.object(settings, "SCHEMA_DN", settings_patch["SCHEMA_DN"]),
        ):
            async with ldap_connection.ldap_connect():
                pass
            return settings.BASE_DN, settings.SCHEMA_DN

    async def test_ambiguous_base_left_unset(self):
        # Multiple naming contexts: nothing to resolve to, so BASE_DN stays
        # None (no raise) and the probe reports it.
        base_dn, _ = await self._connect(
            _naming_contexts=["dc=one", "dc=two"],
        )
        self.assertIsNone(base_dn)

    async def test_missing_schema_left_unset(self):
        _, schema_dn = await self._connect(
            _naming_contexts=["dc=one"],
            _schema_entry=None,
        )
        self.assertIsNone(schema_dn)

    async def test_resolves_single_unique_base(self):
        base_dn, schema_dn = await self._connect(
            _naming_contexts=["dc=example,dc=com"],
            _schema_entry=["cn=Subschema"],
        )
        self.assertEqual(base_dn, "dc=example,dc=com")
        self.assertEqual(schema_dn, "cn=Subschema")


class GetResponsesTimeoutTest(unittest.IsolatedAsyncioTestCase):
    """`get_raw_responses` must not wait on a stuck directory forever: it
    aborts the operation and reports a 504 when the overall timeout fires."""

    async def test_times_out_and_aborts(self):
        connection = MagicMock(name="Connection")
        # Never complete: keep raising LDAPResponseTimeoutError forever.
        connection.get_response.side_effect = LDAPResponseTimeoutError
        connection.abandon = MagicMock()

        with (
            patch.object(ldap_helpers, "OPERATION_TIMEOUT", 0.05),
            self.assertRaises(HTTPException) as ctx,
        ):
            async for _ in ldap_helpers.get_raw_responses(connection, 1):
                pass

        self.assertEqual(ctx.exception.status_code, 504)
        connection.abandon.assert_called_once_with(1)

    async def test_streams_results_when_ready(self):
        connection = MagicMock(name="Connection")
        connection.get_response.return_value = ([{"dn": "cn=x"}], None)

        items = [r async for r in ldap_helpers.get_raw_responses(connection, 1)]
        self.assertEqual(items, [[{"dn": "cn=x"}]])


class RunProbeAsyncTest(unittest.IsolatedAsyncioTestCase):
    """The /api/probe endpoint must distinguish a wrong base/schema DN (LDAP
    operation failure) from an unreachable directory, so the frontend shows
    the right message."""

    @staticmethod
    @asynccontextmanager
    async def _connect(connection):
        yield connection

    def _probe_connection(self):
        "Mocked anonymous connection whose searches raise an LDAP error."
        connection = MagicMock(name="Connection")
        connection.search.return_value = 1
        connection.get_response.side_effect = LDAPNoSuchObjectResult
        return connection

    async def test_wrong_base_dn_reports_base_dn_not_unreachable(self):
        # A manually configured BASE_DN that doesn't exist is reported as a
        # configured-base problem, not an unreachable directory.
        connection = self._probe_connection()
        with (
            patch.object(
                probe,
                "ldap_connect",
                side_effect=lambda: self._connect(connection),
            ),
            patch.object(settings, "BASE_DN", "dc=nope"),
            patch.object(settings, "SCHEMA_DN", "cn=Subschema"),
            patch.object(settings, "INSECURE_TLS", False),
            patch.object(settings, "BIND_AS_USER", False),
            patch.object(
                settings,
                "config",
                lambda k, default=None: {
                    "BASE_DN": "dc=nope",
                    "SCHEMA_DN": "cn=Subschema",
                }.get(k, default),
            ),
        ):
            result = await probe.run_probe()

        messages = [d.message for d in result.diagnostics]
        self.assertTrue(
            any("configured base entry does not exist" in m for m in messages),
            messages,
        )
        self.assertFalse(any("Cannot connect" in m for m in messages), messages)

    async def test_auto_detected_base_dn_unreadable(self):
        # BASE_DN was filled in by root-DSE auto-detection but the entry cannot
        # be read: suggest providing it explicitly.
        connection = self._probe_connection()
        with (
            patch.object(
                probe,
                "ldap_connect",
                side_effect=lambda: self._connect(connection),
            ),
            patch.object(settings, "BASE_DN", "dc=auto"),
            patch.object(settings, "SCHEMA_DN", "cn=Subschema"),
            patch.object(settings, "INSECURE_TLS", False),
            patch.object(settings, "BIND_AS_USER", False),
            patch.object(settings, "config", lambda _k, default=None: default),
        ):
            result = await probe.run_probe()

        messages = [d.message for d in result.diagnostics]
        self.assertTrue(
            any("auto-detected base entry" in m for m in messages),
            messages,
        )
        self.assertTrue(
            any("auto-detected schema" in m for m in messages),
            messages,
        )

    async def test_user_bind_mode_skips_anonymous_access_checks(self):
        # FreeIPA commonly permits an anonymous root-DSE connection but
        # rejects anonymous reads below it. Those reads say nothing about
        # BIND_AS_USER requests, which perform them as the login user.
        connection = self._probe_connection()
        with (
            patch.object(
                probe,
                "ldap_connect",
                side_effect=lambda: self._connect(connection),
            ),
            patch.object(settings, "BASE_DN", "dc=example,dc=com"),
            patch.object(settings, "SCHEMA_DN", "cn=Subschema"),
            patch.object(settings, "INSECURE_TLS", False),
            patch.object(settings, "BIND_AS_USER", True),
            patch.object(
                settings,
                "config",
                lambda k, default=None: "%s" if k == "BIND_PATTERN" else default,
            ),
        ):
            result = await probe.run_probe()

        self.assertTrue(result.ok)
        self.assertEqual(result.diagnostics, [])
        connection.search.assert_not_called()

    @staticmethod
    @asynccontextmanager
    async def _reject_anonymous_bind():
        raise LDAPInappropriateAuthenticationResult(
            [{"desc": "anonymous bind denied"}]
        )
        yield  # pragma: no cover

    async def test_anonymous_bind_denied_without_bind_pattern_error(self):
        # Without user-bound mode, a directory that rejects anonymous binds
        # makes the app unusable before login credentials are tried.
        with (
            patch.object(
                probe,
                "ldap_connect",
                side_effect=self._reject_anonymous_bind,
            ),
            patch.object(settings, "BASE_DN", "dc=example,dc=com"),
            patch.object(settings, "SCHEMA_DN", "cn=Subschema"),
            patch.object(settings, "INSECURE_TLS", False),
            patch.object(settings, "BIND_AS_USER", False),
            patch.object(settings, "config", lambda _k, default=None: default),
        ):
            result = await probe.run_probe()

        self.assertFalse(result.ok)
        self.assertTrue(
            any(
                d.severity == "error"
                and "rejects anonymous binds" in d.message
                for d in result.diagnostics
            ),
            result.diagnostics,
        )

    async def test_anonymous_bind_denied_with_user_bind_mode_silent(self):
        # The unauthenticated probe cannot bind, but this is expected:
        # authenticated requests derive the DN from BIND_PATTERN and open
        # their initial connection with the login user's credentials.
        with (
            patch.object(
                probe,
                "ldap_connect",
                side_effect=self._reject_anonymous_bind,
            ),
            patch.object(settings, "BASE_DN", "dc=example,dc=com"),
            patch.object(settings, "SCHEMA_DN", "cn=Subschema"),
            patch.object(settings, "INSECURE_TLS", False),
            patch.object(settings, "BIND_AS_USER", True),
            patch.object(
                settings,
                "config",
                lambda k, default=None: "%s" if k == "BIND_PATTERN" else default,
            ),
        ):
            result = await probe.run_probe()

        self.assertTrue(result.ok)
        self.assertEqual(result.diagnostics, [])

    async def test_bind_pattern_alone_does_not_fix_rejected_anonymous_bind(self):
        # BIND_PATTERN avoids the username search, but normal mode still
        # opens its initial connection anonymously. BIND_AS_USER is the
        # switch that bypasses that failed bind.
        with (
            patch.object(
                probe,
                "ldap_connect",
                side_effect=self._reject_anonymous_bind,
            ),
            patch.object(settings, "BASE_DN", "dc=example,dc=com"),
            patch.object(settings, "SCHEMA_DN", "cn=Subschema"),
            patch.object(settings, "INSECURE_TLS", False),
            patch.object(settings, "BIND_AS_USER", False),
            patch.object(
                settings,
                "config",
                lambda k, default=None: "%s" if k == "BIND_PATTERN" else default,
            ),
        ):
            result = await probe.run_probe()

        self.assertFalse(result.ok)
        self.assertTrue(
            any("BIND_AS_USER" in d.message for d in result.diagnostics),
            result.diagnostics,
        )

    async def test_user_bind_mode_requires_bind_pattern(self):
        with (
            patch.object(
                probe,
                "ldap_connect",
                side_effect=self._reject_anonymous_bind,
            ),
            patch.object(settings, "BASE_DN", None),
            patch.object(settings, "SCHEMA_DN", None),
            patch.object(settings, "INSECURE_TLS", False),
            patch.object(settings, "BIND_AS_USER", True),
            patch.object(settings, "config", lambda _k, default=None: default),
        ):
            result = await probe.run_probe()

        self.assertFalse(result.ok)
        self.assertTrue(
            any(
                "BIND_AS_USER requires BIND_PATTERN" in d.message
                for d in result.diagnostics
            ),
            result.diagnostics,
        )

    def _connection(self) -> MagicMock:
        "A mock Connection whose call order is recorded."
        connection = MagicMock(name="Connection")
        order: list[str] = []
        connection.rebind.side_effect = lambda *a, **k: order.append("rebind")
        connection.unbind.side_effect = lambda *a, **k: order.append("unbind")
        connection._order = order
        return connection

    async def test_binds_and_unbinds_around_body(self):
        connection = self._connection()

        async with ldap_connection.bound(connection, "cn=test,o=Flintstones", "secret"):
            connection._order.append("body")

        self.assertEqual(connection._order, ["rebind", "body", "unbind"])
        connection.rebind.assert_called_once_with(
            user="cn=test,o=Flintstones", password="secret"
        )

    async def test_invalid_credentials_re_raised_and_unbind_runs(self):
        connection = self._connection()
        connection.rebind.side_effect = LDAPInvalidCredentialsResult(
            [{"desc": "bad password"}]
        )

        with self.assertRaises(LDAPInvalidCredentialsResult):
            async with ldap_connection.bound(connection, "cn=test", "wrong"):
                pass

        # The connection is still closed even on failure.
        connection.unbind.assert_called_once()
        self.assertEqual(connection._order, ["unbind"])

    async def test_invalid_credentials_are_rate_limited(self):
        connection = self._connection()
        connection.rebind.side_effect = LDAPInvalidCredentialsResult(
            [{"desc": "bad password"}]
        )

        with (
            patch.object(ldap_connection, "random", return_value=0.5),
            patch.object(ldap_connection, "sleep", new=AsyncMock()) as sleep,
            self.assertRaises(LDAPInvalidCredentialsResult),
        ):
            async with ldap_connection.bound(connection, "cn=test", "wrong"):
                pass

        sleep.assert_awaited_once_with(0.5 + 0.5 / 5)

    async def test_unbind_errors_are_swallowed(self):
        connection = self._connection()
        connection.unbind.side_effect = RuntimeError("connection already closed")

        # A failing unbind must not mask the successful bind / body.
        async with ldap_connection.bound(connection, "cn=test", "secret"):
            pass

        connection.unbind.assert_called_once()


class ChangePasswordAsyncTest(unittest.IsolatedAsyncioTestCase):
    """`change_password` must issue the password-modify extended operation via
    the async polling idiom (extended() + empty), not the blocking
    `connection.extend.standard.modify_password(...)` which would stall the
    event loop."""

    async def test_extended_issue_and_poll(self):
        connection = MagicMock(name="Connection")
        connection.check_names = True
        connection.user = None  # not self: the old password is not required
        connection.extended.return_value = 3
        connection.get_response.return_value = ([], {"result": 0})

        args = ldap_api.ChangePasswordRequest(new1="abc")
        await ldap_api.change_password("cn=test,o=Flintstones", args, connection)

        # Issued as an (async) extended operation, never the blocking helper.
        connection.extended.assert_called_once()
        oid, value = connection.extended.call_args.args
        self.assertEqual(oid, ldap_api.PASSWORD_MODIFY_OID)
        self.assertEqual(str(value["newPasswd"]), "abc")
        connection.extend.standard.modify_password.assert_not_called()

        # The response is awaited by polling, not by a blocking call.
        connection.get_response.assert_called_once_with(3, timeout=0)

    async def test_extended_sets_old_password(self):
        connection = MagicMock(name="Connection")
        connection.check_names = True
        connection.user = None
        connection.extended.return_value = 4
        connection.get_response.return_value = ([], {"result": 0})

        args = ldap_api.ChangePasswordRequest(old="secret", new1="new")
        await ldap_api.change_password("cn=test,o=Flintstones", args, connection)

        oid, value = connection.extended.call_args.args
        self.assertEqual(oid, ldap_api.PASSWORD_MODIFY_OID)
        self.assertEqual(str(value["oldPasswd"]), "secret")
        self.assertEqual(str(value["newPasswd"]), "new")


if __name__ == "__main__":
    unittest.main()
