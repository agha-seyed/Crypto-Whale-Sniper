from cryptography.fernet import Fernet
import base64
import os
import hashlib

def get_encryption_key() -> bytes:
    """
    تولید یا دریافت کلید رمزنگاری از متغیر محیطی.
    برای امنیت بیشتر، در محیط پروداکشن باید یک کلید ثابت 32 بایتی در ENCRYPTION_KEY قرار داده شود.
    """
    key_string = os.getenv("ENCRYPTION_KEY", "default-insecure-key-change-in-production")
    # تبدیل هر رشته‌ای به کلید 32 بایتی معتبر برای Fernet با استفاده از هش SHA-256
    key_hash = hashlib.sha256(key_string.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(key_hash)

# ایجاد یک نمونه از ابزار رمزنگاری
cipher_suite = Fernet(get_encryption_key())

def encrypt_private_key(private_key: str) -> str:
    """
    دریافت کلید خصوصی ساده و رمزنگاری آن با الگوریتم متقارن Fernet
    """
    if not private_key:
        return None
    encrypted_bytes = cipher_suite.encrypt(private_key.encode('utf-8'))
    return encrypted_bytes.decode('utf-8')

def decrypt_private_key(encrypted_key: str) -> str:
    """
    دریافت کلید خصوصی رمزنگاری شده از دیتابیس و بازگرداندن آن به حالت متنی
    """
    if not encrypted_key:
        return None
    decrypted_bytes = cipher_suite.decrypt(encrypted_key.encode('utf-8'))
    return decrypted_bytes.decode('utf-8')
