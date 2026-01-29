# /app/encryption_plugin_system.py
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, hmac, serialization, padding as sym_padding
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.fernet import Fernet

# Optional deps for token modes
try:
    import jwt  # PyJWT
except Exception:  # pragma: no cover
    jwt = None

try:
    from jwcrypto import jwk, jwe  # JWE support
except Exception:  # pragma: no cover
    jwk = None
    jwe = None


# ----------------------------
# Helpers
# ----------------------------
def b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8")


def b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s.encode("utf-8"))


def _to_bytes(data: str | bytes) -> bytes:
    if isinstance(data, bytes):
        return data
    return data.encode("utf-8")


def _to_str(data: str | bytes) -> str:
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="replace")


def load_key_material_from_env(env_name: str = "ENCRYPTION_KEY_DATA") -> bytes:
    """
    Load key material from an env var.

    - If value looks like base64url/base64, decode it.
    - Else use UTF-8 bytes.
    """
    raw = os.environ.get(env_name, "")
    if not raw:
        # fallback to random (dev convenience). For real thesis tests, provide a Secret.
        return os.urandom(32)

    # Try base64url decode first; if fails, treat as plain text.
    try:
        # Pad for base64 if needed
        padded = raw + "=" * (-len(raw) % 4)
        return base64.urlsafe_b64decode(padded.encode("utf-8"))
    except Exception:
        return raw.encode("utf-8")


# ----------------------------
# Envelope format
# ----------------------------
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


# ----------------------------
# Plugin base
# ----------------------------
class EncryptionPlugin:
    name: str

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        raise NotImplementedError

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        raise NotImplementedError


# ----------------------------
# Symmetric AEAD plugins
# ----------------------------
class AESGCMPlugin(EncryptionPlugin):
    name = "AES_GCM"

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        key = (key_material + b"\x00" * 32)[:32]  # force 32 bytes
        nonce = os.urandom(12)
        aead = AESGCM(key)
        ct = aead.encrypt(nonce, _to_bytes(plaintext), associated_data=None)
        env = Envelope(1, self.name, {"nonce": b64e(nonce), "ct": b64e(ct)})
        return env.dumps()

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("ciphertext not in AES_GCM envelope")
        key = (key_material + b"\x00" * 32)[:32]
        nonce = b64d(env.data["nonce"])
        ct = b64d(env.data["ct"])
        aead = AESGCM(key)
        pt = aead.decrypt(nonce, ct, associated_data=None)
        return _to_str(pt)


class ChaCha20Poly1305Plugin(EncryptionPlugin):
    name = "CHACHA20_POLY1305"

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        key = (key_material + b"\x00" * 32)[:32]
        nonce = os.urandom(12)
        aead = ChaCha20Poly1305(key)
        ct = aead.encrypt(nonce, _to_bytes(plaintext), associated_data=None)
        env = Envelope(1, self.name, {"nonce": b64e(nonce), "ct": b64e(ct)})
        return env.dumps()

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("ciphertext not in CHACHA20_POLY1305 envelope")
        key = (key_material + b"\x00" * 32)[:32]
        nonce = b64d(env.data["nonce"])
        ct = b64d(env.data["ct"])
        aead = ChaCha20Poly1305(key)
        pt = aead.decrypt(nonce, ct, associated_data=None)
        return _to_str(pt)


