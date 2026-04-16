"""
Authentication API endpoints.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.security import create_access_token, ADMIN_PASSWORD

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    access_token: str


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    """Verify admin password and return JWT token."""
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="密码错误")
    return LoginResponse(access_token=create_access_token())
