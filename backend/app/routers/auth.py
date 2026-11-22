import re
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import (
    hash_password, verify_password, generate_reset_token, hash_token,
    create_access_token, get_current_user
)
from backend.app.models.user import User, PasswordResetToken
from backend.app.services.email_service import EmailService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# ---------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------

class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Please provide a valid email address.")
        return clean

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Reset token is required.")
        return clean

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return v

class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Please provide a valid email address.")
        return clean

class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if len(clean) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        return clean

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Please provide a valid email address.")
        return clean

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

def _mask_email(email: str) -> str:
    """Mask email for safe verification display without enumeration leak."""
    if "@" not in email:
        return "user@***"
    user_part, domain = email.split("@", 1)
    if len(user_part) <= 2:
        masked_user = user_part[0] + "***"
    else:
        masked_user = user_part[0] + "***" + user_part[-1]
    return f"{masked_user}@{domain}"

# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------

@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Initiate a secure password recovery request.
    Always returns a generic success message to prevent account enumeration.
    """
    generic_response = {
        "message": "If an account exists with this email address, a password reset link has been sent. Please check your inbox."
    }

    user = db.query(User).filter(User.email == req.email).first()
    if not user or not user.is_active:
        logger.info(f"Password reset requested for non-existent/inactive email: {req.email}")
        return generic_response

    # Basic rate limiting / cooldown per user account
    cooldown_cutoff = datetime.utcnow() - timedelta(seconds=settings.PASSWORD_RESET_COOLDOWN_SECONDS)
    recent_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.created_at >= cooldown_cutoff
    ).first()

    if recent_token:
        logger.warning(f"Password reset rate limit hit for {req.email}. Cooldown active.")
        return generic_response

    # Revoke any prior unused tokens for this user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.is_used == False
    ).update({"is_used": True})

    # Generate cryptographically secure token
    raw_token, token_hash = generate_reset_token()
    expires_at = datetime.utcnow() + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

    reset_record = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        is_used=False
    )
    db.add(reset_record)
    db.commit()

    # Deliver reset email (or log to console in dev mode)
    success, reason = EmailService.send_reset_email_detailed(user.email, raw_token)
    if not success:
        logger.error(f"Password reset email could not be sent to {user.email}: {reason}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to send password reset email at this time. Please check your email delivery configuration, or try again later."
        )

    return generic_response

@router.get("/verify-reset-token")
def verify_reset_token(token: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    """
    Verify whether a reset token is valid, unexpired, and unused.
    """
    token_hash = hash_token(token)
    reset_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash
    ).first()

    if not reset_record or reset_record.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link is invalid or has already been used. Please request a new one."
        )

    if reset_record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link has expired (links are valid for 15 minutes). Please request a new one."
        )

    user = db.query(User).filter(User.id == reset_record.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account associated with this token is invalid."
        )

    return {
        "valid": True,
        "masked_email": _mask_email(user.email),
        "message": "Token is valid. You may now set a new password."
    }

@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Reset user password using a verified single-use token.
    Invalidates the token immediately upon update.
    """
    token_hash = hash_token(req.token)
    reset_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash
    ).first()

    if not reset_record or reset_record.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link is invalid or has already been used. Please request a new one."
        )

    if reset_record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link has expired. Please request a new one."
        )

    user = db.query(User).filter(User.id == reset_record.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Associated user account could not be found."
        )

    # Securely hash new password with bcrypt
    user.hashed_password = hash_password(req.new_password)
    user.updated_at = datetime.utcnow()

    # Invalidate token and all previous tokens for this user
    reset_record.is_used = True
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id
    ).update({"is_used": True})

    db.commit()
    logger.info(f"Password successfully reset for user: {user.email}")

    return {
        "success": True,
        "message": "Your password has been successfully reset. You may now sign in with your new password."
    }

@router.post("/register", status_code=status.HTTP_201_CREATED)
@router.post("/signup", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account with hashed password."""
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    user = User(
        full_name=req.full_name,
        email=req.email,
        hashed_password=hash_password(req.password),
        is_active=True,
        is_superuser=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id, "email": user.email})

    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_superuser": user.is_superuser
        },
        "message": "Account created successfully."
    }

@router.post("/login")
@router.post("/signin")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with email and bcrypt password verification."""
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    token = create_access_token({"sub": user.id, "email": user.email})

    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_superuser": user.is_superuser
        },
        "message": "Login successful."
    }

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve current authenticated user profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_superuser": current_user.is_superuser,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at
    }

# ---------------------------------------------------------
# Direct Un-prefixed Alias Router (supports /register, /signup, etc.)
# ---------------------------------------------------------
direct_auth_router = APIRouter(tags=["Authentication"])
direct_auth_router.add_api_route("/register", register, methods=["POST"], status_code=status.HTTP_201_CREATED)
direct_auth_router.add_api_route("/signup", register, methods=["POST"], status_code=status.HTTP_201_CREATED)
direct_auth_router.add_api_route("/login", login, methods=["POST"])
direct_auth_router.add_api_route("/signin", login, methods=["POST"])
direct_auth_router.add_api_route("/me", get_me, methods=["GET"])
direct_auth_router.add_api_route("/forgot-password", forgot_password, methods=["POST"])
direct_auth_router.add_api_route("/verify-reset-token", verify_reset_token, methods=["GET"])
direct_auth_router.add_api_route("/reset-password", reset_password, methods=["POST"])

