"""
Database Backup — copies SQLite DB and emails it to the admin.
Can be triggered via /admin/backup route or scheduled externally.
"""

import os
import shutil
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime
from pathlib import Path


def create_backup(db_path):
    """Create a timestamped copy of the SQLite database.

    Returns the backup file path.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return None

    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    backup_path = backup_dir / f"pulpiq-backup-{timestamp}.db"

    # Use SQLite-safe copy (handles WAL mode)
    import sqlite3
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    src.backup(dst)
    dst.close()
    src.close()

    # Keep only the last 7 backups
    backups = sorted(backup_dir.glob("pulpiq-backup-*.db"))
    for old in backups[:-7]:
        old.unlink()

    return str(backup_path)


def email_backup(backup_path, smtp_host, smtp_port, smtp_user, smtp_pass, to_email=None):
    """Email the backup file to the admin."""
    if not smtp_user or not smtp_pass:
        print("[BACKUP] No SMTP credentials — skipping email", flush=True)
        return False

    to_email = to_email or smtp_user
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    msg = MIMEMultipart()
    msg["Subject"] = f"PulpIQ Database Backup — {timestamp}"
    msg["From"] = f"PulpIQ <{smtp_user}>"
    msg["To"] = to_email

    body = (
        f"Automated database backup from PulpIQ.\n\n"
        f"Timestamp: {timestamp}\n"
        f"File: {os.path.basename(backup_path)}\n"
        f"Size: {os.path.getsize(backup_path) / 1024:.1f} KB\n"
    )
    msg.attach(MIMEText(body, "plain"))

    with open(backup_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition",
                        f"attachment; filename={os.path.basename(backup_path)}")
        msg.attach(part)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"[BACKUP] Emailed to {to_email}", flush=True)
        return True
    except Exception as e:
        print(f"[BACKUP] Email failed: {e}", flush=True)
        return False


def run_backup(app):
    """Run a full backup: copy DB + email it."""
    db_path = app.config["DATABASE"]
    print(f"[BACKUP] Starting backup of {db_path}...", flush=True)

    backup_path = create_backup(db_path)
    if not backup_path:
        print("[BACKUP] Database file not found — nothing to back up", flush=True)
        return None

    print(f"[BACKUP] Created: {backup_path} ({os.path.getsize(backup_path) / 1024:.1f} KB)", flush=True)

    email_backup(
        backup_path,
        smtp_host=app.config["SMTP_HOST"],
        smtp_port=app.config["SMTP_PORT"],
        smtp_user=app.config["SMTP_USER"],
        smtp_pass=app.config["SMTP_PASS"],
    )

    return backup_path
