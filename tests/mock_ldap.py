"""In-process ldap3 mock directory for the backend test suite.

Replaces the Docker-hosted ``dnknth/ldap-demo`` slapd container with an
in-memory directory backed by the ldap3 ``MockAsyncStrategy``. The directory
is loaded from ``demo-ldap/flintstones.ldif`` (the export the Docker image
ships) and each entry is enriched with the ``structuralObjectClass``
operational attribute, derived from the bundled OpenLDAP 2.4 schema the way a
real server would report it.

Every connection created through ``ldap_connection.open()`` is routed to a
shared :class:`Server` whose DIT holds the fixture entries plus a
``cn=Subschema`` entry built from the bundled OpenLDAP 2.4 schema, so the
app's ``get_schema`` probe resolves a full schema with no server round-trip.

The shared directory is rebuilt from scratch by each test class
(``mock_ldap.reset()`` in ``setUpClass``), so consecutive test classes get a
predictable directory and modifications never leak across classes.
"""

import json
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

import ldap3.core.connection as _ldap3_connection
from ldap3 import MOCK_ASYNC, Server
from ldap3.core.connection import Connection
from ldap3.core.exceptions import LDAPOperationResult
from ldap3.core.results import DO_NOT_RAISE_EXCEPTIONS
from ldap3.operation.add import add_response_to_dict
from ldap3.operation.bind import bind_response_to_dict
from ldap3.operation.compare import compare_response_to_dict
from ldap3.operation.delete import delete_response_to_dict
from ldap3.operation.extended import extended_request_to_dict, extended_response_to_dict
from ldap3.operation.modify import modify_response_to_dict
from ldap3.operation.modifyDn import modify_dn_response_to_dict
from ldap3.operation.search import search_request_to_dict
from ldap3.protocol.rfc3062 import PasswdModifyRequestValue
from ldap3.protocol.rfc4512 import DsaInfo
from ldap3.strategy.mockAsync import MockAsyncStrategy
from ldap3.utils.conv import to_raw, to_unicode
from ldap3.utils.dn import safe_dn
from ldif import LDIFParser
from pyasn1.codec.ber import decoder

_LDIF_PATH = Path(__file__).resolve().parent.parent / "demo-ldap" / "flintstones.ldif"

# The naming context is derived from the fixture below (the first LDIF entry's
# DN, ``o=Flintstones``).
SCHEMA_DN = "cn=Subschema"
PASSWORD_MODIFY_OID = "1.3.6.1.4.1.4203.1.11.1"

_lock = threading.RLock()

# The stock strategy, captured before any swap. The connection factory
# resolves ``MockAsyncStrategy`` from the ``ldap3.core.connection`` namespace
# at construction time, so the swap can be scoped around construction instead
# of applied process-wide at import.
_STOCK_STRATEGY = _ldap3_connection.MockAsyncStrategy  # type: ignore[attr-defined]


def _make_connection(
    server: Server,
    bind_dn: str | None = None,
    bind_password: str | None = None,
) -> Connection:
    """Open a connection to the mock directory.

    Installs :class:`MockLdapStrategy` for the duration of the construction
    only, so other users of ``MOCK_ASYNC`` in the same process keep the stock
    behavior.
    """
    with _lock:
        _ldap3_connection.MockAsyncStrategy = MockLdapStrategy  # type: ignore[attr-defined]
        try:
            return Connection(
                server,
                user=bind_dn,
                password=bind_password,
                client_strategy=MOCK_ASYNC,
                raise_exceptions=True,
            )
        finally:
            _ldap3_connection.MockAsyncStrategy = _STOCK_STRATEGY  # type: ignore[attr-defined]


class _Directory:
    """Holder for the shared Server, rebuilt per test class."""

    server: Server | None = None


def reset(ldap_url: str = "ldap://127.0.0.1:389") -> None:
    """Rebuild the shared directory from scratch (per test class)."""
    with _lock:
        _Directory.server = build_server(ldap_url)


def connect(
    ldap_url: str = "ldap://127.0.0.1:389",
    bind_dn: str | None = None,
    bind_password: str | None = None,
) -> Connection:
    """Open a mock connection to the shared directory."""
    with _lock:
        if _Directory.server is None:
            _Directory.server = build_server(ldap_url)
        server = _Directory.server
    return _make_connection(server, bind_dn, bind_password)


