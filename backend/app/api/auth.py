import datetime
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from backend.app.core.auth import (
    get_current_user,
    verify_google_oauth_token,
    create_user_session,
)
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.models import User, Session as UserSession, Entitlement

router = APIRouter(prefix="/auth", tags=["Authentication"])


class GoogleLoginRequest(BaseModel):
    id_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    registration_number: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_admin: bool
    active_entitlements_count: int = 0


class LoginResponse(BaseModel):
    token: str
    user: UserResponse


@router.post("/google-login", response_model=LoginResponse)
def google_login(
    payload: GoogleLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Authenticate with Google OAuth ID token, strictly restricted to @vitstudent.ac.in."""
    id_info = verify_google_oauth_token(payload.id_token)
    email = id_info["email"].lower().strip()
    sub = id_info.get("sub", email)
    name = id_info.get("name", "VIT Student")
    picture = id_info.get("picture")
    reg_no = id_info.get("registration_number")

    user = db.query(User).filter(User.email == email).first()
    is_admin_candidate = email in [a.lower() for a in settings.ADMIN_EMAILS]

    if not user:
        user_id = f"usr_{secrets.token_hex(12)}"
        user = User(
            id=user_id,
            google_sub=sub,
            email=email,
            registration_number=reg_no,
            full_name=name,
            avatar_url=picture,
            is_active=True,
            is_admin=is_admin_candidate,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update details on login
        user.last_login_at = datetime.datetime.utcnow()
        if picture and not user.avatar_url:
            user.avatar_url = picture
        if reg_no and not user.registration_number:
            user.registration_number = reg_no
        if is_admin_candidate and not user.is_admin:
            user.is_admin = True
        db.commit()
        db.refresh(user)

    # Issue session
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")
    session_token = create_user_session(db, user, ip_address=ip, user_agent=ua)

    # Set secure HttpOnly cookie
    response.set_cookie(
        key="writelynx_session",
        value=session_token,
        max_age=7 * 86400,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in HTTPS production
    )

    # Count active available entitlements
    entitlements_count = db.query(Entitlement).filter(
        Entitlement.user_id == user.id,
        Entitlement.status == "AVAILABLE"
    ).count()

    return {
        "token": session_token,
        "user": UserResponse(
            id=user.id,
            email=user.email,
            registration_number=user.registration_number,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            is_admin=user.is_admin,
            active_entitlements_count=entitlements_count
        )
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve authenticated VIT student profile and active entitlement count."""
    entitlements_count = db.query(Entitlement).filter(
        Entitlement.user_id == user.id,
        Entitlement.status == "AVAILABLE"
    ).count()

    return UserResponse(
        id=user.id,
        email=user.email,
        registration_number=user.registration_number,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        active_entitlements_count=entitlements_count
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Invalidate current session token."""
    token = None
    if "writelynx_session" in request.cookies:
        token = request.cookies.get("writelynx_session")
    elif "Authorization" in request.headers:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if token:
        db.query(UserSession).filter(UserSession.token == token).delete()
        db.commit()

    response.delete_cookie(key="writelynx_session")
    return {"message": "Successfully logged out."}
