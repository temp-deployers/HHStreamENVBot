from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad

import base64
from hashlib import sha256
from ..vars import Var

# Get encryption keys from environment
SECRET_KEY = Var.SECRET_KEY
key = Var.AES_KEY
iv = Var.AES_IV.encode('utf-8')

def verify_sha256_key(cid, fid, expiration_time, sha256_key):
    try:
        # Concatenate the components with the secret key
        data_to_hash = f"{cid}|{fid}|{expiration_time}|{SECRET_KEY}".encode('utf-8')

        # Calculate the SHA-256 hash
        sha256_hash = sha256(data_to_hash).hexdigest()

        # Compare the calculated hash with the received sha256_key
        return sha256_hash == sha256_key
    except Exception:
        return False

def decrypt(enc, key, iv):
    enc = base64.b64decode(enc)
    cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(enc), 16)
    decrypted_str = decrypted.decode('utf-8')
    channel_id, message_id, expiration_time = decrypted_str.split('|')
    return channel_id, message_id, int(expiration_time)

def encrypt_channel_id(channel_id: int) -> str:
    """Encrypt channel ID for use in links"""
    try:
        data = str(channel_id).encode('utf-8')
        cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv)
        encrypted = cipher.encrypt(pad(data, 16))
        return base64.b64encode(encrypted).decode('utf-8')
    except Exception as e:
        print(f"Encryption error: {e}")
        return str(channel_id)

def decrypt_channel_id(encrypted_id: str) -> int:
    """Decrypt channel ID from link"""
    try:
        enc = base64.b64decode(encrypted_id)
        cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(enc), 16)
        return int(decrypted.decode('utf-8'))
    except Exception as e:
        print(f"Decryption error: {e}")
        # Try to parse as direct channel ID (backwards compatibility)
        try:
            return int(encrypted_id)
        except:
            return 0
