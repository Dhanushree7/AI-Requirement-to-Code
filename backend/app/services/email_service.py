import ssl
import socket
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Tuple

from backend.app.core.config import Settings, settings

logger = logging.getLogger(__name__)

class EmailService:
    @classmethod
    def _is_placeholder(cls, user: str, pwd: str) -> bool:
        placeholders = {
            "your-sender-email@gmail.com",
            "your-gmail-app-password",
            "your_email@gmail.com",
            "your_app_password",
            "example@gmail.com",
            "your-sender-email",
            "your-gmail-app"
        }
        u_lower = (user or "").lower()
        p_lower = (pwd or "").lower()
        if u_lower in placeholders or p_lower in placeholders:
            return True
        if "your-sender" in u_lower or "your-gmail" in p_lower:
            return True
        return False

    @classmethod
    def get_effective_settings(cls) -> Settings:
        """
        Return the active settings, checking disk if current in-memory credentials are placeholders.
        Preserves in-memory overrides (e.g. from tests/monkeypatch).
        """
        from backend.app.core.config import settings, Settings
        user = settings.clean_smtp_user
        pwd = settings.clean_smtp_password
        
        # If in-memory settings are empty or placeholders, check if .env has been edited on disk
        if not user or not pwd or cls._is_placeholder(user, pwd):
            try:
                disk_cfg = Settings()
                d_user = disk_cfg.clean_smtp_user
                d_pwd = disk_cfg.clean_smtp_password
                if d_user and d_pwd and not cls._is_placeholder(d_user, d_pwd):
                    return disk_cfg
            except Exception:
                pass
        return settings

    @classmethod
    def is_smtp_configured(cls) -> bool:
        """
        Check whether SMTP credentials have been configured with real, non-placeholder values.
        """
        cfg = cls.get_effective_settings()
        user = cfg.clean_smtp_user
        pwd = cfg.clean_smtp_password
        
        if not cfg.SMTP_HOST or not user or not pwd:
            return False

        if cls._is_placeholder(user, pwd):
            return False

        return True

    @classmethod
    def send_password_reset_email(cls, to_email: str, raw_token: str) -> bool:
        """Compatibility wrapper that returns True on success / dev mode, False on failure."""
        success, _ = cls.send_reset_email_detailed(to_email, raw_token)
        return success

    @classmethod
    def send_reset_email_detailed(cls, to_email: str, raw_token: str) -> Tuple[bool, str]:
        """
        Deliver an authentic password reset email to the recipient's address via Gmail SMTP (STARTTLS).
        - If SMTP credentials are configured: sends an authentic HTML & text email via Gmail SMTP.
        - If SMTP is unconfigured or credentials are placeholders: logs a configuration notice and
          allows local development testing only when ALLOW_DEV_EMAIL_LOG is explicitly enabled.
        - Never leaks credentials or exposes reset tokens to unauthorized production logs.
        Returns (success: bool, description: str).
        """
        cfg = cls.get_effective_settings()
        reset_url = f"{cfg.FRONTEND_URL.rstrip('/')}/reset-password?token={raw_token}"
        expire_minutes = cfg.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES

        subject = "Reset Your ReqToCode AI Password"
        from_address = cfg.effective_from_email
        from_header = f"{cfg.SMTP_FROM_NAME} <{from_address}>"

        # Plain text fallback
        text_body = f"""Reset Your ReqToCode AI Password

Hello,

We received a request to reset the password for your ReqToCode AI account ({to_email}).

Please open the following secure link in your web browser to choose a new password:
{reset_url}

Important Information:
• This link will expire in {expire_minutes} minutes.
• This link is single-use and will be deactivated immediately after your password is updated.
• If you did not request a password reset, you can safely ignore this email. Your password will remain unchanged and your account is secure.

Best regards,
The ReqToCode AI Team
https://reqtocode.ai
"""

        # Sleek, modern SaaS HTML template
        html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="margin: 0; padding: 32px 16px; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width: 580px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);">
    <!-- Header -->
    <tr>
      <td style="background: linear-gradient(135deg, #090e1a 0%, #1e293b 100%); padding: 32px 28px; text-align: center;">
        <div style="display: inline-block; width: 44px; height: 44px; line-height: 44px; border-radius: 12px; background: #2563eb; color: #ffffff; font-weight: 800; font-size: 16px; margin-bottom: 12px; text-align: center; box-shadow: 0 4px 8px rgba(37, 99, 235, 0.35);">
          R+C
        </div>
        <h1 style="color: #ffffff; font-size: 22px; font-weight: 700; margin: 0 0 4px 0; letter-spacing: -0.5px;">ReqToCode AI</h1>
        <p style="color: #94a3b8; font-size: 13px; margin: 0; font-weight: 500;">Intelligent Requirement Engineering Platform</p>
      </td>
    </tr>

    <!-- Body Content -->
    <tr>
      <td style="padding: 36px 32px;">
        <h2 style="font-size: 20px; font-weight: 700; color: #0f172a; margin: 0 0 16px 0;">Reset Your Password</h2>
        <p style="font-size: 14px; line-height: 1.6; color: #334155; margin: 0 0 16px 0;">
          We received a request to reset the password for your ReqToCode AI account (<strong>{to_email}</strong>).
        </p>
        <p style="font-size: 14px; line-height: 1.6; color: #334155; margin: 0 0 28px 0;">
          Click the button below to choose a new password. For security, this link is single-use and will expire in <strong>{expire_minutes} minutes</strong>.
        </p>

        <!-- CTA Button -->
        <div style="text-align: center; margin: 32px 0;">
          <a href="{reset_url}" target="_blank" style="background-color: #2563eb; color: #ffffff; padding: 14px 34px; border-radius: 10px; font-size: 14px; font-weight: 600; text-decoration: none; display: inline-block; box-shadow: 0 2px 6px rgba(37, 99, 235, 0.25);">
            Reset Password
          </a>
        </div>

        <!-- Expiration Alert Box -->
        <div style="background-color: #eff6ff; border-left: 4px solid #2563eb; border-radius: 6px; padding: 12px 16px; margin: 24px 0;">
          <p style="margin: 0; font-size: 13px; color: #1e40af; line-height: 1.5;">
            <strong>Link Validity:</strong> This link expires in <strong>{expire_minutes} minutes</strong>. Once used, it cannot be reused.
          </p>
        </div>

        <!-- Fallback URL -->
        <p style="font-size: 12px; line-height: 1.6; color: #64748b; margin: 24px 0 8px 0;">
          If the button above does not work, copy and paste this URL into your browser:
        </p>
        <p style="font-size: 11px; line-height: 1.5; color: #2563eb; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 12px; word-break: break-all; margin: 0 0 24px 0;">
          <a href="{reset_url}" style="color: #2563eb; text-decoration: underline;">{reset_url}</a>
        </p>

        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 28px 0;" />

        <!-- Security Notice -->
        <p style="font-size: 12px; line-height: 1.6; color: #64748b; margin: 0;">
          <strong>Didn't request this?</strong> If you did not make this request, you can safely ignore this email. Your password will remain unchanged and your account stays secure.
        </p>
      </td>
    </tr>

    <!-- Footer -->
    <tr>
      <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 32px; text-align: center;">
        <p style="font-size: 11px; color: #94a3b8; margin: 0 0 6px 0;">
          ReqToCode AI — Automated Software Requirement Analysis & Code Generation
        </p>
        <p style="font-size: 11px; color: #cbd5e1; margin: 0;">
          This is an automated administrative notification. Please do not reply directly to this email.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
