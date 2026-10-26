"""Background job: nightly (or interval) URL refresh + rebuild, and housekeeping."""

import logging
import threading
import time
from datetime import datetime, timedelta

from . import build, db, epg, media, security

log = logging.getLogger("odr_spi.scheduler")

_wake = threading.Event()
_next = {"ts": None}


def wake():
    _wake.set()


def compute_next(settings, last_run, now=None):
    now = now or time.time()
    if settings.get("refresh_mode") == "interval":
        hours = max(1, min(int(settings.get("refresh_interval_hours") or 6), 24))
        base = last_run or now
        nxt = base + hours * 3600
        return nxt if nxt > now - 60 else now
    # daily: first occurrence of HH:MM (local time) after the last run
    tz = epg.get_tz(settings.get("timezone"))
    h, m = (int(x) for x in (settings.get("refresh_time") or "00:00").split(":"))
    last = last_run or now
    ref = datetime.fromtimestamp(last, tz)
    cand = ref.replace(hour=h, minute=m, second=0, microsecond=0)
    if cand.timestamp() <= last:
        cand = (ref + timedelta(days=1)).replace(hour=h, minute=m, second=0, microsecond=0)
    return cand.timestamp()


def next_run_time():
    return _next["ts"]


def loop():
    last_housekeeping = 0
    while True:
        try:
            settings = db.all_settings()
            last = float(db.get_meta("last_scheduled") or 0) or None
            if last is None:
                db.set_meta("last_scheduled", time.time())
                last = time.time()
            _next["ts"] = compute_next(settings, last)
            if time.time() >= _next["ts"]:
                db.set_meta("last_scheduled", time.time())
                if build.latest_snapshot() is not None:
                    log.info("scheduled refresh and rebuild")
                    try:
                        build.run("scheduled")
                    except RuntimeError:
                        pass  # a manual build is running; it refreshes too
                else:
                    build.refresh_all()
                continue
            if time.time() - last_housekeeping > 3600:
                last_housekeeping = time.time()
                security.purge_sessions()
                db.x("DELETE FROM audit WHERE ts < ?", (time.time() - 365 * 86400,))
                if not build.status()["running"]:
                    media.garbage_collect(build.referenced_media())
        except Exception:
            log.exception("scheduler error")
        _wake.wait(30)
        _wake.clear()


def start():
    threading.Thread(target=loop, name="scheduler", daemon=True).start()