def mock_open(
    ldap_url: str,
    get_info=None,
    bind_dn: str | None = None,
    bind_password: str | None = None,
) -> Connection:
    """Drop-in for ``ldap_connection.open``: the app's connection factory."""
    return connect(ldap_url, bind_dn, bind_password)


def build_server(ldap_url: str) -> Server:
    """Build a Server preloaded with the DIT and the DSA/schema info."""
    from ldap3.protocol.rfc4512 import SchemaInfo
    from ldap3.protocol.schemas.slapd24 import slapd_2_4_schema

    server = Server(ldap_url)

    # Attach the DSA info: ldap_connect() reads namingContexts and the schema
    # subentry from server.info when resolving settings.BASE_DN/SCHEMA_DN.
    server.attach_dsa_info(
        DsaInfo(
            {
                "namingContexts": [BASE_DN],
                "subschemaSubentry": [SCHEMA_DN],
                "supportedExtension": [PASSWORD_MODIFY_OID],
            },
            {
                "namingContexts": [to_raw(BASE_DN)],
                "subschemaSubentry": [to_raw(SCHEMA_DN)],
                "supportedExtension": [to_raw(PASSWORD_MODIFY_OID)],
            },
        )
    )

    # Creating a connection instantiates the mock strategy, which attaches a
    # CaseInsensitiveDict DIT to the server; every later connection shares it.
    connection = _make_connection(server)
    strategy = connection.strategy
    for dn, attributes in fixture_entries():
        strategy.add_entry(dn, attributes, validate=False)
    strategy.add_entry(SCHEMA_DN, schema_attributes(), validate=False)

    # Attach the schema info AFTER populating the DIT: add_entry validates
    # object classes against it (inetLocalMailRecipient isn't in the bundled
    # set) and expands the objectClass hierarchy when a schema is present.
    # Searches can then resolve filter aliases like gn -> givenName through
    # server.schema, as a real directory does.
    server.attach_schema_info(SchemaInfo.from_json(slapd_2_4_schema))
    return server


def schema_attributes() -> dict[str, list[str]]:
    """The ``cn=Subschema`` entry contents from the bundled OpenLDAP schema."""
    from ldap3.protocol.schemas.slapd24 import slapd_2_4_schema

    return json.loads(slapd_2_4_schema)["raw"]


