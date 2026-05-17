"""FastAPI dependencies cho API quản trị."""
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.auth_tokens import is_admin_token


def _bearer_token(authorization: str | None) -> str | None:
    """Lấy token từ Authorization: Bearer <token>."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def require_admin_token(
    authorization: Annotated[str | None, Header()] = None,
    x_admin_token: Annotated[str | None, Header()] = None,
) -> str:
    """FastAPI dependency bắt buộc token admin."""
    token = _bearer_token(authorization) or x_admin_token
    if is_admin_token(token):
        return token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Cần admin token hợp lệ",
        headers={"WWW-Authenticate": "Bearer"},
    )


def optional_admin_token(
    authorization: Annotated[str | None, Header()] = None,
    x_admin_token: Annotated[str | None, Header()] = None,
) -> str | None:
    """FastAPI dependency trả token nếu hợp lệ, không tự chặn request."""
    token = _bearer_token(authorization) or x_admin_token
    return token if is_admin_token(token) else None
