"""Fail-closed bridge helpers for Midnight proof-of-permission operations.

This module deliberately knows nothing about PDF text or LLM context.  The only
application data allowed across the bridge boundary are domain-separated
32-byte digests.  A successful HTTP response is not enough: transaction
receipts must describe a finalized, indexed Midnight state transition.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

DOCUMENT_DIGEST_DOMAIN = b"privatedocs:document-digest:v1\x00"
QUERY_DIGEST_DOMAIN = b"privatedocs:query-digest:v1\x00"
DEFAULT_BRIDGE_URL = "http://127.0.0.1:8787"
MAX_BRIDGE_RESPONSE_BYTES = 64 * 1024

_HEX_32 = re.compile(r"^[0-9a-f]{64}$")
_CHAIN_ID = re.compile(r"^[0-9a-f]{64,}$")


class PrivacyError(RuntimeError):
    """Base class for privacy-gate failures."""


class BridgeConfigurationError(PrivacyError):
    """The bridge configuration would be unsafe or is malformed."""


class BridgeUnavailableError(PrivacyError):
    """The real Midnight bridge could not be reached."""


class ProofVerificationError(PrivacyError):
    """The bridge did not return a verifiable finalized state transition."""


class PermissionStateError(PrivacyError):
    """The local UI state does not permit the requested transition."""


class PermissionPhase(StrEnum):
    UPLOADED = "uploaded"
    REGISTERED = "registered"
    AUTHORIZED = "authorized"
    CONSUMED = "consumed"
    REVOKED = "revoked"


def canonicalize_question(question: str) -> str:
    """Return the exact canonical question whose digest is authorized.

    NFC normalization avoids platform-specific Unicode encodings while keeping
    case, internal whitespace, and punctuation significant.
    """

    if not isinstance(question, str):
        raise TypeError("Question must be text.")
    canonical = unicodedata.normalize("NFC", question).strip()
    if not canonical:
        raise ValueError("Question cannot be empty.")
    return canonical


def document_digest(pdf_bytes: bytes) -> str:
    """Create the versioned SHA-256 digest sent to the local Midnight bridge."""

    if not isinstance(pdf_bytes, bytes):
        raise TypeError("Document content must be bytes.")
    if not pdf_bytes:
        raise ValueError("Document content cannot be empty.")
    return hashlib.sha256(DOCUMENT_DIGEST_DOMAIN + pdf_bytes).hexdigest()


def query_digest(question: str) -> str:
    """Create the versioned SHA-256 digest for the canonical exact question."""

    canonical = canonicalize_question(question)
    return hashlib.sha256(QUERY_DIGEST_DOMAIN + canonical.encode("utf-8")).hexdigest()


def _require_hex_32(value: str, field_name: str) -> str:
    normalized = value.lower()
    if not _HEX_32.fullmatch(normalized):
        raise ProofVerificationError(f"{field_name} must be a 32-byte lowercase hex value.")
    return normalized


def _pick(payload: Mapping[str, Any], snake: str, camel: str) -> Any:
    return payload.get(snake, payload.get(camel))


@dataclass(frozen=True)
class MidnightReceipt:
    operation: str
    network: str
    contract_address: str
    tx_id: str
    block_height: int
    document_commitment: str | None = None
    authorization_commitment: str | None = None
    nullifier: str | None = None
    ledger_verified: bool = True

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any], operation: str) -> MidnightReceipt:
        if payload.get("ok") is not True:
            raise ProofVerificationError("Midnight operation was not confirmed.")
        if payload.get("simulated") is True or payload.get("mode") in {"mock", "simulation", "demo"}:
            raise ProofVerificationError("Simulated proof responses are never accepted.")
        if payload.get("status") != "finalized":
            raise ProofVerificationError("Midnight transaction is not finalized.")
        if payload.get("ledgerVerified") is not True and payload.get("ledger_verified") is not True:
            raise ProofVerificationError("Finalized state was not verified through the indexer.")

        network = str(payload.get("network", ""))
        if network not in {"undeployed", "local", "preview", "preprod", "mainnet"}:
            raise ProofVerificationError("Bridge returned an unknown Midnight network.")

        contract_address = str(_pick(payload, "contract_address", "contractAddress") or "").lower()
        tx_id = str(_pick(payload, "tx_id", "txId") or "").lower()
        if not _CHAIN_ID.fullmatch(contract_address):
            raise ProofVerificationError("Bridge returned an invalid contract address.")
        if not _CHAIN_ID.fullmatch(tx_id):
            raise ProofVerificationError("Bridge returned an invalid transaction identifier.")

        block_height = _pick(payload, "block_height", "blockHeight")
        if not isinstance(block_height, int) or isinstance(block_height, bool) or block_height <= 0:
            raise ProofVerificationError("Bridge returned an invalid finalized block height.")

        values: dict[str, str | None] = {}
        for snake, camel in (
            ("document_commitment", "documentCommitment"),
            ("authorization_commitment", "authorizationCommitment"),
            ("nullifier", "nullifier"),
        ):
            raw = _pick(payload, snake, camel)
            values[snake] = None if raw is None else _require_hex_32(str(raw), snake)

        return cls(
            operation=operation,
            network=network,
            contract_address=contract_address,
            tx_id=tx_id,
            block_height=block_height,
            ledger_verified=True,
            **values,
        )


class MidnightBridgeClient:
    """Small JSON client for a loopback-only, real Midnight TypeScript service."""

    def __init__(self, base_url: str | None = None, *, timeout_seconds: float = 120.0):
        configured_url = (
            base_url
            or os.getenv("PRIVATEDOCS_MIDNIGHT_BRIDGE_URL")
            or DEFAULT_BRIDGE_URL
        )
        self.base_url = configured_url.rstrip("/") + "/"
        self.timeout_seconds = timeout_seconds
        self._validate_base_url()

    def _validate_base_url(self) -> None:
        parsed = urlparse(self.base_url)
        allow_remote = os.getenv("PRIVATEDOCS_ALLOW_REMOTE_BRIDGE") == "1"
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise BridgeConfigurationError("Midnight bridge URL must be an HTTP(S) URL.")
        if not allow_remote and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise BridgeConfigurationError(
                "Midnight bridge must use loopback unless "
                "PRIVATEDOCS_ALLOW_REMOTE_BRIDGE=1 is explicitly set."
            )
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise BridgeConfigurationError(
                "Midnight bridge URL cannot contain credentials, a query, or a fragment."
            )

    def _request(self, path: str, payload: Mapping[str, str] | None = None) -> Mapping[str, Any]:
        body = (
            None
            if payload is None
            else json.dumps(dict(payload), separators=(",", ":")).encode("utf-8")
        )
        request = Request(  # noqa: S310 - base URL permits only validated HTTP(S).
            urljoin(self.base_url, path.lstrip("/")),
            data=body,
            method="GET" if payload is None else "POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - URL is validated above.
                declared_length = response.headers.get("Content-Length")
                if declared_length and int(declared_length) > MAX_BRIDGE_RESPONSE_BYTES:
                    raise ProofVerificationError("Midnight bridge response is unexpectedly large.")
                raw = response.read(MAX_BRIDGE_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise BridgeUnavailableError(f"Midnight bridge rejected the request (HTTP {exc.code}).") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise BridgeUnavailableError(
                "Real Midnight bridge is unavailable; AI access remains blocked."
            ) from exc

        if len(raw) > MAX_BRIDGE_RESPONSE_BYTES:
            raise ProofVerificationError("Midnight bridge response is unexpectedly large.")
        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProofVerificationError("Midnight bridge returned invalid JSON.") from exc
        if not isinstance(decoded, dict):
            raise ProofVerificationError("Midnight bridge returned an invalid response object.")
        return decoded

    def health(self) -> Mapping[str, Any]:
        payload = self._request("health")
        if payload.get("ok") is not True or payload.get("midnightReady") is not True:
            raise BridgeUnavailableError("Midnight provider stack is not ready.")
        if payload.get("simulated") is True:
            raise ProofVerificationError("Simulated bridge mode is not supported.")
        return payload

    def _transition(self, operation: str, document: str, question: str | None = None) -> MidnightReceipt:
        request_payload = {"documentDigest": _require_hex_32(document, "document_digest")}
        if question is not None:
            request_payload["queryDigest"] = _require_hex_32(question, "query_digest")
        response = self._request(operation, request_payload)
        return MidnightReceipt.from_payload(response, operation)

    def register_document(self, document: str) -> MidnightReceipt:
        return self._transition("register", document)

    def authorize_query(self, document: str, question: str) -> MidnightReceipt:
        return self._transition("authorize", document, question)

    def consume_query(self, document: str, question: str) -> MidnightReceipt:
        return self._transition("consume", document, question)

    def revoke_document(self, document: str) -> MidnightReceipt:
        return self._transition("revoke", document)


@dataclass
class PermissionState:
    """UI-side mirror of verified chain transitions; never an authority itself."""

    document_digest: str
    phase: PermissionPhase = PermissionPhase.UPLOADED
    authorized_query_digest: str | None = None
    receipts: list[MidnightReceipt] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.document_digest = _require_hex_32(self.document_digest, "document_digest")

    def record_registration(self, receipt: MidnightReceipt) -> None:
        if self.phase is not PermissionPhase.UPLOADED or receipt.operation != "register":
            raise PermissionStateError("Document registration is not valid in the current state.")
        self.receipts.append(receipt)
        self.phase = PermissionPhase.REGISTERED

    def record_authorization(self, question: str, receipt: MidnightReceipt) -> None:
        if self.phase not in {PermissionPhase.REGISTERED, PermissionPhase.CONSUMED}:
            raise PermissionStateError("Query authorization is not valid in the current state.")
        if receipt.operation != "authorize" or not receipt.authorization_commitment:
            raise PermissionStateError("Authorization receipt is incomplete.")
        self.authorized_query_digest = _require_hex_32(question, "query_digest")
        self.receipts.append(receipt)
        self.phase = PermissionPhase.AUTHORIZED

    def require_authorized(self, question: str) -> None:
        digest = _require_hex_32(question, "query_digest")
        if self.phase is PermissionPhase.REVOKED:
            raise PermissionStateError("Document permission has been revoked.")
        if self.phase is not PermissionPhase.AUTHORIZED or self.authorized_query_digest != digest:
            raise PermissionStateError("This exact document query has no active authorization.")

    def record_consumption(self, question: str, receipt: MidnightReceipt) -> None:
        self.require_authorized(question)
        if receipt.operation != "consume" or not receipt.nullifier:
            raise PermissionStateError("Consumption receipt is incomplete.")
        self.receipts.append(receipt)
        self.phase = PermissionPhase.CONSUMED
        self.authorized_query_digest = None

    def record_revocation(self, receipt: MidnightReceipt) -> None:
        if self.phase is PermissionPhase.UPLOADED or self.phase is PermissionPhase.REVOKED:
            raise PermissionStateError("Document revocation is not valid in the current state.")
        if receipt.operation != "revoke":
            raise PermissionStateError("Revocation receipt is invalid.")
        self.receipts.append(receipt)
        self.phase = PermissionPhase.REVOKED
        self.authorized_query_digest = None
