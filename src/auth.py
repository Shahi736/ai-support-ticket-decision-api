import os
from datetime import datetime, timedelta, timezone
from typing import Optional
 
import bcrypt
from dotenv import load_dotenv
from jose import JWTError, jwt
 
load_dotenv()
 
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
 
if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is not set. Add it to your .env file before starting the app."
    )
 
# bcrypt's underlying algorithm only uses the first 72 bytes of a password;
# encode+truncate up front so long passwords don't raise instead of hashing.
_MAX_PASSWORD_BYTES = 72
 
 
def hash_password(password: str) -> str:
    pw_bytes = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    hashed = bcrypt.hashpw(pw_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")
 
 
def verify_password(plain_password: str, password_hash: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.checkpw(pw_bytes, password_hash.encode("utf-8"))
 
 
def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    """
    Creates a signed JWT. 'subject' is typically the user's id or email
    and is stored in the 'sub' claim, the JWT standard for identifying
    the token's owner.
    """
    expire_minutes = expires_minutes or JWT_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
 
 
def decode_access_token(token: str) -> Optional[str]:
    """
    Decodes and validates a JWT. Returns the subject (user identifier)
    if valid, or None if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
 