"""

        # -------------------------------------------------------------
        # Branch 1: SMTP Configured -> Real Email Delivery
        # -------------------------------------------------------------
        if cls.is_smtp_configured():
            clean_user = cfg.clean_smtp_user
            clean_pwd = cfg.clean_smtp_password
            
            # Mask user for safe logging: e.g. "dh****@gmail.com"
            masked_user = clean_user
            if clean_user and "@" in clean_user:
                prefix, domain = clean_user.split("@", 1)
                masked_user = f"{prefix[:2]}****@{domain}" if len(prefix) > 2 else f"{prefix[0]}****@{domain}"

            logger.info(f"Connecting to Gmail SMTP server {cfg.SMTP_HOST}:{cfg.SMTP_PORT}...")

            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = from_header
                msg["To"] = to_email

                part1 = MIMEText(text_body, "plain", "utf-8")
                part2 = MIMEText(html_body, "html", "utf-8")
                msg.attach(part1)
                msg.attach(part2)

                context = ssl.create_default_context()
                server = smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=20)
                server.ehlo()
                
                if cfg.SMTP_TLS:
                    logger.info("Initiating STARTTLS encryption...")
                    server.starttls(context=context)
                    server.ehlo()

                logger.info(f"Authenticating with Gmail SMTP as '{masked_user}'...")
                server.login(clean_user, clean_pwd)
                logger.info("Gmail SMTP authentication successful.")

                logger.info(f"Dispatching reset email to recipient '{to_email}' from '{from_address}'...")
                server.sendmail(from_address, [to_email], msg.as_string())
                server.quit()

                logger.info(f"Password reset email successfully delivered to '{to_email}' via Gmail SMTP.")
                return True, "Email successfully delivered via Gmail SMTP."

            except smtplib.SMTPAuthenticationError as auth_err:
                logger.error(
                    f"\n[GMAIL SMTP AUTHENTICATION ERROR]\n"
                    f"Status Code: {auth_err.smtp_code}\n"
                    f"Server Response: {auth_err.smtp_error}\n"
                    f"Authenticated User: {masked_user}\n"
                    "DIAGNOSIS & RESOLUTION:\n"
                    "  1. Gmail requires a dedicated 16-character 'Google App Password'.\n"
                    "     Your regular personal Gmail login password WILL NOT WORK.\n"
                    "  2. To create an App Password:\n"
                    "     - Open: https://myaccount.google.com/apppasswords\n"
                    "     - (Ensure 2-Step Verification is turned ON on your Google Account)\n"
                    "     - Create an App Password labeled 'ReqToCode AI'\n"
                    "     - Copy the 16-character code (e.g., 'abcd efgh ijkl mnop')\n"
                    "  3. In backend/.env, update:\n"
                    "       SMTP_USER=<your-full-gmail-address>\n"
                    "       SMTP_PASSWORD=<the-16-character-code>\n"
                    "       SMTP_FROM_EMAIL=<your-full-gmail-address>\n"
                )
                if cfg.ENVIRONMENT == "development" and cfg.ALLOW_DEV_EMAIL_LOG:
                    logger.warning(f"[DEV FALLBACK ACTIVE - SMTP AUTH FAILED] Reset link for {to_email}: {reset_url}")
                return False, "SMTP authentication failed. Verify Google App Password."

            except (smtplib.SMTPConnectError, socket.error, TimeoutError, OSError) as conn_err:
                logger.error(
                    f"\n[GMAIL SMTP CONNECTION ERROR]\n"
                    f"Target: {cfg.SMTP_HOST}:{cfg.SMTP_PORT}\n"
                    f"Error: {type(conn_err).__name__}: {conn_err}\n"
                    "DIAGNOSIS:\n"
                    "  Could not reach smtp.gmail.com on port 587. Check internet connection and firewall."
                )
                if cfg.ENVIRONMENT == "development" and cfg.ALLOW_DEV_EMAIL_LOG:
                    logger.warning(f"[DEV FALLBACK ACTIVE - SMTP CONNECT FAILED] Reset link for {to_email}: {reset_url}")
                return False, "SMTP connection failed. Check network."

            except smtplib.SMTPSenderRefused as sender_err:
                logger.error(
                    f"\n[GMAIL SMTP SENDER ERROR]\n"
                    f"Sender '{from_address}' was refused by Gmail ({sender_err.smtp_code}).\n"
                    f"DIAGNOSIS: Gmail requires the sender to match the authenticated account ({masked_user})."
                )
                if cfg.ENVIRONMENT == "development" and cfg.ALLOW_DEV_EMAIL_LOG:
                    logger.warning(f"[DEV FALLBACK ACTIVE - SENDER REFUSED] Reset link for {to_email}: {reset_url}")
                return False, "SMTP sender address was rejected by Gmail."

            except Exception as e:
                err_type = type(e).__name__
                safe_err = str(e)
                if clean_pwd:
                    safe_err = safe_err.replace(clean_pwd, "********")
                logger.error(f"Failed to deliver password reset email via SMTP to {to_email}: {err_type}: {safe_err}")
                if cfg.ENVIRONMENT == "development" and cfg.ALLOW_DEV_EMAIL_LOG:
                    logger.warning(f"[DEV FALLBACK ACTIVE - DELIVERY ERROR] Reset link for {to_email}: {reset_url}")
                return False, f"SMTP delivery failed: {err_type}"

        # -------------------------------------------------------------
        # Branch 2: SMTP Not Configured
        # -------------------------------------------------------------
        logger.warning(
            "\n" + "=" * 76 + "\n"
            "[SMTP CONFIGURATION NOTICE - EMAIL NOT SENT]\n"
            "Gmail SMTP credentials are not configured (or still contain placeholder values).\n"
            "Real password reset emails cannot be delivered to your inbox until configured.\n\n"
            "TO RECEIVE ACTUAL EMAILS IN YOUR GMAIL INBOX:\n"
            "  1. Go to your Google Account -> Security -> 2-Step Verification -> App Passwords\n"
            "  2. Create an App Password named 'ReqToCode AI' and copy the 16-character code\n"
            "  3. Open backend/.env and set:\n"
            "       SMTP_HOST=smtp.gmail.com\n"
            "       SMTP_PORT=587\n"
            "       SMTP_USER=your-actual-email@gmail.com\n"
            "       SMTP_PASSWORD=your-16-char-app-password\n"
            "       SMTP_FROM_EMAIL=your-actual-email@gmail.com\n"
            "       SMTP_TLS=True\n"
            "=" * 76
        )

        if cfg.ENVIRONMENT == "development" and cfg.ALLOW_DEV_EMAIL_LOG:
            logger.info(
                f"[DEV TESTING MODE ENABLED] (ALLOW_DEV_EMAIL_LOG=True)\n"
                f"  Recipient:  {to_email}\n"
                f"  Reset Link: {reset_url}\n"
                f"  Expires:    {expire_minutes} minutes\n"
            )
            return True, "Development mode: Reset link generated for local testing."

        # In production with missing SMTP, log error and do not expose reset URL
        logger.error(f"Cannot dispatch password reset email to {to_email}: SMTP is not configured in production.")
        return False, "SMTP is not configured."
