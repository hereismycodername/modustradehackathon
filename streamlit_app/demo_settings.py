"""Django settings for the Streamlit Community Cloud demo.

The project's own settings stay untouched; this module only adapts them to
running under a URL prefix behind Streamlit's server with an ephemeral SQLite
database. It is a demonstration stand, not a production pilot.
"""
import os
import secrets

from config.settings import *  # noqa: F403

# SQLite is only accepted by the base settings with DEBUG=1, so DEBUG is
# switched off here, after the database has been chosen: visitors must never
# see Django tracebacks with settings and local variables.
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
DEMO_MODE = True
# The base settings fall back to a public development key under DEBUG=1.
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or secrets.token_urlsafe(64)

# Streamlit Cloud sits behind its own proxy; the public host is not known in
# advance and changes with the app name.
ALLOWED_HOSTS = ["*"]
CSRF_TRUSTED_ORIGINS = [
    "https://*.streamlit.app",
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    *[origin.strip() for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()],
]

# The site is served under a prefix such as /django/ or /~/+/django/. Relative
# STATIC_URL and URL names make Django prepend that prefix itself.
STATIC_URL = "static/"
WHITENOISE_USE_FINDERS = True
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "static_storage.ScriptPrefixStaticFilesStorage"},
}
MIDDLEWARE = ["demo_middleware.TokenAddressCsrf", *MIDDLEWARE]  # noqa: F405
# Requests and the in-process notification worker write to one SQLite file;
# immediate transactions wait for each other instead of failing as "locked".
DATABASES["default"]["OPTIONS"] = {  # noqa: F405
    **DATABASES["default"].get("OPTIONS", {}),  # noqa: F405
    "transaction_mode": "IMMEDIATE",
    "init_command": "PRAGMA journal_mode=WAL;",
}
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "feedback:list"
LOGOUT_REDIRECT_URL = "login"

# The Streamlit page shows the site in a frame; streamlit_app.py replaces the
# X-Frame-Options header with a frame-ancestors policy. TLS ends at the
# Streamlit Cloud proxy, so Django itself receives plain HTTP.
X_FRAME_OPTIONS = "SAMEORIGIN"
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Every visitor arrives through the same proxy address, so the per-IP login
# limit would lock the whole jury out; the per-account limit still applies.
RATE_LOGIN_IP = int(os.getenv("RATE_LOGIN_IP", "1000"))

# Without SMTP settings letters go to the log instead of the read-only checkout.
if not EMAIL_HOST:  # noqa: F405
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
