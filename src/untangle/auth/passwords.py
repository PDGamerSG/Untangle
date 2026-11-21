"""Password hashing with Argon2id (RFC 9106 low-memory profile, the argon2-cffi default)."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_HASHER = PasswordHasher()
# Verifying against a fixed hash when an email is unknown keeps sign-in timing the same for both cases.
_DUMMY = _HASHER.hash("untangle-timing-equaliser")

MIN_LENGTH = 10
MAX_LENGTH = 128
_COMMON = frozenset(
    """password password1 password12 password123 passw0rd 1234567890 12345678910 qwertyuiop qwerty1234
    qwerty12345 iloveyou12 letmein123 welcome123 admin12345 administrator untangle123 abc1234567 1q2w3e4r5t
    0987654321 1111111111 0000000000 football12 baseball12 monkey1234 dragon1234 sunshine12 princess12""".split()
)


def policy_problem(password: str, email: str) -> str | None:
    """A reason the password is unacceptable, or None. Length matters most (NIST SP 800-63B)."""
    if len(password) < MIN_LENGTH:
        return f"Use at least {MIN_LENGTH} characters."
    if len(password) > MAX_LENGTH:
        return f"Use at most {MAX_LENGTH} characters."
    lowered = password.lower()
    if lowered in _COMMON or len(set(password)) < 4:
        return "This password is too easy to guess. Choose a longer or less common one."
    local = email.split("@", 1)[0].lower()
    if len(local) >= 4 and local in lowered:
        return "Do not include your email address in the password."
    return None


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify(stored: str | None, password: str) -> bool:
    try:
        return _HASHER.verify(stored or _DUMMY, password) and stored is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored: str) -> bool:
    try:
        return _HASHER.check_needs_rehash(stored)
    except InvalidHashError:
        return True
