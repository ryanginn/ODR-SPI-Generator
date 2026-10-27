"""SQLite storage."""

import json
import os
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL DEFAULT '',
    pw_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'editor', 'station')),
    can_apply INTEGER NOT NULL DEFAULT 0,
    disabled INTEGER NOT NULL DEFAULT 0,
    must_change_pw INTEGER NOT NULL DEFAULT 0,
    failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until REAL NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    last_login REAL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf TEXT NOT NULL,
    created_at REAL NOT NULL,
    last_seen REAL NOT NULL,
    expires_at REAL NOT NULL,
    ip TEXT,
    user_agent TEXT
);

CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY,
    short_name TEXT NOT NULL DEFAULT '',
    medium_name TEXT NOT NULL DEFAULT '',
    long_name TEXT NOT NULL DEFAULT '',
    short_description TEXT NOT NULL DEFAULT '',
    long_description TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    genres TEXT NOT NULL DEFAULT '[]',
    bearers TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1,
    epg_enabled INTEGER NOT NULL DEFAULT 0,
    epg_feed_url TEXT NOT NULL DEFAULT '',
    epg_feed_type TEXT NOT NULL DEFAULT 'xmltv',
    epg_feed_channel TEXT NOT NULL DEFAULT '',
    epg_feed_status TEXT NOT NULL DEFAULT '',
    epg_feed_checked REAL,
    sort INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS user_services (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, service_id)
);

-- owner_id 0 = ensemble
CREATE TABLE IF NOT EXISTS logos (
    id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('upload', 'url')),
    url TEXT NOT NULL DEFAULT '',
    file TEXT NOT NULL DEFAULT '',
    mime TEXT NOT NULL DEFAULT '',
    size INTEGER NOT NULL DEFAULT 0,
    fetch_status TEXT NOT NULL DEFAULT '',
    fetch_error TEXT NOT NULL DEFAULT '',
    fetched_at REAL,
    updated_at REAL NOT NULL,
    UNIQUE (owner_id, width, height)
);

CREATE TABLE IF NOT EXISTS programmes (
    id INTEGER PRIMARY KEY,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    short_title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    genres TEXT NOT NULL DEFAULT '[]',
    kind TEXT NOT NULL CHECK (kind IN ('weekly', 'once')),
    days INTEGER NOT NULL DEFAULT 0,         -- bitmask, bit 0 = Monday
    date TEXT NOT NULL DEFAULT '',           -- YYYY-MM-DD for one-off
    start_time TEXT NOT NULL,                -- HH:MM local time
    duration INTEGER NOT NULL,               -- minutes
    valid_from TEXT NOT NULL DEFAULT '',
    valid_to TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS feed_templates (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    definition TEXT NOT NULL,
    sample INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    created_at REAL NOT NULL,
    user_id INTEGER,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS builds (
    id INTEGER PRIMARY KEY,
    started_at REAL NOT NULL,
    finished_at REAL,
    trigger TEXT NOT NULL,
    user_id INTEGER,
    username TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'running',
    message TEXT NOT NULL DEFAULT '',
    stats TEXT NOT NULL DEFAULT '{}',
    warnings TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    user_id INTEGER,
    username TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    target TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS audit_ts ON audit(ts);
"""

DEFAULT_SETTINGS = {
    "ensemble": {"ecc": "", "eid": "", "short_name": "", "medium_name": ""},
    "output_path": "",
    "bitrate": 16,
    "packet_address": 1,
    "datagroup_mode": False,
    "write_mode": "inplace",
    "refresh_mode": "daily",       # daily | interval
    "refresh_time": "00:00",
    "refresh_interval_hours": 6,
    "epg_days": 7,
    "timezone": "",
    "allow_private_urls": False,
    "session_hours": 12,
    "mux": {
        "service_uid": "srv-spi", "service_id": "", "label": "SPI", "short_label": "SPI",
        "subchannel_uid": "sub-spi", "subchannel_id": 20, "protection_profile": "EEP_A",
        "protection": 3, "component_uid": "comp-spi",
    },
    "setup_complete": False,
    "mux_name": "",
    "dismissed_warnings": {},
}

_local = threading.local()
_path = None


def init(data_dir):
    global _path
    os.makedirs(data_dir, mode=0o750, exist_ok=True)
    _path = os.path.join(data_dir, "odr-spi.db")
    c = conn()
    c.executescript(SCHEMA)
    for k, v in DEFAULT_SETTINGS.items():
        c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, json.dumps(v)))
    if get_meta("templates_seeded") is None:
        seed_sample_templates()
        set_meta("templates_seeded", 1)
    # feeds created before templates existed used the built-in "mpbnl" type
    mpbnl = q1("SELECT id FROM feed_templates WHERE name = 'MPBNL'")
    if mpbnl:
        x("UPDATE services SET epg_feed_type = ? WHERE epg_feed_type = 'mpbnl'", (f"tpl:{mpbnl['id']}",))
    c.commit()
    try:
        os.chmod(_path, 0o600)
    except OSError:
        pass


def conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    if c is None:
        c = sqlite3.connect(_path, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA journal_mode = WAL")
        c.execute("PRAGMA busy_timeout = 30000")
        _local.conn = c
    return c


def q(sql, args=()):
    return [dict(r) for r in conn().execute(sql, args).fetchall()]


def q1(sql, args=()):
    r = conn().execute(sql, args).fetchone()
    return dict(r) if r else None


def x(sql, args=()):
    return conn().execute(sql, args)


class transaction:
    def __enter__(self):
        conn().execute("BEGIN IMMEDIATE")
        return conn()

    def __exit__(self, exc_type, *_):
        conn().execute("ROLLBACK" if exc_type else "COMMIT")
        return False


def seed_sample_templates():
    """Add any sample templates that are missing (matched by name)."""
    from .feed_templates import SAMPLES
    added = 0
    for t in SAMPLES:
        if not q1("SELECT id FROM feed_templates WHERE name = ?", (t["name"],)):
            x("INSERT INTO feed_templates(name, definition, sample, created_at, updated_at) VALUES (?,?,1,?,?)",
              (t["name"], json.dumps(t), time.time(), time.time()))
            added += 1
    return added


def get_setting(key):
    r = q1("SELECT value FROM settings WHERE key = ?", (key,))
    if r is None:
        return DEFAULT_SETTINGS.get(key)
    return json.loads(r["value"])


def all_settings():
    out = dict(DEFAULT_SETTINGS)
    for r in q("SELECT key, value FROM settings"):
        out[r["key"]] = json.loads(r["value"])
    return out


def set_setting(key, value):
    x("INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
      (key, json.dumps(value)))


def get_meta(key, default=None):
    r = q1("SELECT value FROM meta WHERE key = ?", (key,))
    return r["value"] if r else default


def set_meta(key, value):
    x("INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
      (key, str(value)))


def mark_dirty():
    set_meta("dirty_since", get_meta("dirty_since") or time.time())


def audit(user, ip, action, target="", details=None):
    x("INSERT INTO audit(ts, user_id, username, ip, action, target, details) VALUES (?,?,?,?,?,?,?)",
      (time.time(), user["id"] if user else None, user["username"] if user else "", ip or "",
       action, target, json.dumps(details or {})))
