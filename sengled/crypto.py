#!/usr/bin/env python3
"""
RC4 encryption for Sengled Wi-Fi setup communication.
Implements the same RC4 algorithm used by the Sengled mobile app
to encrypt/decrypt local Wi-Fi configuration payloads sent to bulbs.
"""

import base64
import json

# --- RC4 Crypto for Local Wi-Fi Setup ---
# Note: RC4 is used because it's what the Sengled app uses
# This is NOT cryptographically secure - it's just for protocol compatibility
# The key is hardcoded in the app and provides no real security
KEY_STR = "MTlCaWppbmdTaGFuZ2hhaVdpU2VuZ2xlZEZpMjBBQUJBU0U2NA=="  # literal string used by the app

class SengledWiFiCrypto:
    """Wi-Fi setup crypto handler for Sengled devices"""
    
    def __init__(self):
        """Initialize Wi-Fi crypto handler"""
        pass
    
    def encrypt_wifi_payload(self, data):
        """RC4 encrypt data for Wi-Fi setup. Returns base64(ciphertext)."""
        if isinstance(data, dict):
            data = json.dumps(data)
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        else:
            data_bytes = data
        
        # Use the key format used by the app
        key = KEY_STR.encode('utf-8')
        
        # RC4 encrypt
        encrypted = self._rc4_crypt(data_bytes, key)
        
        # Return base64 format: base64(ciphertext)
        return base64.b64encode(encrypted).decode('utf-8')

    def decrypt_wifi_payload(self, b64_str):
        """Decrypt RC4-encrypted Wi-Fi setup data"""
        try:
            ciphertext = base64.b64decode(b64_str)
            
            # Use the same key format as encrypt
            key = KEY_STR.encode('utf-8')
            decrypted = self._rc4_crypt(ciphertext, key)
            return json.loads(decrypted.decode('utf-8'))
        except Exception as e:
            return f"RC4 Decryption Failed: {e}"
    
    def _rc4_crypt(self, data, key):
        """RC4 encryption/decryption (same operation)"""
        S = list(range(256))
        j = 0
        key_len = len(key)
        
        for i in range(256):
            j = (j + S[i] + key[i % key_len]) % 256
            S[i], S[j] = S[j], S[i]
        
        i = j = 0
        out = bytearray()
        for byte in data:
            i = (i + 1) % 256
            j = (j + S[i]) % 256
            S[i], S[j] = S[j], S[i]
            K = S[(S[i] + S[j]) % 256]
            out.append(byte ^ K)
        
        return bytes(out)

def encrypt_wifi_payload(data):
    """Encrypt Wi-Fi setup payload using RC4"""
    crypto = SengledWiFiCrypto()
    return crypto.encrypt_wifi_payload(data)

def decrypt_wifi_payload(b64_str):
    """Decrypt Wi-Fi setup payload using RC4"""
    crypto = SengledWiFiCrypto()
    return crypto.decrypt_wifi_payload(b64_str)

__all__ = [
    'SengledWiFiCrypto', 
    'encrypt_wifi_payload', 
    'decrypt_wifi_payload',
    'KEY_STR'
] 