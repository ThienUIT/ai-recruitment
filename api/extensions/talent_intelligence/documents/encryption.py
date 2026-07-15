"""Versioned AES-256-GCM envelopes for restricted CandidatePII values."""

import base64
import json
import os
from collections.abc import Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptionConfigurationError(ValueError):
    pass


class PIIEncryptionProvider:
    def __init__(self, keys: Mapping[str, bytes], active_version: str) -> None:
        if active_version not in keys:
            raise EncryptionConfigurationError("Active PII encryption key version is not configured.")
        if any(len(key) != 32 for key in keys.values()):
            raise EncryptionConfigurationError("Every PII encryption key must be exactly 32 bytes.")
        self._keys = dict(keys)
        self.active_version = active_version

    @classmethod
    def from_json(cls, keys_json: str, active_version: str) -> "PIIEncryptionProvider":
        try:
            encoded = json.loads(keys_json)
            if not isinstance(encoded, dict):
                raise TypeError
            keys = {str(version): base64.b64decode(str(value), validate=True) for version, value in encoded.items()}
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            raise EncryptionConfigurationError("PII encryption keys JSON is invalid.") from error
        return cls(keys, active_version)

    @staticmethod
    def aad(tenant_id: str, candidate_id: str, purpose: str, schema_version: str = "v1") -> bytes:
        return json.dumps(
            {
                "candidate_id": candidate_id,
                "purpose": purpose,
                "schema_version": schema_version,
                "tenant_id": tenant_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    def encrypt(self, plaintext: str, *, aad: bytes) -> str:
        nonce = os.urandom(12)
        ciphertext = AESGCM(self._keys[self.active_version]).encrypt(nonce, plaintext.encode(), aad)
        return json.dumps(
            {
                "alg": "A256GCM",
                "ciphertext": base64.b64encode(ciphertext).decode(),
                "key_version": self.active_version,
                "nonce": base64.b64encode(nonce).decode(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def decrypt(self, envelope: str, *, aad: bytes) -> str:
        value = json.loads(envelope)
        version = str(value["key_version"])
        key = self._keys.get(version)
        if key is None:
            raise EncryptionConfigurationError("PII encryption key version is unavailable.")
        nonce = base64.b64decode(value["nonce"], validate=True)
        ciphertext = base64.b64decode(value["ciphertext"], validate=True)
        return AESGCM(key).decrypt(nonce, ciphertext, aad).decode()