class MockLdapStrategy(MockAsyncStrategy):
    """MockAsyncStrategy with response shapes the application expects.

    Adjustments over the stock strategy, each mirroring a real server:

    - ``post_send_single_response`` stores an empty entry list. The app's
      ``empty()``/``get_raw_responses()`` treat the stored response entries as
      search results; the stock mock stores the bare result dict, which the
      API would hand to ``ResponseEntry.of()``.
    - ``mock_search`` expands operational-attribute searches (``'+'``) to the
      entry's full attribute list (the stock mock returns ``entryDN`` only),
      computes ``hasSubordinates``, and excludes the base entry from
      ``singleLevel`` results. Filter aliases (``gn`` -> ``givenName``) are
      resolved through the server's schema, like a real directory.
    - ``add_entry`` hides the attached schema while adding: ldap3 would expand
      the objectClass hierarchy and reject classes outside the bundled schema.
    - ``mock_extended`` implements the password-modify operation against the
      shared DIT; ``mock_add`` reports conflicts with slapd's empty message.
    """

    _responses: dict[int, tuple[Any, Any, list[Any]]]

    def post_send_single_response(self, payload):
        message_id, message_type, request, controls = payload
        result = None
        match message_type:
            case "unbindRequest":
                self.bound = None
            case "abandonRequest":
                pass
            case "bindRequest":
                result = bind_response_to_dict(self.mock_bind(request, controls))
                result["type"] = "bindResponse"
            case "delRequest":
                result = delete_response_to_dict(self.mock_delete(request, controls))
                result["type"] = "delResponse"
            case "addRequest":
                result = add_response_to_dict(self.mock_add(request, controls))
                result["type"] = "addResponse"
            case "compareRequest":
                result = compare_response_to_dict(self.mock_compare(request, controls))
                result["type"] = "compareResponse"
            case "modDNRequest":
                result = modify_dn_response_to_dict(self.mock_modify_dn(request, controls))
                result["type"] = "modDNResponse"
            case "modifyRequest":
                result = modify_response_to_dict(self.mock_modify(request, controls))
                result["type"] = "modifyResponse"
            case "extendedReq":
                result = extended_response_to_dict(self.mock_extended(request, controls))
                result["type"] = "extendedResp"
        if self.connection.raise_exceptions and result and result["result"] not in DO_NOT_RAISE_EXCEPTIONS:
            raise LDAPOperationResult(
                result=result["result"],
                description=result["description"],
                dn=result["dn"],
                message=result["message"],
                response_type=result["type"],
            )
        self._responses[message_id] = (request, result, [])
        return message_id

    def mock_search(self, request_message, controls):
        request = search_request_to_dict(request_message)
        if controls:
            # The app never sends search controls (no paging/size limits), so
            # the overrides below assume the control-less path. If it ever
            # does, extend the overrides to cover the paged path too.
            return super().mock_search(request_message, controls)
        # Snapshot before _execute_search: it mutates the attribute list in
        # place (expanding '+'), so a later '+' check would miss it.
        requested = list(request["attributes"])
        request["filter"] = self._translate_filter(request["filter"])
        responses, result = self._execute_search(request)  # type: ignore[attr-defined]
        if "+" in requested:
            # Operational-attribute request: return every attribute the entry
            # carries (user attributes + operational), as a real server does.
            for entry in responses:
                dn = entry["object"]
                attributes = [
                    {"type": attr, "vals": self.connection.server.dit[dn][attr]}
                    for attr in self.connection.server.dit[dn]
                ]
                attributes.append(
                    {
                        "type": "hasSubordinates",
                        "vals": [b"TRUE" if self._has_subordinates(dn) else b"FALSE"],
                    }
                )
                entry["attributes"] = attributes
        if request["scope"] == 1:
            # singleLevel excludes the base entry itself (the stock mock
            # includes it, which would make the tree list a node as its own
            # child).
            base = safe_dn(request["base"])
            responses = [entry for entry in responses if entry["object"] != base]
        return responses, result

    def _has_subordinates(self, dn: str) -> bool:
        dl = f",{dn.lower()}"
        return any(
            candidate != dn and candidate.lower().endswith(dl)
            for candidate in self.connection.server.dit
        )

    def _canonical_attribute(self, attribute: str) -> str:
        """Resolve a filter attribute to its canonical name via the schema.

        Real directories resolve alias names (``gn`` -> ``givenName``) through
        the schema; the mock matches the filter attribute name verbatim against
        DIT keys, so aliases must be rewritten before matching.
        """
        schema = self.connection.server.schema
        if schema is not None and schema.attribute_types:
            info = schema.attribute_types.get(attribute)
            if info is not None and info.name:
                canonical = info.name[0]
                if canonical.lower() != attribute.lower():
                    return canonical
        return attribute

    def _translate_filter(self, search_filter: str) -> str:
        """Rewrite filter attribute aliases to the DIT attribute names."""
        return re.sub(
            r"(?<=\()\w+(?=[=><~:])",
            lambda match: self._canonical_attribute(match.group(0)),
            search_filter,
            flags=re.IGNORECASE,
        )

    def add_entry(self, dn, attributes, validate=True):
        # The schema is attached for search-time alias resolution only. With it
        # present, ldap3 expands the objectClass hierarchy and rejects classes
        # outside the bundled set (inetLocalMailRecipient), whereas a real
        # server stores objectClass as sent. Temporarily hide the schema so
        # seeding and runtime additions behave like one.
        schema = self.connection.server._schema_info
        if schema is not None:
            self.connection.server._schema_info = None
            try:
                return super().add_entry(dn, attributes, validate)
            finally:
                self.connection.server._schema_info = schema
        return super().add_entry(dn, attributes, validate)

    def mock_add(self, request_message, controls):
        result = super().mock_add(request_message, controls)
        if result["resultCode"] == 68:  # entryAlreadyExists
            # The real server reports conflicts with an empty message; the
            # app's error handler turns the description into the detail text.
            result["diagnosticMessage"] = ""
        return result

    def mock_extended(self, request_message, controls):
        request = extended_request_to_dict(request_message)
        if request["name"] == PASSWORD_MODIFY_OID and request["value"]:
            (decoded, _) = decoder.decode(request["value"], asn1Spec=PasswdModifyRequestValue())
            identity = str(decoded["userIdentity"]) if decoded["userIdentity"].hasValue() else None
            old = str(decoded["oldPasswd"]) if decoded["oldPasswd"].hasValue() else None
            new = str(decoded["newPasswd"]) if decoded["newPasswd"].hasValue() else None
            if not identity or identity not in self.connection.server.dit:
                result = 32  # noSuchObject
                message = "object not found"
            elif old is not None and not self.equal(identity, "userPassword", old):
                result = 49  # invalidCredentials
                message = "invalid credentials"
            else:
                if new:
                    self.connection.server.dit[identity]["userPassword"] = [to_raw(new)]
                else:
                    self.connection.server.dit[identity].pop("userPassword", None)
                result = 0
                message = ""
            return {
                "resultCode": result,
                "matchedDN": "",
                "diagnosticMessage": to_unicode(message, "utf-8"),
                "referral": None,
                "responseName": None,
                "responseValue": None,
            }
        return super().mock_extended(request_message, controls)


