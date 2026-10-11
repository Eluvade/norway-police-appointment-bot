"""Gmail helpers: read the police verification code (IMAP) and send notifications (SMTP)."""

import email
import imaplib
import logging
import os
import re
import smtplib
import sys
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

log = logging.getLogger(__name__)

IMAP_HOST = os.environ.get("IMAP_HOST") or "imap.gmail.com"
SMTP_HOST = os.environ.get("SMTP_HOST") or "smtp.gmail.com"
CODE_SENDER = "noreply-politiet@nemo-q.se"
# Subject: "Your code: KNRQ8F"; body: "...two factor authentication: KNRQ8F for your appointment..."
CODE_RE = re.compile(r":\s*([A-Z0-9]{4,12})\s*$")
BODY_CODE_RE = re.compile(r"authentica\w*:\s*([A-Z0-9]{4,12})\b", re.I)


def _creds():
    return os.environ["GMAIL_ADDRESS"], os.environ["GMAIL_APP_PASSWORD"]


def _imap():
    user, pw = _creds()
    conn = imaplib.IMAP4_SSL(IMAP_HOST)
    conn.login(user, pw)
    return conn


def _trash_folder(conn):
    """Gmail's Trash name is localized, so find it by its \\Trash special-use flag."""
    _, folders = conn.list()
    for raw in folders:
        line = raw.decode()
        if "\\Trash" in line:
            return line.rsplit(' "/" ', 1)[-1]
    return '"[Gmail]/Trash"'


def _code_message_uids(conn):
    conn.select("INBOX")
    _, data = conn.uid("search", None, f'(FROM "{CODE_SENDER}")')
    return data[0].split()


def _body_code(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            m = BODY_CODE_RE.search(part.get_payload(decode=True).decode(errors="ignore"))
            if m:
                return m.group(1)
    return None


def _received(conn, uid):
    """When the mail server received the message (the Date header can be set to anything by the sender)."""
    _, data = conn.uid("fetch", uid, "(INTERNALDATE)")
    return datetime.fromtimestamp(time.mktime(imaplib.Internaldate2tuple(data[0])), timezone.utc)


def fetch_verification_code(since: datetime, timeout: int = 180, poll: int = 5) -> str:
    """Poll the inbox for a code email received after `since` and return the code."""
    since = since - timedelta(seconds=30)  # tolerate clock skew
    deadline = time.monotonic() + timeout
    conn = _imap()  # one login per wait; re-selecting INBOX each poll picks up new mail
    try:
        while time.monotonic() < deadline:
            newest = None
            for uid in _code_message_uids(conn):
                sent = _received(conn, uid)
                if sent < since:
                    continue
                _, msg_data = conn.uid("fetch", uid, "(BODY.PEEK[])")
                msg = email.message_from_bytes(msg_data[0][1])
                if not (_subject_code(msg["Subject"]) or _body_code(msg)):
                    continue
                if newest is None or sent > newest[0]:
                    newest = (sent, msg)
            if newest:
                log.info("Got verification code from email sent at %s", newest[0])
                return _subject_code(newest[1]["Subject"]) or _body_code(newest[1])
            time.sleep(poll)
    finally:
        conn.logout()
    raise TimeoutError(f"No verification code email arrived within {timeout}s")


def _subject_code(subject):
    """The code from a verification-code subject ("Your code: X"), or None for other police emails
    such as booking confirmations, which come from the same sender."""
    subject = str(subject or "")
    m = CODE_RE.search(subject)
    return m.group(1) if m and re.search(r"code|kode", subject, re.I) else None


def _is_code_email(conn, uid):
    _, data = conn.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT)])")
    return _subject_code(email.message_from_bytes(data[0][1])["Subject"]) is not None


def cleanup_code_emails(since: datetime):
    """Move this run's verification-code emails to Trash (one arrives every run). Older ones are left
    alone, so a code you requested yourself while booking by hand isn't moved."""
    since = since - timedelta(seconds=30)
    try:
        conn = _imap()
        try:
            uids = [uid for uid in _code_message_uids(conn) if _received(conn, uid) >= since and _is_code_email(conn, uid)]
            if uids:
                trash = _trash_folder(conn)
                conn.uid("MOVE", b",".join(uids).decode(), trash)
                log.info("Moved %d code email(s) to %s", len(uids), trash)
        finally:
            conn.logout()
    except Exception:
        log.exception("Failed to clean up code emails")


def send_email(subject: str, body: str, attachments=()):
    user, pw = _creds()
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = os.environ.get("NOTIFY_TO") or user
    msg["Subject"] = subject
    msg.set_content(body)
    for path in attachments:
        path = Path(path)
        if not path.is_file():
            continue
        if path.suffix == ".png":
            msg.add_attachment(path.read_bytes(), maintype="image", subtype="png", filename=path.name)
        else:
            msg.add_attachment(path.read_bytes(), maintype="text", subtype="html", filename=path.name)
    with smtplib.SMTP_SSL(SMTP_HOST, 465) as smtp:
        smtp.login(user, pw)
        smtp.send_message(msg)
    log.info("Sent email: %s", subject)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).with_name(".env"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if "--test" in sys.argv:
        send_email("UDI checker: test email", "If you can read this, SMTP works.")
        conn = _imap()
        print("Code emails in inbox:", len(_code_message_uids(conn)))
        print("Trash folder:", _trash_folder(conn))
        conn.logout()
    elif "--read-code" in sys.argv:
        print(fetch_verification_code(datetime.now(timezone.utc) - timedelta(days=30), timeout=10))
