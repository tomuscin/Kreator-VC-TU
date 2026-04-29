"""
Email sender module for Kreator CV TU.
Uses SMTP over SSL (port 465) — smtp.gmail.com on Render, mail.tomaszuscinski.pl locally.
"""

import os
import smtplib
import ssl
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import certifi
from dotenv import load_dotenv

load_dotenv()

# Use .get() with defaults — KeyError at import time crashes the whole app on Render.
# Missing critical vars are caught lazily inside send_cv().
SMTP_HOST      = os.environ.get("SMTP_HOST", "mail.tomaszuscinski.pl")
SMTP_PORT      = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER      = os.environ.get("SMTP_USER", "tomasz@tomaszuscinski.pl")
SMTP_PASSWORD  = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM      = os.environ.get("SMTP_FROM", SMTP_USER)
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Tomasz Uściński")


def send_cv(
    to: str,
    subject: str,
    body_html: str,
    docx_bytes: bytes,
    docx_filename: str,
    body_plain: str | None = None,
) -> None:
    """
    Sends a CV email with a .docx attachment via SMTP SSL.

    Args:
        to:            Recipient email address.
        subject:       Email subject.
        body_html:     HTML body of the email.
        docx_bytes:    Raw bytes of the .docx file to attach.
        docx_filename: Filename shown in the email attachment.
        body_plain:    Optional plain text fallback (auto-generated if omitted).

    Raises:
        smtplib.SMTPException: On SMTP errors.
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        raise RuntimeError("SMTP credentials are not configured.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    # Properly encode non-ASCII display name (Polish chars) per RFC 2047 / RFC 5322
    if SMTP_FROM_NAME:
        encoded_name  = Header(SMTP_FROM_NAME, "utf-8").encode()
        from_address  = f"{encoded_name} <{SMTP_FROM}>"
    else:
        from_address  = SMTP_FROM
    msg["From"] = from_address
    msg["To"]   = to

    plain = body_plain or _strip_html(body_html)
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    # Attach .docx
    attachment = MIMEApplication(docx_bytes, _subtype="vnd.openxmlformats-officedocument.wordprocessingml.document")
    attachment.add_header("Content-Disposition", "attachment", filename=docx_filename)

    outer = MIMEMultipart("mixed")
    outer["Subject"] = msg["Subject"]
    outer["From"]    = msg["From"]
    outer["To"]      = msg["To"]
    outer.attach(msg)
    outer.attach(attachment)

    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=30) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to], outer.as_string())
    except smtplib.SMTPAuthenticationError:
        raise RuntimeError(
            "Błąd logowania SMTP. Sprawdź SMTP_USER i SMTP_PASSWORD / Google App Password."
        )
    except (TimeoutError, ConnectionRefusedError, OSError) as exc:
        raise RuntimeError(
            f"Nie udało się połączyć z serwerem SMTP ({SMTP_HOST}:{SMTP_PORT}). "
            "Sprawdź SMTP_HOST, SMTP_PORT i konfigurację TLS/SSL."
        ) from exc


def test_connection() -> bool:
    """
    Tests SMTP connection and authentication without sending any message.

    Returns:
        True if connection and login succeed.

    Raises:
        smtplib.SMTPAuthenticationError: On bad credentials.
        smtplib.SMTPException: On other SMTP errors.
    """
    context = ssl.create_default_context(cafile=certifi.where())
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
    return True


def _strip_html(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", html).strip()