# ---------------------------------------------------------------------------
# Fixture: demo-ldap/flintstones.ldif plus structuralObjectClass.
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _ldif_records() -> list[tuple[str, dict[str, list[str]]]]:
    """The demo directory, parsed once from ``demo-ldap/flintstones.ldif``."""
    records: list[tuple[str, dict[str, list[str]]]] = []
    with _LDIF_PATH.open("rb") as fh:
        for dn, attributes in LDIFParser(fh).parse():
            assert dn is not None
            entry_attrs: dict[str, list[str]] = {}
            for attr, vals in attributes.items():
                if not isinstance(attr, str):
                    continue
                entry_attrs[attr] = list(vals)
            records.append((dn, entry_attrs))
    return records


def _base_dn() -> str:
    """The naming context of the demo directory.

    LDIF exports list the root (suffix) entry first, so the first record's DN
    is the base the whole export hangs off.
    """
    return _ldif_records()[0][0]


# The naming context of the demo directory (``o=Flintstones``), from the LDIF.
BASE_DN = _base_dn()


@lru_cache(maxsize=1)
def _object_class_kinds() -> dict[str, str]:
    """Map object class names to their schema kind (STRUCTURAL/...)."""
    from ldap3.protocol.schemas.slapd24 import slapd_2_4_schema

    kinds: dict[str, str] = {}
    for raw in json.loads(slapd_2_4_schema)["raw"]["objectClasses"]:
        name = re.search(r"NAME\s*'([^']*)'", raw)
        kind = re.search(r"\b(STRUCTURAL|AUXILIARY|ABSTRACT)\b", raw)
        if name and kind:
            kinds[name.group(1).lower()] = kind.group(1)
    return kinds


def _structural_class(object_classes: list[str]) -> str:
    """The entry's structural object class, or its own first class.

    Real servers report ``structuralObjectClass`` for every entry. It is the
    schema's structural class among the entry's object classes; entries that
    carry none (here only ``posixGroup``) get the first class they do carry.
    """
    kinds = _object_class_kinds()
    for name in object_classes:
        if kinds.get(name.lower()) == "STRUCTURAL":
            return name
    return object_classes[0]


def fixture_entries() -> list[tuple[str, dict[str, list[str]]]]:
    """The demo directory entries with ``structuralObjectClass`` added.

    Returns fresh copies every call so the shared directory's mutations
    (modify/delete/password ops) never leak across test classes.
    """
    entries = []
    for dn, attrs in _ldif_records():
        attrs = dict(attrs)
        attrs["structuralObjectClass"] = [
            _structural_class(list(attrs["objectClass"]))
        ]
        entries.append((dn, attrs))
    return entries