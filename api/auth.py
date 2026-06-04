"""OAuth 2.0 client credentials flow with RS256 JWT."""

import os
import time
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

ALGORITHM = os.getenv("JWT_ALGORITHM", "RS256")
PRIVATE_KEY_PATH = Path(os.getenv("JWT_PRIVATE_KEY_PATH", "keys/private.pem"))
PUBLIC_KEY_PATH = Path(os.getenv("JWT_PUBLIC_KEY_PATH", "keys/public.pem"))
EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
CLIENT_ID = os.getenv("OAUTH_CLIENT_ID", "arxivmind-client")
_raw_secret = os.getenv("OAUTH_CLIENT_SECRET", "")
if not _raw_secret:
    import warnings

    warnings.warn(
        "OAUTH_CLIENT_SECRET is not set — using insecure default. Set it in .env.", stacklevel=1
    )
    _raw_secret = "change-me"
CLIENT_SECRET = _raw_secret

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token", auto_error=False)

_private_key: str | None = None
_public_key: str | None = None


def _load_keys() -> tuple[str, str]:
    global _private_key, _public_key
    if _private_key is None:
        if PRIVATE_KEY_PATH.exists():
            _private_key = PRIVATE_KEY_PATH.read_text()
            _public_key = PUBLIC_KEY_PATH.read_text()
        else:
            # Fallback to HS256 for dev without key files
            global ALGORITHM
            ALGORITHM = "HS256"
            _private_key = CLIENT_SECRET
            _public_key = CLIENT_SECRET
    return _private_key, _public_key


def create_access_token(client_id: str, scopes: list[str]) -> str:
    private_key, _ = _load_keys()
    payload = {
        "sub": client_id,
        "scopes": scopes,
        "iat": int(time.time()),
        "exp": int(time.time()) + EXPIRE_MINUTES * 60,
    }
    return jwt.encode(payload, private_key, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    _, public_key = _load_keys()
    try:
        return jwt.decode(token, public_key, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def get_current_client(token: str = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token(token)


def require_scope(scope: str):
    def checker(client: dict = Depends(get_current_client)) -> dict:
        if scope not in client.get("scopes", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{scope}' required",
            )
        return client

    return checker
