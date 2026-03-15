from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Dict, Optional

from cryptography.hazmat.primitives import hashes, hmac, padding as sym_padding, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


DEFAULT_SHARED_KEY = b"change-me-for-benchmarks-only"
RSA_CHUNK_SIZE_2048_OAEP_SHA256 = 190


def _to_bytes(value: str | bytes) -> bytes:
    return value if isinstance(value, bytes) else value.encode("utf-8")


def _to_str(value: str | bytes) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else value


def b64e(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def b64d(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


@dataclass
class Envelope:
    v: int
    alg: str
    data: dict

    def dumps(self) -> str:
        return json.dumps({"v": self.v, "alg": self.alg, "data": self.data}, separators=(",", ":"))

    @staticmethod
    def loads(payload: str) -> Optional["Envelope"]:
        try:
            obj = json.loads(payload)
        except Exception:
            return None
        if not isinstance(obj, dict):
            return None
        if obj.get("v") != 1:
            return None
        alg = obj.get("alg")
        data = obj.get("data")
        if not isinstance(alg, str) or not isinstance(data, dict):
            return None
        return Envelope(v=1, alg=alg, data=data)


@dataclass
class KeyMaterial:
    shared_key: bytes
    rsa_private_key_pem: Optional[bytes] = None
    rsa_public_key_pem: Optional[bytes] = None

    def get_rsa_private_key(self):
        if not self.rsa_private_key_pem:
            raise ValueError("RSA private key not configured")
        return serialization.load_pem_private_key(self.rsa_private_key_pem, password=None)

    def get_rsa_public_key(self):
        if self.rsa_public_key_pem:
            return serialization.load_pem_public_key(self.rsa_public_key_pem)
        if self.rsa_private_key_pem:
            return self.get_rsa_private_key().public_key()
        raise ValueError("RSA public key not configured")


class EncryptionPlugin:
    name: str

    def encrypt(self, plaintext: str, key_material: KeyMaterial) -> str:
        raise NotImplementedError

    def decrypt(self, ciphertext: str, key_material: KeyMaterial) -> str:
        raise NotImplementedError


class PlaintextPlugin(EncryptionPlugin):
    name = "PLAINTEXT"

    def encrypt(self, plaintext: str, key_material: KeyMaterial) -> str:
        return Envelope(1, self.name, {"value": plaintext}).dumps()

    def decrypt(self, ciphertext: str, key_material: KeyMaterial) -> str:
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("not PLAINTEXT envelope")
        return str(env.data["value"])


class AESGCMPlugin(EncryptionPlugin):
    name = "AES_GCM"

    def encrypt(self, plaintext: str, key_material: KeyMaterial) -> str:
        key = (key_material.shared_key + b"\x00" * 32)[:32]
        nonce = os.urandom(12)
        ct = AESGCM(key).encrypt(nonce, _to_bytes(plaintext), None)
        return Envelope(1, self.name, {"nonce": b64e(nonce), "ct": b64e(ct)}).dumps()

    def decrypt(self, ciphertext: str, key_material: KeyMaterial) -> str:
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("not AES_GCM envelope")
        key = (key_material.shared_key + b"\x00" * 32)[:32]
        pt = AESGCM(key).decrypt(b64d(env.data["nonce"]), b64d(env.data["ct"]), None)
        return _to_str(pt)


class AESCBCPlugin(EncryptionPlugin):
    name = "AES_CBC"

    def encrypt(self, plaintext: str, key_material: KeyMaterial) -> str:
        km = (key_material.shared_key + b"\x00" * 64)[:64]
        enc_key = km[:32]
        mac_key = km[32:]
        iv = os.urandom(16)
        padder = sym_padding.PKCS7(128).padder()
        padded = padder.update(_to_bytes(plaintext)) + padder.finalize()
        cipher = Cipher(algorithms.AES(enc_key), modes.CBC(iv))
        ct = cipher.encryptor().update(padded) + cipher.encryptor().finalize()
        h = hmac.HMAC(mac_key, hashes.SHA256())
        h.update(iv + ct)
        tag = h.finalize()
        return Envelope(1, self.name, {"iv": b64e(iv), "ct": b64e(ct), "tag": b64e(tag)}).dumps()

    def decrypt(self, ciphertext: str, key_material: KeyMaterial) -> str:
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("not AES_CBC envelope")
        km = (key_material.shared_key + b"\x00" * 64)[:64]
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
        return _to_str(unpadder.update(padded) + unpadder.finalize())


class RSAPlugin(EncryptionPlugin):
    name = "RSA"

    @staticmethod
    def _encrypt_chunks(data: bytes, public_key) -> list[str]:
        chunks = []
        for idx in range(0, len(data), RSA_CHUNK_SIZE_2048_OAEP_SHA256):
            block = data[idx: idx + RSA_CHUNK_SIZE_2048_OAEP_SHA256]
            ct = public_key.encrypt(
                block,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            chunks.append(b64e(ct))
        return chunks

    @staticmethod
    def _decrypt_chunks(chunks: list[str], private_key) -> bytes:
        return b"".join(
            private_key.decrypt(
                b64d(chunk),
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            for chunk in chunks
        )

    def encrypt(self, plaintext: str, key_material: KeyMaterial) -> str:
        chunks = self._encrypt_chunks(_to_bytes(plaintext), key_material.get_rsa_public_key())
        return Envelope(1, self.name, {"chunks": chunks}).dumps()

    def decrypt(self, ciphertext: str, key_material: KeyMaterial) -> str:
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("not RSA envelope")
        return _to_str(self._decrypt_chunks(env.data["chunks"], key_material.get_rsa_private_key()))


class HybridAESGCMRSAPlugin(EncryptionPlugin):
    name = "HYBRID_AES_GCM_RSA"

    def encrypt(self, plaintext: str, key_material: KeyMaterial) -> str:
        public_key = key_material.get_rsa_public_key()
        dek = os.urandom(32)
        nonce = os.urandom(12)
        ct = AESGCM(dek).encrypt(nonce, _to_bytes(plaintext), None)
        encrypted_key = public_key.encrypt(
            dek,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return Envelope(1, self.name, {"nonce": b64e(nonce), "ct": b64e(ct), "encrypted_key": b64e(encrypted_key)}).dumps()

    def decrypt(self, ciphertext: str, key_material: KeyMaterial) -> str:
        env = Envelope.loads(ciphertext)
        if not env or env.alg != self.name:
            raise ValueError("not HYBRID_AES_GCM_RSA envelope")
        private_key = key_material.get_rsa_private_key()
        dek = private_key.decrypt(
            b64d(env.data["encrypted_key"]),
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        pt = AESGCM(dek).decrypt(b64d(env.data["nonce"]), b64d(env.data["ct"]), None)
        return _to_str(pt)


class EncryptionPluginManager:
    def __init__(self) -> None:
        self._plugins: Dict[str, EncryptionPlugin] = {}

    def register(self, plugin: EncryptionPlugin) -> None:
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> EncryptionPlugin:
        normalized = (name or "").strip().upper()
        if normalized in {"NONE", "PLAINTEXT"}:
            normalized = "PLAINTEXT"
        if normalized not in self._plugins:
            raise KeyError(f"unsupported encryption type: {name}")
        return self._plugins[normalized]

    @property
    def names(self) -> list[str]:
        return sorted(self._plugins.keys())


def default_manager() -> EncryptionPluginManager:
    manager = EncryptionPluginManager()
    manager.register(PlaintextPlugin())
    manager.register(AESGCMPlugin())
    manager.register(AESCBCPlugin())
    manager.register(RSAPlugin())
    manager.register(HybridAESGCMRSAPlugin())
    return manager


def load_key_material_from_env(shared_env: str = "ENCRYPTION_KEY_DATA") -> KeyMaterial:
    shared_key = os.environ.get(shared_env, "").encode("utf-8") or DEFAULT_SHARED_KEY
    private_pem = os.environ.get("RSA_PRIVATE_KEY_PEM", "").encode("utf-8") or None
    public_pem = os.environ.get("RSA_PUBLIC_KEY_PEM", "").encode("utf-8") or None
    return KeyMaterial(shared_key=shared_key, rsa_private_key_pem=private_pem, rsa_public_key_pem=public_pem)


def generate_rsa_keypair(bits: int = 2048) -> tuple[bytes, bytes]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def ensure_rsa_key_material(key_material: KeyMaterial) -> KeyMaterial:
    if key_material.rsa_private_key_pem or key_material.rsa_public_key_pem:
        return key_material
    private_pem, public_pem = generate_rsa_keypair()
    return KeyMaterial(shared_key=key_material.shared_key, rsa_private_key_pem=private_pem, rsa_public_key_pem=public_pem)


def try_decrypt_any(value: str, key_material: KeyMaterial, manager: EncryptionPluginManager) -> str:
    env = Envelope.loads(value)
    if not env:
        return value
    plugin = manager.get(env.alg)
    return plugin.decrypt(value, key_material)
