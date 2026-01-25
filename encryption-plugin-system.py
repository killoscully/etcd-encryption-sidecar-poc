from Crypto.Cipher import AES
import base64
import os

class EncryptionPlugin:
    """Base class for encryption plugins."""
    def encrypt(self, data, key):
        raise NotImplementedError

    def decrypt(self, data, key):
        raise NotImplementedError

    def generate_key(self):
        """Generate a random key (default 256-bit for AES)."""
        return os.urandom(32)

class AESPlugin(EncryptionPlugin):
    """AES encryption plugin using AES-256-CBC."""
    def encrypt(self, data, key):
        cipher = AES.new(key, AES.MODE_CBC, key[:16])
        padded_data = data + (16 - len(data) % 16) * chr(16 - len(data) % 16)
        encrypted_bytes = cipher.encrypt(padded_data.encode())
        return base64.b64encode(encrypted_bytes).decode()

    def decrypt(self, data, key):
        cipher = AES.new(key, AES.MODE_CBC, key[:16])
        decrypted_bytes = cipher.decrypt(base64.b64decode(data))
        return decrypted_bytes.rstrip(b"\x10").decode()

class EncryptionPluginManager:
    """Manages encryption plugins."""
    def __init__(self):
        self.plugins = {}

    def register_plugin(self, name, plugin):
        self.plugins[name] = plugin

    def get_plugin(self, name):
        return self.plugins.get(name, AESPlugin())  # Default to AES

