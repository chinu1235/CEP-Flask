"""Configuration for OpportunityHub.

Values come from environment variables. A local `.env` file is loaded here,
which happens before the database connection is created in app.py.
"""
import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    # Secrets and connection details are never hardcoded. See .env.example.
    SECRET_KEY = os.getenv("SECRET_KEY")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "opportunityhub")

    # Fail fast (5 seconds) when MongoDB cannot be reached.
    MONGO_TIMEOUT_MS = 5000

    # Session cookie settings.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Set SESSION_COOKIE_SECURE=true in .env when you deploy behind HTTPS.
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # An opportunity stays "Active" for this many days after it is posted.
    OPPORTUNITY_LIFETIME_DAYS = 10

    # Reject very large request bodies (64 KB is plenty for this app).
    MAX_CONTENT_LENGTH = 64 * 1024
