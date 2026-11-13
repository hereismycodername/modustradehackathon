"""Streamlit Community Cloud entry point.

`streamlit run streamlit_app/streamlit_app.py` finds the `st.App` below and
serves two things from one server:

* `/` — a small Streamlit page (page.py) that shows the site in a frame;
* `/django/` — the unchanged Django application with every feature.

The database is SQLite in a temporary directory. It is created and filled
with the demo data on start, so it resets whenever Streamlit restarts the app.
"""
from __future__ import annotations

import logging
import os
import re
import sys
import tempfile
import threading
import time
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import streamlit as st
from starlette.routing import Mount
from streamlit import config as streamlit_config

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for entry in (str(HERE), str(ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

SITE = "/django"
PREFIX_COOKIE = "modus_prefix"
SAFE_PREFIX = re.compile(r"^(/[A-Za-z0-9._~+-]+)*$")
FRAME_POLICY = b"frame-ancestors 'self' https://*.streamlit.app https://share.streamlit.io"
log = logging.getLogger("modustrade.streamlit")


def _export_secrets() -> None:
    """Expose plain top-level Streamlit secrets as environment variables."""
    try:
        items = dict(st.secrets)
    except Exception:  # no secrets configured
        return
    for key, value in items.items():
        if isinstance(value, (str, int, float, bool)):
            os.environ.setdefault(key, str(value))


def _configure() -> None:
    _export_secrets()
    data = Path(os.getenv("MODUS_DATA_DIR") or Path(tempfile.gettempdir()) / "modustrade-demo")
    data.mkdir(parents=True, exist_ok=True)
    os.environ["DJANGO_SETTINGS_MODULE"] = "demo_settings"
    # The base settings accept SQLite only with DEBUG=1; demo_settings then
    # turns DEBUG off again for every request.
    os.environ["DEBUG"] = "1"
    os.environ["DB_ENGINE"] = "sqlite"
    os.environ["DEMO_MODE"] = "1"
    os.environ.setdefault("SQLITE_PATH", str(data / "db.sqlite3"))
    os.environ.setdefault("ATTACHMENTS_ROOT", str(data / "attachments"))
    os.environ.setdefault("DEMO_PASSWORD", "ModusDemo2026!")


def _prepare_database() -> None:
    """Migrate and load the demo data before the first request.

    uvicorn imports this module inside its event loop, where Django refuses
    synchronous database work, so the setup runs in a thread and is awaited.
    """
    failure: list[BaseException] = []

    def run() -> None:
        from django.core.management import call_command
        from django.db import connections

        try:
            call_command("migrate", interactive=False, verbosity=0)
            for command in ("load_demo", "load_hackathon_demo", "load_pavlodar_demo"):
                call_command(command, verbosity=0)
        except BaseException as exc:  # re-raised in the importing thread
            failure.append(exc)
        finally:
            connections.close_all()

    thread = threading.Thread(target=run, name="demo-setup")
    thread.start()
    thread.join()
    if failure:
        raise failure[0]


def _worker() -> None:
    """In-process replacement for `manage.py process_outbox --loop`."""
    from django.db import close_old_connections
    from django.utils import timezone

    from feedback.models import WorkerHeartbeat
    from feedback.services import process_outbox

    while True:
        try:
            counts = process_outbox(limit=100)
            WorkerHeartbeat.objects.update_or_create(
                key="default", defaults={"last_seen": timezone.now(), "last_error": "", "last_counts": counts})
        except Exception as exc:  # keep delivering after a transient error
            log.warning("Outbox pass failed: %s", type(exc).__name__)
        finally:
            close_old_connections()
        time.sleep(5)


_configure()
import django  # noqa: E402

django.setup()
_prepare_database()
threading.Thread(target=_worker, name="outbox-worker", daemon=True).start()

from django.core.asgi import get_asgi_application  # noqa: E402

_django = get_asgi_application()


def _headers(scope) -> dict[str, str]:
    return {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}


def _clean(prefix: str | None) -> str | None:
    if prefix is None:
        return None
    prefix = prefix.rstrip("/")
    return prefix if len(prefix) <= 100 and SAFE_PREFIX.match(prefix) else None


def _browser_prefix(headers: dict[str, str]) -> tuple[str, bool]:
    """Path the browser sees in front of /django; True when it should be remembered.

    Locally the site lives at /django/. Streamlit Cloud serves the app under
    a path such as /~/+/ and its proxy removes that part before the request
    arrives, so Django has to learn it from the page that opened the site.
    """
    configured = _clean(os.getenv("STREAMLIT_PATH_PREFIX"))
    if configured is not None:
        return configured, False
    referer = urlsplit(headers.get("referer", ""))
    hosts = {headers.get("host", ""), headers.get("x-forwarded-host", "")} - {""}
    if referer.path and (referer.netloc in hosts or referer.netloc.endswith(".streamlit.app")):
        marker = referer.path.find(SITE + "/")
        if marker < 0 and referer.path.endswith(SITE):
            marker = len(referer.path) - len(SITE)
        # Without the marker the referer is the Streamlit page framing the site.
        found = _clean(referer.path[:marker] if marker >= 0 else referer.path)
        if found is not None:
            return found, True
    cookie = SimpleCookie()
    try:
        cookie.load(headers.get("cookie", ""))
    except Exception:
        pass
    if PREFIX_COOKIE in cookie:
        remembered = _clean(unquote(cookie[PREFIX_COOKIE].value))
        if remembered is not None:
            return remembered, False
    host = headers.get("x-forwarded-host") or headers.get("host", "")
    return ("/~/+" if host.endswith(".streamlit.app") else ""), False


async def django_site(scope, receive, send):
    if scope["type"] != "http":
        return await _django(scope, receive, send)
    prefix, remember = _browser_prefix(_headers(scope))
    mount_root = scope.get("root_path", "")
    path = scope["path"]
    rest = path[len(mount_root):] if path.startswith(mount_root) else path
    # When the prefix already reaches the server, it is not added twice.
    browser_root = mount_root if mount_root.startswith(prefix) else prefix + mount_root
    scope = {**scope, "root_path": browser_root, "path": browser_root + rest}
    scope.pop("raw_path", None)

    async def send_adapted(message):
        if message["type"] == "http.response.start":
            # ASGI expects lowercase names. Django keeps "Content-Length", and
            # Streamlit's gzip layer would then add a second, conflicting one.
            headers = [(bytes(k).lower(), bytes(v)) for k, v in message.get("headers", [])]
            # The site is shown inside the Streamlit page; allow only that frame.
            headers = [(k, v) for k, v in headers if k != b"x-frame-options"]
            headers.append((b"content-security-policy", FRAME_POLICY))
            if remember:
                cookie = f"{PREFIX_COOKIE}={quote(prefix, safe='')}; Path=/; SameSite=Lax; HttpOnly"
                headers.append((b"set-cookie", cookie.encode("latin-1")))
            message = {**message, "headers": headers}
        await send(message)

    return await _django(scope, receive, send_adapted)


# Streamlit does not place custom routes under server.baseUrlPath itself.
_base = (streamlit_config.get_option("server.baseUrlPath") or "").strip("/")
app = st.App("page.py", routes=[Mount((f"/{_base}" if _base else "") + SITE, app=django_site)])
