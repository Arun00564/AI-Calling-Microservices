from cryptography.fernet import Fernet
from app.core.config import settings


def encrypt_value(value: str) -> str:
    fernet = Fernet(settings.WEBHOOK_ENCRYPTION_KEY.encode())
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    fernet = Fernet(settings.WEBHOOK_ENCRYPTION_KEY.encode())
    return fernet.decrypt(value.encode()).decode()
