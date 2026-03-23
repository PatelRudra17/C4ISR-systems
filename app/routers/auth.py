from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import secrets

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    decode_token, generate_totp_secret, get_totp_uri, verify_totp,
    get_permissions_for_role, validate_password_strength
)
from app.core.redis_client import check_rate_limit, session_set, session_delete, session_get
from app.core.config import get_settings
from app.models.models import User, UserRole, ClearanceLevel

settings = get_settings()
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# Pydantic Models
class LoginRequest(BaseModel):
    callsign: str
    password: str
    totp_code: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    callsign: str
    role: str
    clearance: str
    permissions: List[str]
    mfa_required: bool = False
    totp_setup_uri: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    callsign: str
    email: EmailStr
    full_name: str
    password: str
    role: UserRole
    clearance: ClearanceLevel


class UserProfile(BaseModel):
    id: str
    callsign: str
    email: str
    full_name: str
    role: str
    clearance: str
    mfa_enabled: bool
    permissions: List[str]
    last_login: Optional[datetime]


class MFAEnableRequest(BaseModel):
    totp_code: str


# Dependency: Get current user from JWT
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """Extract and validate user from JWT token"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )

    token = auth_header.split(" ")[1]
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    user_id = payload.get("sub")
    jti = payload.get("jti")

    # Verify session exists in Redis
    session_data = await session_get(f"{user_id}:{jti}")
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or expired"
        )

    # Get user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    return user


# Dependency: Require specific permission
def require_permission(permission: str):
    """Factory for permission checking dependency"""
    async def permission_checker(user: User = Depends(get_current_user)) -> User:
        from app.core.security import has_permission

        if not has_permission(user.role.value, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission}"
            )
        return user

    return permission_checker


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user with callsign, password, and optional TOTP"""
    client_ip = request.client.host

    # Rate limiting: 10 attempts per minute per IP
    rate_key = f"auth_rate:{client_ip}"
    if not await check_rate_limit(rate_key, settings.RATE_LIMIT_AUTH_PER_MINUTE, 60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later."
        )

    # Find user by callsign
    result = await db.execute(select(User).where(User.callsign == login_data.callsign))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Check account lock
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked until {user.locked_until.isoformat()}"
        )

    # Verify password
    if not verify_password(login_data.password, user.password_hash):
        user.login_attempts += 1

        # Lock account after 5 failed attempts for 30 minutes
        if user.login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=30)

        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Handle MFA
    if user.mfa_enabled:
        if not login_data.totp_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TOTP code required"
            )

        if not verify_totp(user.totp_secret, login_data.totp_code, window=1):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TOTP code"
            )
    elif not user.totp_secret:
        # First login - generate TOTP secret
        user.totp_secret = generate_totp_secret()
        await db.commit()

        setup_uri = get_totp_uri(user.totp_secret, user.callsign)

        return LoginResponse(
            access_token="",
            refresh_token="",
            callsign=user.callsign,
            role=user.role.value,
            clearance=user.clearance.value,
            permissions=[],
            mfa_required=True,
            totp_setup_uri=setup_uri
        )

    # Generate tokens
    permissions = get_permissions_for_role(user.role.value)
    token_data = {
        "sub": str(user.id),
        "role": user.role.value,
        "callsign": user.callsign,
        "clearance": user.clearance.value,
        "permissions": permissions
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"sub": str(user.id)})

    # Decode to get JTI for session storage
    access_payload = decode_token(access_token)
    session_data = {
        "callsign": user.callsign,
        "role": user.role.value,
        "ip": client_ip,
        "login_at": datetime.utcnow().isoformat()
    }

    await session_set(
        f"{user.id}:{access_payload['jti']}",
        session_data,
        settings.JWT_ACCESS_EXPIRE_MINUTES * 60
    )

    # Reset login attempts and update last login
    user.login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    await db.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        callsign=user.callsign,
        role=user.role.value,
        clearance=user.clearance.value,
        permissions=permissions
    )


@router.post("/refresh")
async def refresh_token(refresh_data: RefreshRequest):
    """Generate new access token from refresh token"""
    payload = decode_token(refresh_data.refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Create new access token with same user data
    new_access_token = create_access_token({"sub": payload["sub"]})

    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout(user: User = Depends(get_current_user), request: Request = None):
    """Invalidate current session"""
    auth_header = request.headers.get("Authorization")
    token = auth_header.split(" ")[1]
    payload = decode_token(token)

    if payload:
        await session_delete(f"{user.id}:{payload['jti']}")

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserProfile)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile"""
    return UserProfile(
        id=str(user.id),
        callsign=user.callsign,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        clearance=user.clearance.value,
        mfa_enabled=user.mfa_enabled,
        permissions=get_permissions_for_role(user.role.value),
        last_login=user.last_login
    )


@router.post("/register")
async def register_user(
    register_data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users:*"))
):
    """Register new user (COMMANDER only)"""
    # Validate password strength
    is_valid, error_msg = validate_password_strength(register_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Check if callsign or email already exists
    result = await db.execute(
        select(User).where(
            (User.callsign == register_data.callsign) | (User.email == register_data.email)
        )
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Callsign or email already registered"
        )

    # Create new user
    new_user = User(
        callsign=register_data.callsign,
        email=register_data.email,
        full_name=register_data.full_name,
        password_hash=hash_password(register_data.password),
        role=register_data.role,
        clearance=register_data.clearance,
        totp_secret=generate_totp_secret()
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {
        "message": "User registered successfully",
        "callsign": new_user.callsign,
        "totp_uri": get_totp_uri(new_user.totp_secret, new_user.callsign)
    }


@router.post("/mfa/enable")
async def enable_mfa(
    mfa_data: MFAEnableRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Enable MFA for current user after verifying TOTP code"""
    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP secret not generated"
        )

    if not verify_totp(user.totp_secret, mfa_data.totp_code, window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code"
        )

    user.mfa_enabled = True
    await db.commit()

    return {"message": "MFA enabled successfully"}
