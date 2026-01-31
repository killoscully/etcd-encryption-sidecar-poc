from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives import hashes, hmac, padding as sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.fernet import Fernet

try:
    import jwt  # PyJWT
except Exception:  # pragma: no cover
    jwt = None

try:
    from jwcrypto import jwk, jwe  # JWE support
except Exception:  # pragma: no cover
    jwk = None
    jwe = None


def b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8")


def b64d(s: str) -> bytes:
    padded = s + "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _to_bytes(x: str | bytes) -> bytes:
    return x if isinstance(x, (bytes, bytearray)) else x.encode("utf-8")


def _to_str(x: str | bytes) -> str:
    return x if isinstance(x, str) else x.decode("utf-8", errors="replace")


def load_key_material_from_env(env_name: str = "ENCRYPTION_KEY_DATA") -> bytes:
    """Load key material from env var.

    - If it's base64/base64url, decode it.
    - Otherwise treat as plain text.
    - If missing, generate random 32B (dev convenience).
    """
    raw = os.environ.get(env_name, "")
    if not raw:
        return os.urandom(32)

    try:
        return b64d(raw)
    except Exception:
        return raw.encode("utf-8")


@dataclass
class Envelope:
    v: int
    alg: str
    data: Dict[str, Any]

    def dumps(self) -> str:
        return json.dumps({"v": self.v, "alg": self.alg, "data": self.data}, separators=(",", ":"))

    @staticmethod
    def loads(s: str) -> Optional["Envelope"]:
        try:
            obj = json.loads(s)
            if not isinstance(obj, dict):
                return None
            if obj.get("v") != 1:
                return None
            alg = obj.get("alg")
            data = obj.get("data")
            if not isinstance(alg, str) or not isinstance(data, dict):
                return None
            return Envelope(v=1, alg=alg, data=data)
        except Exception:
            return None


class EncryptionPlugin:
    name: str

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        raise NotImplementedError

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        raise NotImplementedError


class AESGCMPlugin(EncryptionPlugin):
    name = "AES_GCM"

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        key = (key_material + b"\x00" * 32)[:32]
        nonce = os.urandom(12)
        ct = AESGCM(key).encrypt(nonce, _to_bytes(plaintext), None)
        return Envelope(1, self.name, {"nonce": b64e(nonce), "ct": b64e(ct)}).dumps()

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("not AES_GCM envelope")
        key = (key_material + b"\x00" * 32)[:32]
        nonce = b64d(env.data["nonce"])
        ct = b64d(env.data["ct"])
        pt = AESGCM(key).decrypt(nonce, ct, None)
        return _to_str(pt)


class ChaCha20Poly1305Plugin(EncryptionPlugin):
    name = "CHACHA20_POLY1305"

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        key = (key_material + b"\x00" * 32)[:32]
        nonce = os.urandom(12)
        ct = ChaCha20Poly1305(key).encrypt(nonce, _to_bytes(plaintext), None)
        return Envelope(1, self.name, {"nonce": b64e(nonce), "ct": b64e(ct)}).dumps()

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("not CHACHA20_POLY1305 envelope")
        key = (key_material + b"\x00" * 32)[:32]
        nonce = b64d(env.data["nonce"])
        ct = b64d(env.data["ct"])
        pt = ChaCha20Poly1305(key).decrypt(nonce, ct, None)
        return _to_str(pt)


