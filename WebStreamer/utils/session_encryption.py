# Session file encryption for secure GitHub storage
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import base64
import hashlib
from ..vars import Var

def get_session_key():
    """Get session encryption key from environment"""
    key = Var.GITHUB_SESSION_KEY
    if not key:
        raise ValueError("GITHUB_SESSION_KEY not set in environment")
    # Derive a 32-byte key using SHA-256
    return hashlib.sha256(key.encode()).digest()

def encrypt_session_file(file_data: bytes) -> bytes:
    """Encrypt session file before uploading to GitHub"""
    try:
        key = get_session_key()
        
        # Generate random IV
        iv = get_random_bytes(16)
        
        # Create cipher
        cipher = AES.new(key, AES.MODE_CBC, iv)
        
        # Encrypt data
        encrypted_data = cipher.encrypt(pad(file_data, AES.block_size))
        
        # Combine IV + encrypted data
        result = iv + encrypted_data
        
        # Return base64 encoded
        return base64.b64encode(result)
        
    except Exception as e:
        print(f"❌ Session encryption failed: {e}")
        # Return original data if encryption fails (fallback)
        return file_data

def decrypt_session_file(encrypted_data: bytes) -> bytes:
    """Decrypt session file after downloading from GitHub"""
    try:
        key = get_session_key()
        
        # Decode base64
        data = base64.b64decode(encrypted_data)
        
        # Extract IV (first 16 bytes)
        iv = data[:16]
        encrypted_content = data[16:]
        
        # Create cipher
        cipher = AES.new(key, AES.MODE_CBC, iv)
        
        # Decrypt and unpad
        decrypted_data = unpad(cipher.decrypt(encrypted_content), AES.block_size)
        
        return decrypted_data
        
    except Exception as e:
        print(f"❌ Session decryption failed: {e}")
        # Try to return data as-is (might be unencrypted legacy file)
        try:
            return base64.b64decode(encrypted_data)
        except:
            return encrypted_data
