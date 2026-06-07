import unittest
from unittest.mock import MagicMock, patch

from ldap_ui import ldap_api, settings


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
            getattr(connection, op).side_effect = (
                lambda *args, _op=op, **kwargs: order.append(_op)
            )

        # Pin BASE_DN/SCHEMA_DN so the root DSE auto-detection is skipped and
        # the test stays focused on the connection setup sequence.
        with (
            patch.object(ldap_api, "Server"),
            patch.object(ldap_api, "Connection", return_value=connection),
            patch.object(settings, "LDAP_URL", ldap_url),
            patch.object(settings, "USE_TLS", True),
            patch.object(settings, "BASE_DN", "o=Flintstones"),
            patch.object(settings, "SCHEMA_DN", "cn=Subschema"),
        ):
            await ldap_api.ldap_connect()

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


if __name__ == "__main__":
    unittest.main()
