import datetime
import re
import secrets
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.models import User, Session as UserSession, UserRestriction

security_bearer = HTTPBearer(auto_error=False)
REG_NO_PATTERN = re.compile(r"^([0-9]{2}[a-zA-Z]{3}[0-9]{4})", re.IGNORECASE)


def extract_registration_number(email: str) -> Optional[str]:
    """Extract standard VIT registration number (e.g. 21BCE1234) from email username."""
    username = email.split("@")[0].strip()
    match = REG_NO_PATTERN.match(username)
    if match:
        return match.group(1).upper()
    return None


def verify_vit_email_domain(email: str, hd: Optional[str] = None) -> bool:
    """Strictly verify that the email and hosted domain belong to vitstudent.ac.in."""
    email_lower = email.lower().strip()
    expected_domain = settings.ALLOWED_STUDENT_DOMAIN.lower()
    
    # Domain must end with @vitstudent.ac.in
    if not email_lower.endswith(f"@{expected_domain}"):
        return False
        
    # Hosted domain claim in OAuth token must match
    if hd is not None and hd.lower() != expected_domain:
        return False
        
    return True


def verify_google_oauth_token(id_token_str: str) -> dict:
    """Verify Google OAuth token and ensure VIT student domain claim."""
    id_token_str = (id_token_str or "").strip()
    if not id_token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing OAuth token."
        )

    # 1. Mock Authentication Mode for automated testing & CI/CD
    if id_token_str.startswith("mock-") or id_token_str.startswith("test-"):
        if settings.ENVIRONMENT in ("production", "staging") or not settings.TEST_MODE_MOCK_AUTH:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Mock authentication is strictly disabled in production/staging environments."
            )

        parts = id_token_str.split(":")
        # Format can be mock-token:<email> or mock-token:<reg_no>:<email>
        if len(parts) >= 3:
            email = parts[2].strip()
            reg_no = parts[1].strip()
        elif len(parts) == 2:
            email = parts[1].strip()
            reg_no = extract_registration_number(email)
        else:
            email = "21bce1001@vitstudent.ac.in"
            reg_no = "21BCE1001"

        if not verify_vit_email_domain(email, hd="vitstudent.ac.in" if email.endswith("@vitstudent.ac.in") else "other"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted to Vellore Institute of Technology students (@{settings.ALLOWED_STUDENT_DOMAIN})."
            )

        return {
            "email": email.lower(),
            "name": f"VIT Student {reg_no or 'Member'}",
            "sub": f"mock-sub-{email.lower()}",
            "hd": "vitstudent.ac.in",
            "registration_number": reg_no,
        }

    # 2. Production Google ID Token Verification
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests

        request_adapter = requests.Request()
        id_info = id_token.verify_oauth2_token(
            id_token_str,
            request_adapter,
            settings.GOOGLE_CLIENT_ID
        )

        # Require verified email
        if not id_info.get("email_verified", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Google account email is not verified."
            )

        email = id_info.get("email", "").lower().strip()
        hd = id_info.get("hd", "").lower().strip()

        if not verify_vit_email_domain(email, hd):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted to Vellore Institute of Technology students (@{settings.ALLOWED_STUDENT_DOMAIN})."
            )

        reg_no = extract_registration_number(email)
        id_info["registration_number"] = reg_no
        return id_info

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google ID token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OAuth verification failed: {str(e)}"
        )


def create_user_session(
    db: Session,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> str:
    """Create a cryptographically secure 7-day session token."""
    token = secrets.token_urlsafe(32)
    session_id = f"sess_{secrets.token_hex(12)}"
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=7)

    db_session = UserSession(
        id=session_id,
        user_id=user.id,
        token=token,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at,
    )
    db.add(db_session)
    db.commit()
    return token


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    """Authorize current user via Bearer token or HttpOnly session cookie."""
    token = None
    if credentials:
        token = credentials.credentials
    elif "writelynx_session" in request.cookies:
        token = request.cookies.get("writelynx_session")
    elif "Authorization" in request.headers:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in with your VIT student account."
        )

    # Validate active session
    user_session = db.query(UserSession).filter(
        UserSession.token == token,
        UserSession.expires_at > datetime.datetime.utcnow()
    ).first()

    if not user_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or is invalid. Please sign in again."
        )

    user = db.query(User).filter(User.id == user_session.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or disabled."
        )

    # Check for active account restrictions
    active_restriction = db.query(UserRestriction).filter(
        UserRestriction.user_id == user.id,
        UserRestriction.is_active == True,
    ).first()

    if active_restriction:
        if not active_restriction.expires_at or active_restriction.expires_at > datetime.datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account restricted: {active_restriction.reason}"
            )

    return user


def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Retrieve user if valid session exists, otherwise return None."""
    try:
        return get_current_user(request, credentials, db)
    except HTTPException:
        return None


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Enforce administrator privileges."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required."
        )
    return user
