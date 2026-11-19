"""Standard-library password hashing and constant-time verification."""

import hashlib
import hmac
import secrets

from backend.core.errors import ValidationError

PBKDF2_ITERATIONS = 310_000
SALT_BYTES = 16
HASH_BYTES = 32


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> tuple[str, str]:
    """Return a random salt and PBKDF2-SHA256 password digest as hex."""
    if not isinstance(password, str) or len(password) < 8:
        raise ValidationError("Password must contain at least 8 characters.")
    if iterations < PBKDF2_ITERATIONS:
        raise ValidationError("Password hashing iterations are below the security minimum.")
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=HASH_BYTES)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, digest_hex: str, iterations: int = PBKDF2_ITERATIONS) -> bool:
    """Verify a password digest without timing-sensitive comparison."""
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    if not salt or len(expected) != HASH_BYTES or iterations < PBKDF2_ITERATIONS:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected))
    return hmac.compare_digest(candidate, expected)


def hash_pin(pin: str) -> tuple[str, str]:
    """Hash a numeric administrator PIN using the password primitive."""
    if not pin.isdigit() or not 4 <= len(pin) <= 12:
        raise ValidationError("PIN must contain 4 to 12 digits.")
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=HASH_BYTES
    )
    return salt.hex(), digest.hex()
