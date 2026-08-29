from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch
from urllib.error import URLError

from utils.privacy import (
    BridgeConfigurationError,
    BridgeUnavailableError,
    MidnightBridgeClient,
    MidnightReceipt,
    PermissionPhase,
    PermissionState,
    PermissionStateError,
    ProofVerificationError,
    canonicalize_question,
    document_digest,
    query_digest,
)

HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
HEX_D = "d" * 64


def receipt(operation: str) -> MidnightReceipt:
    return MidnightReceipt(
        operation=operation,
        network="local",
        contract_address=HEX_A,
        tx_id=HEX_B,
        block_height=7,
        document_commitment=HEX_C,
        authorization_commitment=HEX_D if operation == "authorize" else None,
        nullifier=HEX_D if operation == "consume" else None,
    )


class PrivacyTests(unittest.TestCase):
    def test_domain_separated_digests_are_stable_and_distinct(self) -> None:
        self.assertEqual(document_digest(b"same"), document_digest(b"same"))
        self.assertEqual(query_digest("same"), query_digest("same"))
        self.assertNotEqual(document_digest(b"same"), query_digest("same"))
        self.assertEqual(canonicalize_question("  Caf\u00e9?  "), "Caf\u00e9?")

    def test_query_digest_preserves_exact_internal_text(self) -> None:
        self.assertNotEqual(query_digest("Salary?"), query_digest("salary?"))
        self.assertNotEqual(
            query_digest("annual  salary?"), query_digest("annual salary?")
        )

    def test_bridge_rejects_remote_url_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PRIVATEDOCS_ALLOW_REMOTE_BRIDGE", None)
            with self.assertRaises(BridgeConfigurationError):
                MidnightBridgeClient("https://example.com")

    def test_receipt_rejects_simulated_or_unverified_results(self) -> None:
        base = {
            "ok": True,
            "status": "finalized",
            "network": "local",
            "contractAddress": HEX_A,
            "txId": HEX_B,
            "blockHeight": 3,
            "ledgerVerified": True,
        }
        with self.assertRaisesRegex(ProofVerificationError, "Simulated"):
            MidnightReceipt.from_payload({**base, "simulated": True}, "register")
        with self.assertRaisesRegex(ProofVerificationError, "indexer"):
            MidnightReceipt.from_payload(
                {**base, "ledgerVerified": False}, "register"
            )

    def test_permission_state_blocks_wrong_query_replay_and_revocation(self) -> None:
        state = PermissionState(HEX_A)
        state.record_registration(receipt("register"))
        state.record_authorization(HEX_B, receipt("authorize"))

        with self.assertRaisesRegex(PermissionStateError, "exact"):
            state.require_authorized(HEX_C)

        state.record_consumption(HEX_B, receipt("consume"))
        self.assertIs(state.phase, PermissionPhase.CONSUMED)
        with self.assertRaisesRegex(PermissionStateError, "active"):
            state.require_authorized(HEX_B)

        state.record_authorization(HEX_B, receipt("authorize"))
        state.record_revocation(receipt("revoke"))
        self.assertIs(state.phase, PermissionPhase.REVOKED)
        with self.assertRaisesRegex(PermissionStateError, "revoked"):
            state.require_authorized(HEX_B)

    def test_bridge_sends_only_digests(self) -> None:
        captured: dict[str, object] = {}

        class FakeHeaders:
            def get(self, _name: str):
                return None

        class FakeResponse:
            headers = FakeHeaders()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self, _limit: int) -> bytes:
                return json.dumps(
                    {
                        "ok": True,
                        "status": "finalized",
                        "network": "local",
                        "contractAddress": HEX_A,
                        "txId": HEX_B,
                        "blockHeight": 4,
                        "ledgerVerified": True,
                        "authorizationCommitment": HEX_C,
                    }
                ).encode()

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data)
            captured["timeout"] = timeout
            return FakeResponse()

        with patch("utils.privacy.urlopen", fake_urlopen):
            result = MidnightBridgeClient(timeout_seconds=2).authorize_query(
                HEX_A, HEX_B
            )
        self.assertEqual(result.authorization_commitment, HEX_C)
        self.assertEqual(
            captured["body"],
            {"documentDigest": HEX_A, "queryDigest": HEX_B},
        )

    def test_bridge_fails_closed_when_unavailable(self) -> None:
        def fail(*_args, **_kwargs):
            raise URLError("offline")

        with (
            patch("utils.privacy.urlopen", fail),
            self.assertRaisesRegex(BridgeUnavailableError, "blocked"),
        ):
            MidnightBridgeClient().register_document(HEX_A)


if __name__ == "__main__":
    unittest.main()
