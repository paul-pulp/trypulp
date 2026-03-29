"""
Configuration — loaded from environment variables with sensible defaults.
"""

import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
DATABASE_PATH = os.environ.get("DATABASE_PATH", "instance/pulpiq.db")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
APP_URL = os.environ.get("APP_URL", "http://localhost:5000")
