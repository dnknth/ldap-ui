import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ldap3.core.exceptions import LDAPInvalidCredentialsResult
from ldap_ui import ldap_connection, settings


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
            await ldap_connection.ldap_connect()

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


class BoundTest(unittest.IsolatedAsyncioTestCase):
    """`bound()` must bind with the given DN/password, always unbind on exit,
    and rate-limit invalid credentials."""

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


if __name__ == "__main__":
    unittest.main()