class AESCBC_HMACPlugin(EncryptionPlugin):
    name = "AES_CBC_HMAC"

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        km = (key_material + b"\x00" * 64)[:64]
        enc_key = km[:32]
        mac_key = km[32:]
        iv = os.urandom(16)

        padder = sym_padding.PKCS7(128).padder()
        padded = padder.update(_to_bytes(plaintext)) + padder.finalize()

        cipher = Cipher(algorithms.AES(enc_key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ct = encryptor.update(padded) + encryptor.finalize()

        h = hmac.HMAC(mac_key, hashes.SHA256())
        h.update(iv + ct)
        tag = h.finalize()

        return Envelope(1, self.name, {"iv": b64e(iv), "ct": b64e(ct), "tag": b64e(tag)}).dumps()

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("not AES_CBC_HMAC envelope")
        km = (key_material + b"\x00" * 64)[:64]
        enc_key = km[:32]
        mac_key = km[32:]
        iv = b64d(env.data["iv"])
        ct = b64d(env.data["ct"])
        tag = b64d(env.data["tag"])

        h = hmac.HMAC(mac_key, hashes.SHA256())
        h.update(iv + ct)
        h.verify(tag)

        cipher = Cipher(algorithms.AES(enc_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ct) + decryptor.finalize()

        unpadder = sym_padding.PKCS7(128).unpadder()
        pt = unpadder.update(padded) + unpadder.finalize()
        return _to_str(pt)


class FernetPlugin(EncryptionPlugin):
    name = "FERNET"

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        key32 = (key_material + b"\x00" * 32)[:32]
        fkey = base64.urlsafe_b64encode(key32)
        token = Fernet(fkey).encrypt(_to_bytes(plaintext))
        return Envelope(1, self.name, {"token": _to_str(token)}).dumps()

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("not FERNET envelope")
        key32 = (key_material + b"\x00" * 32)[:32]
        fkey = base64.urlsafe_b64encode(key32)
        pt = Fernet(fkey).decrypt(_to_bytes(env.data["token"]))
        return _to_str(pt)


class JWTSignedPlugin(EncryptionPlugin):
    name = "JWT_SIGNED"

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        if jwt is None:
            raise ValueError("PyJWT not installed")
        token = jwt.encode({"v": plaintext}, key_material, algorithm="HS256")
        return Envelope(1, self.name, {"token": token}).dumps()

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        if jwt is None:
            raise ValueError("PyJWT not installed")
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("not JWT_SIGNED envelope")
        obj = jwt.decode(env.data["token"], key_material, algorithms=["HS256"])
        return _to_str(obj.get("v", ""))


class JWTEncryptedPlugin(EncryptionPlugin):
    name = "JWT_ENCRYPTED"

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        if jwk is None or jwe is None:
            raise ValueError("jwcrypto not installed")
        k = jwk.JWK(kty="oct", k=b64e((key_material + b"\x00" * 32)[:32]))
        protected = {"alg": "dir", "enc": "A256GCM"}
        token = jwe.JWE(_to_bytes(plaintext), protected=protected)
        token.add_recipient(k)
        return Envelope(1, self.name, {"token": token.serialize(compact=True)}).dumps()

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        if jwk is None or jwe is None:
            raise ValueError("jwcrypto not installed")
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("not JWT_ENCRYPTED envelope")
        k = jwk.JWK(kty="oct", k=b64e((key_material + b"\x00" * 32)[:32]))
        token = jwe.JWE()
        token.deserialize(env.data["token"])
        token.decrypt(k)
        return _to_str(token.payload)


class EncryptionPluginManager:
    def __init__(self) -> None:
        self._plugins: Dict[str, EncryptionPlugin] = {}

    def register(self, plugin: EncryptionPlugin) -> None:
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> EncryptionPlugin:
        n = (name or "").strip().upper()
        return self._plugins.get(n, self._plugins["AES_GCM"])


def default_manager() -> EncryptionPluginManager:
    m = EncryptionPluginManager()
    m.register(AESGCMPlugin())
    m.register(ChaCha20Poly1305Plugin())
    m.register(AESCBC_HMACPlugin())
    m.register(FernetPlugin())
    m.register(JWTSignedPlugin())
    m.register(JWTEncryptedPlugin())
    return m


def try_decrypt_any(value: str, key_material: bytes, manager: EncryptionPluginManager) -> str:
    env = Envelope.loads(value)
    if not env:
        return value
    plugin = manager.get(env.alg)
    return plugin.decrypt(value, key_material)
