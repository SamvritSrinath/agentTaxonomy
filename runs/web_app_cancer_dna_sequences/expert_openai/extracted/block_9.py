from dataclasses import dataclass
from typing import Iterable
import jwt
from fastapi import Header, HTTPException, status
from .config import settings


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str
    roles: list[str]


def decode_token(token: str) -> Principal:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {str(exc)}",
        )

    tenant_id = payload.get("tenant_id")
    subject = payload.get("sub")
    roles = payload.get("roles", [])

    if not tenant_id or not subject:
        raise HTTPException(status_code=401, detail="token missing tenant_id or sub")

    return Principal(subject=subject, tenant_id=tenant_id, roles=list(roles))


def require_principal(authorization: str = Header(...)) -> Principal:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    return decode_token(authorization.removeprefix("Bearer ").strip())


def require_roles(principal: Principal, allowed: Iterable[str]):
    if not set(principal.roles).intersection(set(allowed)):
        raise HTTPException(status_code=403, detail="insufficient role")