# ----------------------------
# AES-CBC + HMAC (Encrypt-then-MAC)
# ----------------------------
class AESCBC_HMACPlugin(EncryptionPlugin):
    name = "AES_CBC_HMAC"

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        # derive two keys from key_material (simple split; adequate for PoC)
        km = (key_material + b"\x00" * 64)[:64]
        enc_key = km[:32]  # AES-256
        mac_key = km[32:]  # HMAC-SHA256
        iv = os.urandom(16)

        padder = sym_padding.PKCS7(128).padder()
        padded = padder.update(_to_bytes(plaintext)) + padder.finalize()

        cipher = Cipher(algorithms.AES(enc_key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ct = encryptor.update(padded) + encryptor.finalize()

        h = hmac.HMAC(mac_key, hashes.SHA256())
        h.update(iv + ct)
        tag = h.finalize()

        env = Envelope(1, self.name, {"iv": b64e(iv), "ct": b64e(ct), "tag": b64e(tag)})
        return env.dumps()

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("ciphertext not in AES_CBC_HMAC envelope")

        km = (key_material + b"\x00" * 64)[:64]
        enc_key = km[:32]
        mac_key = km[32:]

        iv = b64d(env.data["iv"])
        ct = b64d(env.data["ct"])
        tag = b64d(env.data["tag"])

        h = hmac.HMAC(mac_key, hashes.SHA256())
        h.update(iv + ct)
        h.verify(tag)  # raises InvalidSignature if tampered

        cipher = Cipher(algorithms.AES(enc_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ct) + decryptor.finalize()

        unpadder = sym_padding.PKCS7(128).unpadder()
        pt = unpadder.update(padded) + unpadder.finalize()
        return _to_str(pt)


# ----------------------------
# Fernet (high-level recipe)
# ----------------------------
class FernetPlugin(EncryptionPlugin):
    name = "FERNET"

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        # Fernet wants a 32-byte key that is base64 urlsafe encoded.
        key32 = (key_material + b"\x00" * 32)[:32]
        fkey = base64.urlsafe_b64encode(key32)
        f = Fernet(fkey)
        token = f.encrypt(_to_bytes(plaintext))
        env = Envelope(1, self.name, {"token": _to_str(token)})
        return env.dumps()

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("ciphertext not in FERNET envelope")
        key32 = (key_material + b"\x00" * 32)[:32]
        fkey = base64.urlsafe_b64encode(key32)
        f = Fernet(fkey)
        pt = f.decrypt(_to_bytes(env.data["token"]))
        return _to_str(pt)


# ----------------------------
# RSA-OAEP (asymmetric)
# NOTE: For a PoC, we derive a deterministic private key from env is messy.
# We instead accept PEM keys from env vars when using RSA modes.
# ----------------------------
class RSA_OAEPPlugin(EncryptionPlugin):
    name = "RSA_OAEP"

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        pub_pem = os.environ.get("RSA_PUBLIC_KEY_PEM", "")
        if not pub_pem:
            raise ValueError("RSA_PUBLIC_KEY_PEM is required for RSA_OAEP")
        public_key = serialization.load_pem_public_key(pub_pem.encode("utf-8"))

        ct = public_key.encrypt(
            _to_bytes(plaintext),
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        env = Envelope(1, self.name, {"ct": b64e(ct)})
        return env.dumps()

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        priv_pem = os.environ.get("RSA_PRIVATE_KEY_PEM", "")
        if not priv_pem:
            raise ValueError("RSA_PRIVATE_KEY_PEM is required for RSA_OAEP")
        private_key = serialization.load_pem_private_key(priv_pem.encode("utf-8"), password=None)

        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("ciphertext not in RSA_OAEP envelope")

        ct = b64d(env.data["ct"])
        pt = private_key.decrypt(
            ct,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return _to_str(pt)


# ----------------------------
# Hybrid envelope: RSA-OAEP wraps DEK + AES-GCM encrypts payload
# ----------------------------
class Hybrid_RSA_AESGCMPlugin(EncryptionPlugin):
    name = "HYBRID_RSA_AESGCM"

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        pub_pem = os.environ.get("RSA_PUBLIC_KEY_PEM", "")
        if not pub_pem:
            raise ValueError("RSA_PUBLIC_KEY_PEM is required for HYBRID_RSA_AESGCM")
        public_key = serialization.load_pem_public_key(pub_pem.encode("utf-8"))

        dek = os.urandom(32)
        nonce = os.urandom(12)
        ct = AESGCM(dek).encrypt(nonce, _to_bytes(plaintext), None)

        wrapped_dek = public_key.encrypt(
            dek,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        env = Envelope(1, self.name, {"nonce": b64e(nonce), "ct": b64e(ct), "edek": b64e(wrapped_dek)})
        return env.dumps()

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        priv_pem = os.environ.get("RSA_PRIVATE_KEY_PEM", "")
        if not priv_pem:
            raise ValueError("RSA_PRIVATE_KEY_PEM is required for HYBRID_RSA_AESGCM")
        private_key = serialization.load_pem_private_key(priv_pem.encode("utf-8"), password=None)

        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("ciphertext not in HYBRID_RSA_AESGCM envelope")

        dek = private_key.decrypt(
            b64d(env.data["edek"]),
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        nonce = b64d(env.data["nonce"])
        ct = b64d(env.data["ct"])
        pt = AESGCM(dek).decrypt(nonce, ct, None)
        return _to_str(pt)


# ----------------------------
# Token modes
# JWT_SIGNED = integrity/auth (NOT encryption)
# JWT_ENCRYPTED = JWE (real encryption) via jwcrypto
# ----------------------------
class JWTSignedPlugin(EncryptionPlugin):
    name = "JWT_SIGNED"

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        if jwt is None:
            raise ValueError("PyJWT not installed")
        secret = key_material  # HMAC secret
        token = jwt.encode({"v": plaintext}, secret, algorithm="HS256")
        env = Envelope(1, self.name, {"token": token})
        return env.dumps()

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        if jwt is None:
            raise ValueError("PyJWT not installed")
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("ciphertext not in JWT_SIGNED envelope")
        secret = key_material
        obj = jwt.decode(env.data["token"], secret, algorithms=["HS256"])
        return _to_str(obj.get("v", ""))


class JWTEncryptedPlugin(EncryptionPlugin):
    name = "JWT_ENCRYPTED"

    def encrypt(self, plaintext: str, key_material: bytes) -> str:
        if jwk is None or jwe is None:
            raise ValueError("jwcrypto not installed")
        # Direct encryption with an octet key (A256GCM)
        k = jwk.JWK(kty="oct", k=b64e((key_material + b"\x00" * 32)[:32]))
        protected = {"alg": "dir", "enc": "A256GCM"}
        token = jwe.JWE(_to_bytes(plaintext), protected=protected)
        token.add_recipient(k)
        env = Envelope(1, self.name, {"token": token.serialize(compact=True)})
        return env.dumps()

    def decrypt(self, ciphertext: str, key_material: bytes) -> str:
        if jwk is None or jwe is None:
            raise ValueError("jwcrypto not installed")
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("ciphertext not in JWT_ENCRYPTED envelope")
        k = jwk.JWK(kty="oct", k=b64e((key_material + b"\x00" * 32)[:32]))
        token = jwe.JWE()
        token.deserialize(env.data["token"])
        token.decrypt(k)
        return _to_str(token.payload)


# ----------------------------
# Plugin Manager
# ----------------------------
class EncryptionPluginManager:
    def __init__(self) -> None:
        self._plugins: Dict[str, EncryptionPlugin] = {}

    def register(self, plugin: EncryptionPlugin) -> None:
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> EncryptionPlugin:
        n = (name or "").strip().upper()
        if n in self._plugins:
            return self._plugins[n]
        # Backward-compat default
        return self._plugins["AES_GCM"]


def default_manager() -> EncryptionPluginManager:
    m = EncryptionPluginManager()
    m.register(AESGCMPlugin())
    m.register(ChaCha20Poly1305Plugin())
    m.register(AESCBC_HMACPlugin())
    m.register(FernetPlugin())
    m.register(RSA_OAEPPlugin())
    m.register(Hybrid_RSA_AESGCMPlugin())
    m.register(JWTSignedPlugin())
    m.register(JWTEncryptedPlugin())
    return m


def try_decrypt_any(value: str, key_material: bytes, manager: EncryptionPluginManager) -> str:
    """
    If value is not an envelope, return as-is.
    If it is an envelope, decrypt using the alg stated.
    """
    env = Envelope.loads(value)
    if not env:
        return value
    plugin = manager.get(env.alg)
    return plugin.decrypt(value, key_material)
