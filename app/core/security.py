import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from passlib.context import CryptContext
from jose import JWTError, jwt
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
import pyotp
from app.core.config import get_settings

settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


# JWT Token Management
def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": secrets.token_hex(16),
        "type": "access"
    })

    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: Dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": secrets.token_hex(16),
        "type": "refresh"
    })

    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Dict:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


# AES-256 Encryption for Messages
def _get_aes_key() -> bytes:
    """Derive 32-byte AES key from config"""
    return hashlib.sha256(settings.AES_KEY.encode()).digest()


def encrypt_message(plaintext: str) -> Dict[str, str]:
    """
    Encrypt message using AES-256-CBC
    Returns: {ciphertext: base64, iv: base64}
    """
    key = _get_aes_key()
    iv = secrets.token_bytes(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)

    padded_data = pad(plaintext.encode(), AES.block_size)
    ciphertext = cipher.encrypt(padded_data)

    return {
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "iv": base64.b64encode(iv).decode()
    }


def decrypt_message(ciphertext_b64: str, iv_b64: str) -> str:
    """Decrypt AES-256-CBC encrypted message"""
    key = _get_aes_key()
    iv = base64.b64decode(iv_b64)
    ciphertext = base64.b64decode(ciphertext_b64)

    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_plaintext = cipher.decrypt(ciphertext)
    plaintext = unpad(padded_plaintext, AES.block_size)

    return plaintext.decode()


# Multi-Factor Authentication (TOTP)
def generate_totp_secret() -> str:
    """Generate new TOTP secret"""
    return pyotp.random_base32()


def get_totp_uri(secret: str, callsign: str) -> str:
    """Get TOTP provisioning URI for QR code"""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=callsign, issuer_name=settings.MFA_ISSUER)


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """Verify TOTP code with time window"""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=window)


# Role-Based Access Control
ROLE_PERMISSIONS = {
    "COMMANDER": {
        "level": 4,
        "permissions": [
            "admin:*", "users:*", "map:rw", "threats:rw",
            "comms:rw", "drones:rw", "analytics:rw", "cyber:rw",
            "intel:rw", "missions:rw", "sensors:rw", "audit:r"
        ]
    },
    "OPERATOR": {
        "level": 3,
        "permissions": [
            "map:rw", "threats:rw", "comms:rw", "drones:rw",
            "analytics:r", "cyber:r", "sensors:rw", "missions:r"
        ]
    },
    "ANALYST": {
        "level": 2,
        "permissions": [
            "threats:r", "comms:r", "analytics:r", "cyber:r",
            "intel:r", "sensors:r", "missions:r"
        ]
    },
    "VIEWER": {
        "level": 1,
        "permissions": [
            "map:r", "analytics:r", "missions:r"
        ]
    }
}


def get_permissions_for_role(role: str) -> List[str]:
    """Get permission list for role"""
    return ROLE_PERMISSIONS.get(role, {}).get("permissions", [])


def has_permission(user_role: str, required_permission: str) -> bool:
    """Check if role has specific permission"""
    permissions = get_permissions_for_role(user_role)

    # Check for wildcard permission
    for perm in permissions:
        if perm == required_permission:
            return True
        if perm.endswith(":*"):
            resource = perm.split(":")[0]
            if required_permission.startswith(f"{resource}:"):
                return True

    return False


# Audit Hashing (Tamper-Evident)
def compute_audit_hash(entry: Dict) -> str:
    """Compute SHA-256 hash of audit log entry for tamper detection"""
    # Sort keys for consistent hashing
    sorted_entry = {k: entry[k] for k in sorted(entry.keys())}
    entry_str = str(sorted_entry)
    return hashlib.sha256(entry_str.encode()).hexdigest()


# Password Strength Validation
def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password meets military-grade requirements
    Returns: (is_valid, error_message)
    """
    if len(password) < 12:
        return False, "Password must be at least 12 characters"

    if not any(c.isupper() for c in password):
        return False, "Password must contain uppercase letters"

    if not any(c.islower() for c in password):
        return False, "Password must contain lowercase letters"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain numbers"

    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Password must contain special characters"

    # Check for common patterns
    common_patterns = ["password", "123456", "qwerty", "admin", "aegis"]
    if any(pattern in password.lower() for pattern in common_patterns):
        return False, "Password contains common patterns"

    return True, "Password meets requirements"
