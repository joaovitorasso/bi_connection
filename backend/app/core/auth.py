from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from .config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

# ---------------------------------------------------------------------------
# Password hashing - tries bcrypt directly (avoids passlib 1.7.4 / bcrypt 4.x
# incompatibility on Python 3.13); falls back to SHA-256 for robustness.
# ---------------------------------------------------------------------------
try:
    import bcrypt as _bcrypt

    def _hash_password(plain: str) -> str:
        return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()

    def _verify_password(plain: str, hashed: str) -> bool:
        try:
            return _bcrypt.checkpw(plain.encode(), hashed.encode())
        except Exception:
            return False

except Exception:
    import hashlib
    import hmac

    _SALT = "pbix_editor_mvp_2024"

    def _hash_password(plain: str) -> str:
        return hashlib.sha256((_SALT + plain).encode()).hexdigest()

    def _verify_password(plain: str, hashed: str) -> bool:
        return hmac.compare_digest(_hash_password(plain), hashed)


# Usuarios hardcoded para MVP
USERS_DB = {
    "admin": {"username": "admin", "hashed_password": _hash_password("admin"), "role": "admin"},
    "viewer": {"username": "viewer", "hashed_password": _hash_password("viewer"), "role": "viewer"},
}


class UserProfile(BaseModel):
    username: str
    role: str


class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    role: str


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def authenticate_user(username: str, password: str) -> Optional[UserProfile]:
    user = USERS_DB.get(username)
    if not user:
        return None
    if not _verify_password(password, user["hashed_password"]):
        return None
    return UserProfile(username=user["username"], role=user["role"])


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserProfile:
    if not token:
        # Permitir acesso sem autenticacao em modo dev (retorna usuario admin padrao)
        return UserProfile(username="dev", role="admin")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role", "viewer")
        if username is None:
            raise HTTPException(status_code=401, detail="Token invalido")
        return UserProfile(username=username, role=role)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalido")


def require_admin(user: UserProfile = Depends(get_current_user)) -> UserProfile:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Requer perfil admin")
    return user


def require_any_role(user: UserProfile = Depends(get_current_user)) -> UserProfile:
    return user
