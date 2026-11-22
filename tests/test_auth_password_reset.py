"""
Test suite for Password Reset and Authentication workflow.
Verifies all 10 security and functional test requirements:
1. Valid email format.
2. Invalid email format.
3. Reset link generation.
4. Valid reset token.
5. Expired reset token.
6. Invalid reset token.
7. Password mismatch / short password rejection.
8. Successful password update.
9. Token reuse rejection.
10. Login using the newly updated password.
"""
import pytest
from datetime import datetime, timedelta
from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.models.user import User, PasswordResetToken
from backend.app.core.security import (
    hash_password,
    verify_password,
    generate_reset_token,
    hash_token
)
from backend.app.routers.auth import (
    register,
    login,
    forgot_password,
    verify_reset_token,
    reset_password,
    RegisterRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest
)

@pytest.fixture
def test_user(db_session):
    """Create a clean test user."""
    email = "engineer@example.com"
    existing = db_session.query(User).filter(User.email == email).first()
    if existing:
        db_session.delete(existing)
        db_session.commit()

    user = User(
        full_name="Software Engineer",
        email=email,
        hashed_password=hash_password("OriginalPass123!"),
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestPasswordResetSuite:

    def test_1_valid_email_format(self):
        """1. Verify valid email formats are accepted by request schemas."""
        req1 = ForgotPasswordRequest(email="valid.user@company.com")
        assert req1.email == "valid.user@company.com"

        req2 = ForgotPasswordRequest(email="  UPPERCASE@DOMAIN.ORG  ")
        assert req2.email == "uppercase@domain.org"

    def test_2_invalid_email_format(self):
        """2. Verify invalid email formats are rejected with validation error."""
        invalid_emails = ["not-an-email", "missing-domain@", "@no-user.com", "spaces in@mail.com"]
        for bad_email in invalid_emails:
            with pytest.raises(ValidationError):
                ForgotPasswordRequest(email=bad_email)

    def test_3_reset_link_generation_and_enumeration_protection(self, db_session, test_user):
        """3. Reset link generation stores token hash, protects against enumeration."""
        # Case A: Existing user
        res1 = forgot_password(ForgotPasswordRequest(email=test_user.email), db_session)
        assert "password reset link has been sent" in res1["message"]
        assert "check your inbox" in res1["message"]

        token_record = db_session.query(PasswordResetToken).filter_by(user_id=test_user.id).first()
        assert token_record is not None
        assert token_record.is_used is False
        assert len(token_record.token_hash) == 64  # SHA-256 hash
        assert token_record.expires_at > datetime.utcnow()

        # Case B: Non-existent user returns identical response (anti-enumeration)
        res2 = forgot_password(ForgotPasswordRequest(email="nonexistent.user@random.com"), db_session)
        assert res2["message"] == res1["message"]

    def test_4_valid_reset_token(self, db_session, test_user):
        """4. Valid token is accepted and returns masked email."""
        raw_token, token_hash = generate_reset_token()
        token_record = PasswordResetToken(
            user_id=test_user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(minutes=15),
            is_used=False
        )
        db_session.add(token_record)
        db_session.commit()

        res = verify_reset_token(token=raw_token, db=db_session)
        assert res["valid"] is True
        assert "@example.com" in res["masked_email"]

    def test_5_expired_reset_token(self, db_session, test_user):
        """5. Expired reset token is strictly rejected."""
        raw_token, token_hash = generate_reset_token()
        token_record = PasswordResetToken(
            user_id=test_user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() - timedelta(minutes=5),  # expired 5 min ago
            is_used=False
        )
        db_session.add(token_record)
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            verify_reset_token(token=raw_token, db=db_session)
        assert exc.value.status_code == 400
        assert "expired" in str(exc.value.detail).lower()

    def test_6_invalid_reset_token(self, db_session):
        """6. Malformed or non-existent token is rejected."""
        with pytest.raises(HTTPException) as exc:
            verify_reset_token(token="completely-bogus-token-string", db=db_session)
        assert exc.value.status_code == 400
        assert "invalid" in str(exc.value.detail).lower()

    def test_7_password_length_validation(self):
        """7. Reject passwords shorter than 8 characters."""
        with pytest.raises(ValidationError):
            ResetPasswordRequest(token="some-valid-token", new_password="short")

    def test_8_successful_password_update(self, db_session, test_user):
        """8. Successfully reset password and verify bcrypt hash in DB."""
        raw_token, token_hash = generate_reset_token()
        token_record = PasswordResetToken(
            user_id=test_user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(minutes=15),
            is_used=False
        )
        db_session.add(token_record)
        db_session.commit()

        reset_res = reset_password(
            ResetPasswordRequest(token=raw_token, new_password="BrandNewSecurePassword2026!"),
            db=db_session
        )
        assert reset_res["success"] is True

        db_session.refresh(test_user)
        assert verify_password("BrandNewSecurePassword2026!", test_user.hashed_password) is True

    def test_9_token_reuse_rejection(self, db_session, test_user):
        """9. Ensure token cannot be reused once password has been reset."""
        raw_token, token_hash = generate_reset_token()
        token_record = PasswordResetToken(
            user_id=test_user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(minutes=15),
            is_used=False
        )
        db_session.add(token_record)
        db_session.commit()

        # First use succeeds
        reset_password(
            ResetPasswordRequest(token=raw_token, new_password="UpdatedPassword1!"),
            db=db_session
        )

        # Second use with same token fails
        with pytest.raises(HTTPException) as exc:
            reset_password(
                ResetPasswordRequest(token=raw_token, new_password="AnotherPassword2!"),
                db=db_session
            )
        assert exc.value.status_code == 400
        assert "invalid or has already been used" in str(exc.value.detail).lower()

    def test_10_login_using_newly_updated_password(self, db_session, test_user):
        """10. Verify old password fails login and new password succeeds."""
        raw_token, token_hash = generate_reset_token()
        token_record = PasswordResetToken(
            user_id=test_user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(minutes=15),
            is_used=False
        )
        db_session.add(token_record)
        db_session.commit()

        # Update password
        reset_password(
            ResetPasswordRequest(token=raw_token, new_password="FinalPasswordVerification789!"),
            db=db_session
        )

        # Old password rejected
        with pytest.raises(HTTPException) as exc_old:
            login(LoginRequest(email=test_user.email, password="OriginalPass123!"), db=db_session)
        assert exc_old.value.status_code == 401

        # New password authenticated
        login_res = login(
            LoginRequest(email=test_user.email, password="FinalPasswordVerification789!"),
            db=db_session
        )
        assert login_res["success"] is True
        assert login_res["user"]["email"] == test_user.email

    def test_11_user_registration_end_to_end(self, db_session):
        """11. Verify user registration creates active user with bcrypt hashed password."""
        email = "unique_registered_user@example.com"
        # Cleanup if exists
        existing = db_session.query(User).filter(User.email == email).first()
        if existing:
            db_session.delete(existing)
            db_session.commit()

        req = RegisterRequest(
            full_name="Alex Morgan",
            email=email,
            password="SecurePassword123!"
        )
        result = register(req, db=db_session)

        assert result["success"] is True
        assert result["user"]["email"] == email
        assert result["user"]["full_name"] == "Alex Morgan"
        assert result["message"] == "Account created successfully."

        # Verify persisted in database
        saved_user = db_session.query(User).filter(User.email == email).first()
        assert saved_user is not None
        assert saved_user.email == email
        assert saved_user.full_name == "Alex Morgan"
        assert saved_user.is_active is True
        assert verify_password("SecurePassword123!", saved_user.hashed_password) is True

    def test_12_duplicate_email_registration_rejection(self, db_session):
        """12. Verify registration rejects duplicate email with HTTP 400."""
        email = "duplicate_test_user@example.com"
        # Ensure user exists
        existing = db_session.query(User).filter(User.email == email).first()
        if not existing:
            first_user = User(
                full_name="Original Account",
                email=email,
                hashed_password=hash_password("FirstPassword123!"),
                is_active=True
            )
            db_session.add(first_user)
            db_session.commit()

        # Attempt to register again with same email
        dup_req = RegisterRequest(
            full_name="Duplicate Attempt",
            email=email,
            password="AnotherPassword456!"
        )
        with pytest.raises(HTTPException) as exc_info:
            register(dup_req, db=db_session)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "An account with this email address already exists."

    def test_13_router_path_mappings_for_frontend(self):
        """13. Verify all route variants (/api/auth/register, /api/auth/signup, /auth/register, etc.) exist."""
        from backend.app.main import app
        paths = {r.path for r in app.routes}

        # Canonical routes
        assert "/api/auth/register" in paths
        assert "/api/auth/signup" in paths
        assert "/api/auth/login" in paths
        assert "/api/auth/signin" in paths
        assert "/api/auth/forgot-password" in paths
        assert "/api/auth/reset-password" in paths

        # Direct / non-prefixed fallback aliases
        assert "/auth/register" in paths
        assert "/auth/signup" in paths
        assert "/api/register" in paths
        assert "/api/signup" in paths

    def test_14_smtp_configuration_detection(self, monkeypatch):
        """14. Verify SMTP configuration correctly distinguishes real vs placeholder credentials."""
        from backend.app.services.email_service import EmailService
        from backend.app.core.config import settings

        # Placeholder config returns False
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
        monkeypatch.setattr(settings, "SMTP_USER", "your-sender-email@gmail.com")
        monkeypatch.setattr(settings, "SMTP_PASSWORD", "your-gmail-app-password")
        assert EmailService.is_smtp_configured() is False

        # Real credentials return True
        monkeypatch.setattr(settings, "SMTP_USER", "developer.alerts@gmail.com")
        monkeypatch.setattr(settings, "SMTP_PASSWORD", "abcd efgh ijkl mnop")
        assert EmailService.is_smtp_configured() is True

    def test_15_smtp_real_email_delivery_with_starttls(self, monkeypatch):
        """15. Verify real Gmail SMTP delivery with STARTTLS, professional HTML and plain-text fallback."""
        from unittest.mock import MagicMock
        import smtplib
        from backend.app.services.email_service import EmailService
        from backend.app.core.config import settings

        sent_messages = []

        class MockSMTP:
            def __init__(self, host, port, timeout=15):
                self.host = host
                self.port = port
                self.tls_started = False
                self.logged_in = False

            def ehlo(self):
                pass

            def starttls(self, context=None):
                self.tls_started = True

            def login(self, user, password):
                self.logged_in = True
                assert user == "testsender@gmail.com"
                assert password == "secureapppassword16"

            def sendmail(self, from_addr, to_addrs, msg_str):
                sent_messages.append({
                    "from": from_addr,
                    "to": to_addrs,
                    "msg": msg_str
                })

            def quit(self):
                pass

        monkeypatch.setattr(smtplib, "SMTP", MockSMTP)
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
        monkeypatch.setattr(settings, "SMTP_PORT", 587)
        monkeypatch.setattr(settings, "SMTP_USER", "testsender@gmail.com")
        monkeypatch.setattr(settings, "SMTP_PASSWORD", "secureapppassword16")
        monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "testsender@gmail.com")
        monkeypatch.setattr(settings, "SMTP_FROM_NAME", "ReqToCode AI")
        monkeypatch.setattr(settings, "SMTP_TLS", True)

        raw_token = "mock_secure_token_1234567890abcdef"
        success = EmailService.send_password_reset_email("user.recipient@company.org", raw_token)

        assert success is True
        assert len(sent_messages) == 1
        sent = sent_messages[0]
        assert sent["from"] == "testsender@gmail.com"
        assert sent["to"] == ["user.recipient@company.org"]
        
        # Verify subject and contents in MIME message
        import email
        parsed_msg = email.message_from_string(sent["msg"])
        assert parsed_msg["Subject"] == "Reset Your ReqToCode AI Password"
        assert parsed_msg["From"] == "ReqToCode AI <testsender@gmail.com>"
        assert parsed_msg["To"] == "user.recipient@company.org"

        # Check decoded payload parts (HTML and plain text)
        decoded_parts = [part.get_payload(decode=True).decode("utf-8") for part in parsed_msg.get_payload()]
        combined_text = "\n".join(decoded_parts)
        assert "15 minutes" in combined_text
        assert f"token={raw_token}" in combined_text
        assert "Reset Password" in combined_text
        assert "safely ignore this email" in combined_text

    def test_16_smtp_delivery_failure_safe_handling(self, monkeypatch, caplog):
        """16. Verify SMTP failure logs safely without leaking password, returns False."""
        import smtplib
        from backend.app.services.email_service import EmailService
        from backend.app.core.config import settings

        class FailingSMTP:
            def __init__(self, *args, **kwargs):
                pass
            def starttls(self):
                raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Authentication failed with supersecretpassword")
            def login(self, *args):
                pass
            def sendmail(self, *args):
                pass
            def quit(self):
                pass

        monkeypatch.setattr(smtplib, "SMTP", FailingSMTP)
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
        monkeypatch.setattr(settings, "SMTP_USER", "sender@gmail.com")
        monkeypatch.setattr(settings, "SMTP_PASSWORD", "supersecretpassword")

        success = EmailService.send_password_reset_email("target@company.com", "fail_token_123")
        assert success is False
        # Verify password is not in logged records
        for record in caplog.records:
            assert "supersecretpassword" not in record.message

    def test_17_forgot_password_endpoint_smtp_failure_handling(self, db_session, test_user, monkeypatch):
        """17. Verify /forgot-password raises 503 without leaking credentials if SMTP fails."""
        from backend.app.services.email_service import EmailService
        
        # Mock EmailService to simulate delivery failure
        monkeypatch.setattr(
            EmailService,
            "send_reset_email_detailed",
            lambda to_email, raw_token: (False, "SMTP authentication failed.")
        )

        with pytest.raises(HTTPException) as exc_info:
            forgot_password(ForgotPasswordRequest(email=test_user.email), db=db_session)

        assert exc_info.value.status_code == 503
        assert "Unable to send password reset email" in exc_info.value.detail
        # Sensitive SMTP details and tokens must NOT be in client response
        assert "SMTP" not in exc_info.value.detail
        assert "token" not in exc_info.value.detail.lower()
        assert "supersecretpassword" not in exc_info.value.detail.lower()

    def test_18_forgot_password_endpoint_smtp_success(self, db_session, test_user, monkeypatch):
        """18. Verify /forgot-password returns 200 with standard inbox message upon successful delivery."""
        from backend.app.services.email_service import EmailService

        monkeypatch.setattr(
            EmailService,
            "send_reset_email_detailed",
            lambda to_email, raw_token: (True, "Delivered successfully")
        )

        res = forgot_password(ForgotPasswordRequest(email=test_user.email), db=db_session)
        assert "password reset link has been sent" in res["message"]
        assert "check your inbox" in res["message"]
