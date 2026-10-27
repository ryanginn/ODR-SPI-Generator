"""JSON API."""

import hmac
import json
import os
import re
import secrets
import stat
import threading
import time
from datetime import date, datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, make_response, request, send_file

from .. import __version__, build, db, epg, feed_templates, fetch, importers, media, scheduler, security
from ..encoder import spi_binary
from . import (ALL_SERVICE_FIELDS, COOKIE, STATION_FIELDS, ApiError, allowed_service_ids, audit, can_apply,
               check_service_access, client_ip, current_user, is_editor, json_body, require)

bp = Blueprint("api", __name__)

HEX = lambda n: re.compile(r"^[0-9a-fA-F]{%d}$" % n)
GENRE_RE = re.compile(r"^urn:tva:metadata:cs:[A-Za-z]+CS:\d{4}:[0-9]+(\.[0-9]+)*$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{3,64}$")


# --- validation helpers -------------------------------------------------------------------

def _str(data, key, maxlen, required=False, label=None):
    v = data.get(key, "")
    if v is None:
        v = ""
    if not isinstance(v, str):
        raise ApiError(f"{label or key} must be text.")
    v = v.strip()
    if "\x00" in v or any(ord(c) < 32 and c not in "\n\t" for c in v):
        raise ApiError(f"{label or key} contains control characters.")
    if len(v) > maxlen:
        raise ApiError(f"{label or key} must be at most {maxlen} characters.")
    if required and not v:
        raise ApiError(f"{label or key} is required.")
    return v


def _int(data, key, lo, hi, label=None):
    try:
        v = int(data.get(key))
    except (TypeError, ValueError):
        raise ApiError(f"{label or key} must be a number.")
    if not lo <= v <= hi:
        raise ApiError(f"{label or key} must be between {lo} and {hi}.")
    return v


def _url(v, label="URL"):
    v = (v or "").strip()
    if not v:
        return ""
    try:
        fetch.validate_url(v)
    except fetch.FetchError as e:
        raise ApiError(f"{label}: {e}")
    return v


def _date(v, label):
    v = (v or "").strip()
    if not v:
        return ""
    try:
        return date.fromisoformat(v).isoformat()
    except ValueError:
        raise ApiError(f"{label} must be a date (YYYY-MM-DD).")


def _bearers(v):
    if not isinstance(v, list) or len(v) > 8:
        raise ApiError("Bearers must be a list of at most 8 entries.")
    out = []
    for b in v:
        if not isinstance(b, dict):
            raise ApiError("Invalid bearer.")
        sid = str(b.get("sid", "")).strip().lower().removeprefix("0x")
        ecc = str(b.get("ecc") or "").strip().lower().removeprefix("0x")
        eid = str(b.get("eid") or "").strip().lower().removeprefix("0x")
        if not HEX(4).match(sid) or sid == "0000":
            raise ApiError("Service ID (SId) must be 4 hex digits, e.g. c586.")
        if ecc and not HEX(2).match(ecc):
            raise ApiError("ECC must be 2 hex digits, e.g. e1.")
        if eid and not HEX(4).match(eid):
            raise ApiError("EId must be 4 hex digits.")
        try:
            scids = int(b.get("scids") or 0)
        except (TypeError, ValueError):
            scids = -1
        if not 0 <= scids <= 15:
            raise ApiError("SCIdS must be 0-15.")
        out.append({"ecc": ecc, "eid": eid, "sid": sid, "scids": scids})
    return out


def _genres(v):
    if not isinstance(v, list) or len(v) > 10:
        raise ApiError("At most 10 genres.")
    out = []
    for gnr in v:
        if not isinstance(gnr, str) or len(gnr) > 100 or not GENRE_RE.match(gnr.strip()) \
                or spi_binary.genre_bytes(gnr.strip()) is None:
            raise ApiError(f"Invalid genre: {str(gnr)[:60]}")
        if gnr.strip() not in out:
            out.append(gnr.strip())
    return out


def _size(spec):
    m = re.fullmatch(r"(\d{1,4})x(\d{1,4})", spec or "")
    if not m:
        raise ApiError("Invalid logo size.")
    w, h = int(m.group(1)), int(m.group(2))
    if not (1 <= w <= 2000 and 1 <= h <= 2000):
        raise ApiError("Invalid logo size.")
    return w, h


# --- session / auth -----------------------------------------------------------------------

def _set_cookie(resp, token, hours):
    resp.set_cookie(COOKIE, token, max_age=int(hours * 3600), httponly=True, samesite="Strict",
                    secure=request.is_secure, path="/")


def _user_public(u):
    return {"id": u["id"], "username": u["username"], "display_name": u["display_name"], "role": u["role"],
            "can_apply": bool(u["can_apply"]) or u["role"] in ("admin", "editor"),
            "must_change_pw": bool(u["must_change_pw"])}


def setup_token_path():
    return os.path.join(current_app.config["ODR_CFG"]["data_dir"], "setup-token")


def users_exist():
    return db.q1("SELECT 1 AS x FROM users LIMIT 1") is not None


@bp.get("/api/state")
def state():
    u = current_user()
    return jsonify(
        version=__version__, setup_required=not users_exist(),
        user=_user_public(u) if u else None, csrf=u["csrf"] if u else None,
        setup_complete=bool(db.get_setting("setup_complete")),
        mux_name=mux_display_name(),
    )


def mux_display_name():
    """Shown on the login screen, page title and sidebar. It names the
    multiplex, which is public on air, so it is safe to show before login."""
    return db.get_setting("mux_name") or (db.get_setting("ensemble") or {}).get("medium_name", "")


@bp.post("/api/setup")
def setup():
    if not security.setup_limiter.hit(client_ip()):
        raise ApiError("Too many attempts - wait 15 minutes.", 429)
    if users_exist():
        raise ApiError("Setup has already been completed.", 409)
    data = json_body()
    token = data.get("token", "")
    try:
        with open(setup_token_path()) as f:
            expected = f.read().strip()
    except OSError:
        raise ApiError("No setup token found. Run: sudo odr-spi-generator setup-token", 403)
    if not isinstance(token, str) or not expected or not hmac.compare_digest(token.strip(), expected):
        db.audit(None, client_ip(), "setup.bad_token")
        raise ApiError("Setup token is incorrect.", 403)
    username = _str(data, "username", 64, True, "Username")
    if not USERNAME_RE.match(username):
        raise ApiError("Username may contain letters, digits and . _ @ - (3-64 characters).")
    pw = data.get("password", "")
    problem = security.password_problem(pw, username)
    if problem:
        raise ApiError(problem)
    with db.transaction():
        if users_exist():
            raise ApiError("Setup has already been completed.", 409)
        uid = db.x("INSERT INTO users(username, display_name, pw_hash, role, can_apply, created_at) "
                   "VALUES (?,?,?,?,1,?)", (username, _str(data, "display_name", 64) or username,
                                            security.hash_password(pw), "admin", time.time())).lastrowid
    try:
        os.remove(setup_token_path())
    except OSError:
        pass
    user = {"id": uid, "username": username}
    db.audit(user, client_ip(), "setup.admin_created", username)
    return _login_response(uid)


def _login_response(uid):
    hours = int(db.get_setting("session_hours") or 12)
    token, _ = security.create_session(uid, client_ip(), request.headers.get("User-Agent"), hours)
    db.x("UPDATE users SET last_login = ?, failed_logins = 0, locked_until = 0 WHERE id = ?", (time.time(), uid))
    resp = make_response(jsonify(ok=True))
    _set_cookie(resp, token, hours)
    return resp


@bp.post("/api/login")
def login():
    if not security.login_limiter.hit(client_ip()):
        raise ApiError("Too many login attempts from your address - wait 15 minutes.", 429)
    data = json_body()
    username = data.get("username", "")
    password = data.get("password", "")
    if not isinstance(username, str) or not isinstance(password, str) or len(password) > security.MAX_PASSWORD_LEN:
        raise ApiError("Invalid username or password.", 401)
    u = db.q1("SELECT * FROM users WHERE username = ?", (username.strip(),))
    if not u:
        security.dummy_verify(password)
        db.audit(None, client_ip(), "login.failed", username[:64])
        raise ApiError("Invalid username or password.", 401)
    if u["locked_until"] > time.time():
        security.dummy_verify(password)
        raise ApiError("Account temporarily locked after repeated failures - try again later.", 429)
    if not security.verify_password(password, u["pw_hash"]) or u["disabled"]:
        fails = u["failed_logins"] + 1
        locked = time.time() + security.LOCKOUT_SECONDS if fails >= security.LOCKOUT_THRESHOLD else 0
        db.x("UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?",
             (0 if locked else fails, locked, u["id"]))
        db.audit(u, client_ip(), "login.failed" + (".locked" if locked else ""), u["username"])
        raise ApiError("Invalid username or password.", 401)
    db.audit(u, client_ip(), "login", u["username"])
    return _login_response(u["id"])


@bp.post("/api/logout")
def logout():
    if g.session_token:
        security.destroy_session(g.session_token)
    resp = make_response(jsonify(ok=True))
    resp.delete_cookie(COOKIE, path="/")
    return resp


@bp.post("/api/account/password")
@require()
def change_password():
    data = json_body()
    u = db.q1("SELECT * FROM users WHERE id = ?", (current_user()["id"],))
    if not security.verify_password(data.get("current", "") or "", u["pw_hash"]):
        raise ApiError("Current password is incorrect.", 403)
    problem = security.password_problem(data.get("new", ""), u["username"])
    if problem:
        raise ApiError(problem)
    if data["new"] == data.get("current"):
        raise ApiError("New password must differ from the current one.")
    db.x("UPDATE users SET pw_hash = ?, must_change_pw = 0 WHERE id = ?",
         (security.hash_password(data["new"]), u["id"]))
    security.destroy_user_sessions(u["id"], except_token=g.session_token)
    audit("account.password_changed", u["username"])
    return jsonify(ok=True)


@bp.patch("/api/account")
@require()
def update_account():
    data = json_body()
    name = _str(data, "display_name", 64)
    db.x("UPDATE users SET display_name = ? WHERE id = ?", (name, current_user()["id"]))
    return jsonify(ok=True)


# --- status -------------------------------------------------------------------------------

@bp.get("/api/status")
@require()
def status():
    u = current_user()
    last = db.q1("SELECT * FROM builds ORDER BY id DESC LIMIT 1")
    last_ok = db.get_meta("last_success")
    dirty = db.get_meta("dirty_since") or ""
    snap_exists = db.q1("SELECT id FROM snapshots LIMIT 1") is not None
    out = {
        "build": _redact_builds([_build_public(last)], u)[0] if last else None,
        "running": build.status()["running"],
        "dirty_since": float(dirty) if dirty else None,
        "published": snap_exists,
        "last_success": float(last_ok) if last_ok else None,
        "next_refresh": scheduler.next_run_time(),
        "can_apply": can_apply(u),
        "setup_complete": bool(db.get_setting("setup_complete")),
        "server_time": time.time(),
    }
    if is_editor(u):
        out["output_path"] = db.get_setting("output_path")
    return jsonify(out)


def _build_public(b):
    return {**b, "stats": json.loads(b["stats"]), "warnings": json.loads(b["warnings"])}


def _redact_builds(rows, u):
    """Station owners see build outcomes, not server paths or other stations' warnings."""
    if is_editor(u):
        return rows
    return [dict(r, warnings=[], message="Build failed - contact an administrator." if r["status"] == "error"
                 else "") for r in rows]


@bp.get("/api/builds")
@require()
def builds():
    rows = db.q("SELECT * FROM builds ORDER BY id DESC LIMIT 50")
    return jsonify(_redact_builds([_build_public(r) for r in rows], current_user()))


@bp.post("/api/builds/<int:bid>/dismiss")
@require("editor")
def dismiss_warnings(bid):
    """Dismiss one warning (or all) of a build; the same warning is hidden on
    later builds too, so a known condition stops flagging the status."""
    b = db.q1("SELECT * FROM builds WHERE id = ?", (bid,))
    if not b:
        raise ApiError("Build not found.", 404)
    text = json_body().get("warning")
    warnings = json.loads(b["warnings"])
    stats = json.loads(b["stats"])
    targets = warnings if text is None else [w for w in warnings if w == text]
    if not targets:
        raise ApiError("Warning not found.", 404)
    dismissed = dict(db.get_setting("dismissed_warnings") or {})
    for w in targets:
        key = build.warning_key(w)
        dismissed[key] = stats.get("cycle_seconds", 0) if key == build.SLOW_CYCLE else 1
    if len(dismissed) > 1000:
        raise ApiError("Too many dismissed warnings - restore them first.")
    db.set_setting("dismissed_warnings", dismissed)
    remaining = [w for w in warnings if w not in targets]
    stats["dismissed_warnings"] = stats.get("dismissed_warnings", 0) + len(targets)
    status = "ok" if b["status"] == "warning" and not remaining else b["status"]
    db.x("UPDATE builds SET warnings = ?, stats = ?, status = ? WHERE id = ?",
         (json.dumps(remaining), json.dumps(stats), status, bid))
    audit("warnings.dismiss", str(bid), {"count": len(targets)})
    return jsonify(ok=True)


@bp.post("/api/warnings/restore")
@require("editor")
def restore_warnings():
    db.set_setting("dismissed_warnings", {})
    audit("warnings.restore")
    return jsonify(ok=True)


@bp.post("/api/apply")
@require()
def apply():
    u = current_user()
    if not can_apply(u):
        raise ApiError("You are not allowed to apply changes - ask an administrator.", 403)
    path = db.get_setting("output_path")
    try:
        build.check_output_path(path)
    except ValueError as e:
        raise ApiError(f"Output location problem: {e}")
    try:
        build.run_async("apply", u, apply_changes=True)
    except RuntimeError as e:
        raise ApiError(str(e), 409)
    audit("apply")
    return jsonify(ok=True)


# --- ensemble -----------------------------------------------------------------------------

@bp.get("/api/ensemble")
@require()
def get_ensemble():
    return jsonify(ensemble=db.get_setting("ensemble"), logos=_logos_for(0), editable=is_editor(current_user()))


@bp.put("/api/ensemble")
@require("editor")
def put_ensemble():
    data = json_body()
    ecc = _str(data, "ecc", 4, True, "ECC").lower().removeprefix("0x")
    eid = _str(data, "eid", 6, True, "EId").lower().removeprefix("0x")
    if not HEX(2).match(ecc):
        raise ApiError("ECC must be 2 hex digits, e.g. e1.")
    if not HEX(4).match(eid):
        raise ApiError("EId must be 4 hex digits, e.g. c185.")
    ens = {"ecc": ecc, "eid": eid, "short_name": _str(data, "short_name", 8, True, "Short label"),
           "medium_name": _str(data, "medium_name", 16, True, "Label")}
    db.set_setting("ensemble", ens)
    db.mark_dirty()
    audit("ensemble.update", f"{ecc}.{eid}", ens)
    return jsonify(ok=True)


# --- services -----------------------------------------------------------------------------

def _logos_for(owner_id):
    return db.q("SELECT width, height, source, url, file, mime, size, fetch_status, fetch_error, fetched_at, "
                "updated_at FROM logos WHERE owner_id = ? ORDER BY width * height", (owner_id,))


def _service_public(s, u, owners=None):
    out = dict(s)
    out["genres"] = json.loads(s["genres"])
    out["bearers"] = json.loads(s["bearers"])
    out["logos"] = _logos_for(s["id"])
    out["programme_count"] = db.q1("SELECT COUNT(*) AS n FROM programmes WHERE service_id = ?", (s["id"],))["n"]
    out["can_edit_core"] = is_editor(u)
    if owners is not None:
        out["owners"] = owners.get(s["id"], [])
    return out


@bp.get("/api/services")
@require()
def list_services():
    u = current_user()
    ids = allowed_service_ids(u)
    rows = db.q("SELECT * FROM services ORDER BY sort, medium_name COLLATE NOCASE, id")
    if ids is not None:
        rows = [r for r in rows if r["id"] in ids]
    owners = None
    if is_editor(u):
        owners = {}
        for r in db.q("SELECT us.service_id, u.username FROM user_services us JOIN users u ON u.id = us.user_id"):
            owners.setdefault(r["service_id"], []).append(r["username"])
    return jsonify([_service_public(r, u, owners) for r in rows])


@bp.get("/api/services/<int:sid>")
@require()
def get_service(sid):
    check_service_access(current_user(), sid)
    return jsonify(_service_public(db.q1("SELECT * FROM services WHERE id = ?", (sid,)), current_user()))


def _service_fields(data, allowed):
    out = {}
    for k in data:
        if k not in ALL_SERVICE_FIELDS:
            continue
        if k not in allowed:
            raise ApiError(f"You are not allowed to change '{k}'.", 403)
    if "short_name" in data:
        out["short_name"] = _str(data, "short_name", 8, True, "Short name")
    if "medium_name" in data:
        out["medium_name"] = _str(data, "medium_name", 16, True, "Name")
    if "long_name" in data:
        out["long_name"] = _str(data, "long_name", 128, False, "Long name")
    if "short_description" in data:
        out["short_description"] = _str(data, "short_description", 180, False, "Short description")
    if "long_description" in data:
        out["long_description"] = _str(data, "long_description", 1200, False, "Long description")
    if "website" in data:
        out["website"] = _url(data.get("website"), "Website")
    if "genres" in data:
        out["genres"] = json.dumps(_genres(data["genres"]))
    if "bearers" in data:
        out["bearers"] = json.dumps(_bearers(data["bearers"]))
    if "enabled" in data:
        out["enabled"] = 1 if data["enabled"] else 0
    if "sort" in data:
        out["sort"] = _int(data, "sort", -100000, 100000)
    return out


@bp.post("/api/services")
@require("editor")
def create_service():
    data = json_body()
    for k in ("short_name", "medium_name"):
        data.setdefault(k, "")
    fields = _service_fields(data, ALL_SERVICE_FIELDS)
    now = time.time()
    fields.update(created_at=now, updated_at=now)
    cols = ",".join(fields)
    sid = db.x(f"INSERT INTO services({cols}) VALUES ({','.join('?' * len(fields))})",
               tuple(fields.values())).lastrowid
    db.mark_dirty()
    audit("service.create", fields.get("medium_name", ""), {"id": sid})
    return jsonify(id=sid)


@bp.patch("/api/services/<int:sid>")
@require()
def update_service(sid):
    u = current_user()
    check_service_access(u, sid)
    data = json_body()
    fields = _service_fields(data, ALL_SERVICE_FIELDS if is_editor(u) else STATION_FIELDS)
    if not fields:
        return jsonify(ok=True)
    fields["updated_at"] = time.time()
    db.x(f"UPDATE services SET {', '.join(k + ' = ?' for k in fields)} WHERE id = ?", (*fields.values(), sid))
    db.mark_dirty()
    audit("service.update", str(sid), {k: v for k, v in fields.items() if k != "updated_at"})
    return jsonify(ok=True)


@bp.delete("/api/services/<int:sid>")
@require("editor")
def delete_service(sid):
    s = db.q1("SELECT * FROM services WHERE id = ?", (sid,))
    if not s:
        raise ApiError("Station not found.", 404)
    with db.transaction():
        db.x("DELETE FROM logos WHERE owner_id = ?", (sid,))
        db.x("DELETE FROM services WHERE id = ?", (sid,))
    epg.delete_feed(sid)
    db.mark_dirty()
    audit("service.delete", s["medium_name"], {"id": sid})
    return jsonify(ok=True)


# --- logos --------------------------------------------------------------------------------

def _check_logo_owner(owner_id):
    u = current_user()
    if owner_id == 0:
        if not is_editor(u):
            raise ApiError("Only editors can change ensemble logos.", 403)
    else:
        check_service_access(u, owner_id)


def _upsert_logo(owner_id, w, h, **fields):
    now = time.time()
    existing = db.q1("SELECT id FROM logos WHERE owner_id = ? AND width = ? AND height = ?", (owner_id, w, h))
    fields["updated_at"] = now
    if existing:
        db.x(f"UPDATE logos SET {', '.join(k + ' = ?' for k in fields)} WHERE id = ?",
             (*fields.values(), existing["id"]))
        return existing["id"]
    fields.update(owner_id=owner_id, width=w, height=h)
    return db.x(f"INSERT INTO logos({','.join(fields)}) VALUES ({','.join('?' * len(fields))})",
                tuple(fields.values())).lastrowid


@bp.post("/api/logos/<int:owner_id>/<spec>/upload")
@require()
def upload_logo(owner_id, spec):
    _check_logo_owner(owner_id)
    w, h = _size(spec)
    f = request.files.get("file")
    if not f:
        raise ApiError("No file uploaded.")
    raw = f.read(media.MAX_LOGO_BYTES + 1)
    try:
        data, mime, _, _ = media.normalise(raw, w, h, fit=request.form.get("fit") == "1")
    except media.ImageError as e:
        raise ApiError(str(e))
    name = media.store(data, mime)
    _upsert_logo(owner_id, w, h, source="upload", url="", file=name, mime=mime, size=len(data),
                 fetch_status="", fetch_error="", fetched_at=None)
    db.mark_dirty()
    audit("logo.upload", f"{owner_id}:{spec}", {"bytes": len(data)})
    return jsonify(ok=True, size=len(data))


@bp.put("/api/logos/<int:owner_id>/<spec>/url")
@require()
def set_logo_url(owner_id, spec):
    _check_logo_owner(owner_id)
    w, h = _size(spec)
    url = _url(json_body().get("url"), "Logo URL")
    if not url:
        raise ApiError("Enter a URL.")
    lid = _upsert_logo(owner_id, w, h, source="url", url=url)
    logo = db.q1("SELECT * FROM logos WHERE id = ?", (lid,))
    err = build.refresh_logo(logo, bool(db.get_setting("allow_private_urls")))
    db.mark_dirty()
    audit("logo.url", f"{owner_id}:{spec}", {"url": url, "error": err})
    return jsonify(ok=not err, error=err or None)


@bp.post("/api/logos/<int:owner_id>/<spec>/refresh")
@require()
def refresh_logo(owner_id, spec):
    _check_logo_owner(owner_id)
    w, h = _size(spec)
    logo = db.q1("SELECT * FROM logos WHERE owner_id = ? AND width = ? AND height = ? AND source = 'url'",
                 (owner_id, w, h))
    if not logo:
        raise ApiError("No URL logo at this size.", 404)
    err = build.refresh_logo(logo, bool(db.get_setting("allow_private_urls")))
    return jsonify(ok=not err, error=err or None)


@bp.delete("/api/logos/<int:owner_id>/<spec>")
@require()
def delete_logo(owner_id, spec):
    _check_logo_owner(owner_id)
    w, h = _size(spec)
    db.x("DELETE FROM logos WHERE owner_id = ? AND width = ? AND height = ?", (owner_id, w, h))
    db.mark_dirty()
    audit("logo.delete", f"{owner_id}:{spec}")
    return jsonify(ok=True)


@bp.get("/media/<name>")
@require()
def serve_media(name):
    u = current_user()
    try:
        path = media.path_for(name)
    except ValueError:
        raise ApiError("Not found.", 404)
    if not is_editor(u):
        ids = allowed_service_ids(u) or set()
        owners = {r["owner_id"] for r in db.q("SELECT owner_id FROM logos WHERE file = ?", (name,))}
        if not owners & (ids | {0}):
            raise ApiError("Not found.", 404)
    if not os.path.exists(path):
        raise ApiError("Not found.", 404)
    resp = send_file(path, mimetype="image/png" if name.endswith(".png") else "image/jpeg", max_age=86400)
    resp.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return resp


# --- EPG ----------------------------------------------------------------------------------

def _programme_fields(data):
    kind = data.get("kind")
    if kind not in ("weekly", "once"):
        raise ApiError("Choose weekly or one-off.")
    start = _str(data, "start_time", 5, True, "Start time")
    if not TIME_RE.match(start):
        raise ApiError("Start time must be HH:MM.")
    out = {
        "title": _str(data, "title", 128, True, "Title"),
        "short_title": _str(data, "short_title", 8, False, "Short title"),
        "description": _str(data, "description", 1200, False, "Description"),
        "genres": json.dumps(_genres(data.get("genres") or [])),
        "kind": kind, "start_time": start,
        "duration": _int(data, "duration", 1, 1440, "Duration (minutes)"),
        "days": 0, "date": "", "valid_from": "", "valid_to": "",
    }
    if kind == "weekly":
        out["days"] = _int(data, "days", 1, 127, "Days")
        out["valid_from"] = _date(data.get("valid_from"), "Valid from")
        out["valid_to"] = _date(data.get("valid_to"), "Valid until")
    else:
        out["date"] = _date(data.get("date"), "Date")
        if not out["date"]:
            raise ApiError("Pick a date for a one-off programme.")
    return out


@bp.get("/api/services/<int:sid>/programmes")
@require()
def list_programmes(sid):
    check_service_access(current_user(), sid)
    rows = db.q("SELECT * FROM programmes WHERE service_id = ? ORDER BY kind DESC, start_time, id", (sid,))
    for r in rows:
        r["genres"] = json.loads(r["genres"])
    return jsonify(rows)


@bp.post("/api/services/<int:sid>/programmes")
@require()
def create_programme(sid):
    check_service_access(current_user(), sid)
    if db.q1("SELECT COUNT(*) AS n FROM programmes WHERE service_id = ?", (sid,))["n"] >= 2000:
        raise ApiError("Too many programmes for this station.")
    f = _programme_fields(json_body())
    now = time.time()
    f.update(service_id=sid, created_at=now, updated_at=now)
    pid = db.x(f"INSERT INTO programmes({','.join(f)}) VALUES ({','.join('?' * len(f))})",
               tuple(f.values())).lastrowid
    db.mark_dirty()
    audit("epg.create", str(sid), {"title": f["title"]})
    return jsonify(id=pid)


def _programme(pid):
    p = db.q1("SELECT * FROM programmes WHERE id = ?", (pid,))
    if not p:
        raise ApiError("Programme not found.", 404)
    check_service_access(current_user(), p["service_id"])
    return p


@bp.put("/api/programmes/<int:pid>")
@require()
def update_programme(pid):
    p = _programme(pid)
    f = _programme_fields(json_body())
    f["updated_at"] = time.time()
    db.x(f"UPDATE programmes SET {', '.join(k + ' = ?' for k in f)} WHERE id = ?", (*f.values(), pid))
    db.mark_dirty()
    audit("epg.update", str(p["service_id"]), {"id": pid, "title": f["title"]})
    return jsonify(ok=True)


@bp.delete("/api/programmes/<int:pid>")
@require()
def delete_programme(pid):
    p = _programme(pid)
    db.x("DELETE FROM programmes WHERE id = ?", (pid,))
    db.mark_dirty()
    audit("epg.delete", str(p["service_id"]), {"id": pid, "title": p["title"]})
    return jsonify(ok=True)


@bp.put("/api/services/<int:sid>/epg")
@require()
def set_epg(sid):
    check_service_access(current_user(), sid)
    data = json_body()
    ftype = data.get("epg_feed_type", "xmltv")
    if not isinstance(ftype, str):
        raise ApiError("Invalid feed type.")
    if ftype.startswith("tpl:"):
        if not ftype[4:].isdigit() or not db.q1("SELECT id FROM feed_templates WHERE id = ?", (int(ftype[4:]),)):
            raise ApiError("That API template no longer exists.")
    elif ftype not in ("xmltv", "spi"):
        raise ApiError("Feed type must be XMLTV, SPI XML or an API template.")
    url = _url(data.get("epg_feed_url"), "Feed URL")
    db.x("UPDATE services SET epg_enabled = ?, epg_feed_url = ?, epg_feed_type = ?, epg_feed_channel = ?, "
         "updated_at = ? WHERE id = ?",
         (1 if data.get("epg_enabled") else 0, url, ftype, _str(data, "epg_feed_channel", 128), time.time(), sid))
    if not url:
        epg.delete_feed(sid)
        db.x("UPDATE services SET epg_feed_status = '', epg_feed_checked = NULL WHERE id = ?", (sid,))
    db.mark_dirty()
    audit("epg.settings", str(sid), {"enabled": bool(data.get("epg_enabled")), "feed": url})
    return jsonify(ok=True)


@bp.post("/api/services/<int:sid>/epg/refresh")
@require()
def refresh_epg(sid):
    check_service_access(current_user(), sid)
    s = db.q1("SELECT * FROM services WHERE id = ?", (sid,))
    if not s["epg_feed_url"]:
        raise ApiError("No feed URL configured.")
    err = build.refresh_feed(s, bool(db.get_setting("allow_private_urls")))
    db.mark_dirty()
    return jsonify(ok=not err, error=err or None)


@bp.get("/api/services/<int:sid>/epg/preview")
@require()
def epg_preview(sid):
    check_service_access(current_user(), sid)
    s = db.q1("SELECT * FROM services WHERE id = ?", (sid,))
    entries = db.q("SELECT * FROM programmes WHERE service_id = ?", (sid,))
    for e in entries:
        e["genres"] = json.loads(e["genres"])
    feed = epg.load_feed(sid) if s["epg_feed_url"] else []
    tz = epg.get_tz(db.get_setting("timezone"))
    days = int(db.get_setting("epg_days") or 7) or 7
    today = datetime.now(tz).date()
    out = []
    for d in range(days):
        day = today + timedelta(days=d)
        progs = epg.expand_day(entries, feed, day, tz)
        out.append({"date": day.isoformat(), "programmes": [
            {"start": p["start"].astimezone(tz).strftime("%H:%M"), "end": p["end"].astimezone(tz).strftime("%H:%M"),
             "title": p["title"], "description": p["description"],
             "source": "manual" if any(p["start"] == epg._local(day, e["start_time"], tz) and e["title"] == p["title"]
                                       for e in entries) else "feed"} for p in progs]})
    return jsonify(days=out, timezone=str(tz))


# --- users --------------------------------------------------------------------------------

def _user_row(u):
    out = {k: u[k] for k in ("id", "username", "display_name", "role", "can_apply", "disabled",
                             "must_change_pw", "created_at", "last_login")}
    out["locked"] = u["locked_until"] > time.time()
    out["services"] = [r["service_id"] for r in db.q("SELECT service_id FROM user_services WHERE user_id = ?",
                                                     (u["id"],))]
    return out


@bp.get("/api/users")
@require("admin")
def list_users():
    return jsonify([_user_row(u) for u in db.q("SELECT * FROM users ORDER BY username COLLATE NOCASE")])


def _user_fields(data, creating):
    out = {}
    if "display_name" in data:
        out["display_name"] = _str(data, "display_name", 64)
    if "role" in data or creating:
        role = data.get("role")
        if role not in ("admin", "editor", "station"):
            raise ApiError("Role must be admin, editor or station.")
        out["role"] = role
    if "can_apply" in data:
        out["can_apply"] = 1 if data["can_apply"] else 0
    if "disabled" in data:
        out["disabled"] = 1 if data["disabled"] else 0
    return out


def _set_user_services(uid, services):
    if not isinstance(services, list) or len(services) > 1000:
        raise ApiError("Invalid station list.")
    valid = {r["id"] for r in db.q("SELECT id FROM services")}
    db.x("DELETE FROM user_services WHERE user_id = ?", (uid,))
    for sid in services:
        if isinstance(sid, int) and sid in valid:
            db.x("INSERT OR IGNORE INTO user_services(user_id, service_id) VALUES (?, ?)", (uid, sid))


@bp.post("/api/users")
@require("admin")
def create_user():
    data = json_body()
    username = _str(data, "username", 64, True, "Username")
    if not USERNAME_RE.match(username):
        raise ApiError("Username may contain letters, digits and . _ @ - (3-64 characters).")
    if db.q1("SELECT id FROM users WHERE username = ?", (username,)):
        raise ApiError("That username is taken.")
    pw = data.get("password") or ""
    generated = not pw
    if generated:
        pw = secrets.token_urlsafe(12)
    problem = security.password_problem(pw, username)
    if problem:
        raise ApiError(problem)
    f = _user_fields(data, True)
    f.update(username=username, pw_hash=security.hash_password(pw), created_at=time.time(), must_change_pw=1)
    with db.transaction():
        uid = db.x(f"INSERT INTO users({','.join(f)}) VALUES ({','.join('?' * len(f))})",
                   tuple(f.values())).lastrowid
        _set_user_services(uid, data.get("services") or [])
    audit("user.create", username, {"role": f["role"]})
    return jsonify(id=uid, password=pw if generated else None)


@bp.patch("/api/users/<int:uid>")
@require("admin")
def update_user(uid):
    u = db.q1("SELECT * FROM users WHERE id = ?", (uid,))
    if not u:
        raise ApiError("User not found.", 404)
    data = json_body()
    f = _user_fields(data, False)
    me = current_user()
    if uid == me["id"] and (f.get("role", "admin") != "admin" or f.get("disabled")):
        raise ApiError("You cannot demote or disable your own account.")
    if u["role"] == "admin" and (f.get("role", "admin") != "admin" or f.get("disabled")):
        if db.q1("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND disabled = 0")["n"] <= 1:
            raise ApiError("At least one active administrator is required.")
    with db.transaction():
        if f:
            db.x(f"UPDATE users SET {', '.join(k + ' = ?' for k in f)} WHERE id = ?", (*f.values(), uid))
        if "services" in data:
            _set_user_services(uid, data["services"])
        if data.get("unlock"):
            db.x("UPDATE users SET locked_until = 0, failed_logins = 0 WHERE id = ?", (uid,))
    if f.get("disabled") or ("role" in f and f["role"] != u["role"]):
        security.destroy_user_sessions(uid)
    audit("user.update", u["username"], {**f, **({"services": data["services"]} if "services" in data else {})})
    return jsonify(ok=True)


@bp.post("/api/users/<int:uid>/reset-password")
@require("admin")
def reset_password(uid):
    u = db.q1("SELECT * FROM users WHERE id = ?", (uid,))
    if not u:
        raise ApiError("User not found.", 404)
    pw = secrets.token_urlsafe(12)
    db.x("UPDATE users SET pw_hash = ?, must_change_pw = 1, failed_logins = 0, locked_until = 0 WHERE id = ?",
         (security.hash_password(pw), uid))
    security.destroy_user_sessions(uid)
    audit("user.reset_password", u["username"])
    return jsonify(password=pw)


@bp.delete("/api/users/<int:uid>")
@require("admin")
def delete_user(uid):
    if uid == current_user()["id"]:
        raise ApiError("You cannot delete your own account.")
    u = db.q1("SELECT * FROM users WHERE id = ?", (uid,))
    if not u:
        raise ApiError("User not found.", 404)
    if u["role"] == "admin" and db.q1("SELECT COUNT(*) AS n FROM users WHERE role='admin'")["n"] <= 1:
        raise ApiError("At least one administrator is required.")
    db.x("DELETE FROM users WHERE id = ?", (uid,))
    audit("user.delete", u["username"])
    return jsonify(ok=True)


# --- settings -----------------------------------------------------------------------------

SETTING_KEYS = ("mux_name", "output_path", "bitrate", "packet_address", "datagroup_mode", "write_mode", "refresh_mode",
                "refresh_time", "refresh_interval_hours", "epg_days", "timezone", "allow_private_urls",
                "session_hours", "mux", "setup_complete")


@bp.get("/api/settings")
@require("admin")
def get_settings():
    s = db.all_settings()
    return jsonify({k: s[k] for k in SETTING_KEYS})


@bp.put("/api/settings")
@require("admin")
def put_settings():
    data = json_body()
    out = {}
    if "output_path" in data:
        p = _str(data, "output_path", 1024, True, "Output path")
        try:
            build.check_output_path(p)
        except ValueError as e:
            raise ApiError(str(e))
        out["output_path"] = p
    if "bitrate" in data:
        b = _int(data, "bitrate", 8, 96, "Bitrate")
        if b not in build.BITRATES:
            raise ApiError("Bitrate must be a multiple of 8 kbps, from 8 to 96.")
        out["bitrate"] = b
    if "packet_address" in data:
        out["packet_address"] = _int(data, "packet_address", 1, 1023, "Packet address")
    for k in ("datagroup_mode", "allow_private_urls", "setup_complete"):
        if k in data:
            out[k] = bool(data[k])
    if "write_mode" in data:
        if data["write_mode"] not in ("inplace", "atomic"):
            raise ApiError("Invalid write mode.")
        out["write_mode"] = data["write_mode"]
    if "refresh_mode" in data:
        if data["refresh_mode"] not in ("daily", "interval"):
            raise ApiError("Invalid refresh mode.")
        out["refresh_mode"] = data["refresh_mode"]
    if "refresh_time" in data:
        t = _str(data, "refresh_time", 5, True, "Refresh time")
        if not TIME_RE.match(t):
            raise ApiError("Refresh time must be HH:MM.")
        out["refresh_time"] = t
    if "refresh_interval_hours" in data:
        out["refresh_interval_hours"] = _int(data, "refresh_interval_hours", 1, 24, "Refresh interval")
    if "epg_days" in data:
        out["epg_days"] = _int(data, "epg_days", 0, 14, "EPG days")
    if "timezone" in data:
        tzn = _str(data, "timezone", 64)
        if not epg.valid_tz(tzn):
            raise ApiError("Unknown timezone (use e.g. Europe/Dublin).")
        out["timezone"] = tzn
    if "mux_name" in data:
        out["mux_name"] = _str(data, "mux_name", 64, False, "Multiplex name")
    if "session_hours" in data:
        out["session_hours"] = _int(data, "session_hours", 1, 168, "Session length")
    if "mux" in data:
        out["mux"] = _mux_fields(data["mux"])
    for k, v in out.items():
        db.set_setting(k, v)
    if set(out) & {"output_path", "bitrate", "packet_address", "datagroup_mode", "write_mode", "epg_days",
                   "timezone"}:
        db.mark_dirty()
    scheduler.wake()
    audit("settings.update", "", out)
    return jsonify(ok=True)


def _mux_fields(m):
    if not isinstance(m, dict):
        raise ApiError("Invalid mux settings.")
    ident = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
    out = {}
    for k in ("service_uid", "subchannel_uid", "component_uid"):
        v = _str(m, k, 32, True, k)
        if not ident.match(v):
            raise ApiError(f"{k} may only contain letters, digits, - and _.")
        out[k] = v
    sid = _str(m, "service_id", 10, False, "SPI service id").lower().removeprefix("0x")
    if sid and not HEX(8).match(sid):
        raise ApiError("SPI service id must be 8 hex digits (32-bit data service id), e.g. e1c185f1.")
    out["service_id"] = sid
    out["label"] = _str(m, "label", 16, True, "Label")
    out["short_label"] = _str(m, "short_label", 8, True, "Short label")
    if '"' in out["label"] + out["short_label"] or "\\" in out["label"] + out["short_label"]:
        raise ApiError("Labels must not contain quotes or backslashes.")
    out["subchannel_id"] = _int(m, "subchannel_id", 0, 63, "Subchannel id")
    if m.get("protection_profile") not in ("EEP_A", "EEP_B"):
        raise ApiError("Protection profile must be EEP_A or EEP_B.")
    out["protection_profile"] = m["protection_profile"]
    out["protection"] = _int(m, "protection", 1, 4, "Protection level")
    return out


@bp.get("/api/mux-snippet")
@require("editor")
def mux_snippet():
    s = db.all_settings()
    m = s["mux"]
    ens = s["ensemble"]
    sid = m.get("service_id") or (f"{ens.get('ecc') or 'e1'}{ens.get('eid') or '0000'}f1")
    warnings = []
    if m["protection_profile"] == "EEP_B" and s["bitrate"] % 32:
        warnings.append("EEP_B protection needs a bitrate that is a multiple of 32 kbps - use EEP_A for "
                        f"{s['bitrate']} kbps.")
    if s["datagroup_mode"]:
        warnings.append("Datagroup output mode is enabled: the file contains raw MSC datagroups, not packets.")
    if not s["output_path"]:
        warnings.append("Set the output location in Settings first.")
    path = (s["output_path"] or "/path/to/spi-output.dat").replace('"', "")
    blocks = {
        "services": f'''{m["service_uid"]} {{
    id 0x{sid}
    label "{m["label"]}"
    shortlabel "{m["short_label"]}"
}}''',
        "subchannels": f'''{m["subchannel_uid"]} {{
    type packet
    bitrate {s["bitrate"]}
    id {m["subchannel_id"]}
    protection-profile {m["protection_profile"]}
    protection {m["protection"]}
    inputproto file
    inputuri "{path}"
}}''',
        "components": f'''{m["component_uid"]} {{
    type 60
    service {m["service_uid"]}
    subchannel {m["subchannel_uid"]}
    user-applications {{
        userapp "spi"
    }}
    address 0x{s["packet_address"]:x}
    datagroup true
}}''',
    }
    return jsonify(blocks=blocks, warnings=warnings, packet_size=build.packet_size_for(s["bitrate"]))


# --- file browser (admin only) ------------------------------------------------------------

@bp.get("/api/fs")
@require("admin")
def fs_list():
    path = request.args.get("path") or "/"
    if not os.path.isabs(path) or "\x00" in path:
        raise ApiError("Path must be absolute.")
    path = os.path.realpath(path)
    if not os.path.isdir(path):
        raise ApiError("Not a directory.", 404)
    show_files = request.args.get("files", "")  # comma separated extensions
    exts = tuple("." + e.strip().lower() for e in show_files.split(",") if e.strip())
    entries = []
    try:
        with os.scandir(path) as it:
            for e in it:
                if e.name.startswith(".") and request.args.get("hidden") != "1":
                    continue
                try:
                    st = e.stat(follow_symlinks=True)
                except OSError:
                    continue
                if stat.S_ISDIR(st.st_mode):
                    entries.append({"name": e.name, "dir": True})
                elif exts and stat.S_ISREG(st.st_mode) and e.name.lower().endswith(exts):
                    entries.append({"name": e.name, "dir": False, "size": st.st_size, "mtime": st.st_mtime})
                if len(entries) >= 2000:
                    break
    except PermissionError:
        raise ApiError("Permission denied for the service user.", 403)
    entries.sort(key=lambda x: (not x["dir"], x["name"].lower()))
    return jsonify(path=path, parent=os.path.dirname(path) if path != "/" else None,
                   writable=os.access(path, os.W_OK), entries=entries)


@bp.post("/api/fs/mkdir")
@require("admin")
def fs_mkdir():
    data = json_body()
    parent = os.path.realpath(_str(data, "path", 1024, True))
    name = _str(data, "name", 128, True, "Folder name")
    if not os.path.isabs(parent) or not re.fullmatch(r"[A-Za-z0-9._ -]+", name) or name in (".", ".."):
        raise ApiError("Invalid folder name.")
    target = os.path.join(parent, name)
    try:
        os.mkdir(target, 0o755)
    except FileExistsError:
        raise ApiError("Folder already exists.")
    except OSError as e:
        raise ApiError(f"Could not create folder: {e.strerror}")
    audit("fs.mkdir", target)
    return jsonify(path=target)


# --- import -------------------------------------------------------------------------------

_imports = {}
_imports_lock = threading.Lock()


def _new_import(kind, parsed):
    with _imports_lock:
        now = time.time()
        for k in [k for k, v in _imports.items() if now - v["created"] > 3600]:
            del _imports[k]
        iid = secrets.token_urlsafe(16)
        _imports[iid] = {"user_id": current_user()["id"], "created": now, "kind": kind, "parsed": parsed,
                         "files": {}}
    return iid


def _get_import(iid):
    with _imports_lock:
        imp = _imports.get(iid)
    if not imp or imp["user_id"] != current_user()["id"]:
        raise ApiError("Import session expired - start again.", 404)
    return imp


def _import_summary(iid, imp):
    p = imp["parsed"]
    local = []
    for s in p["services"]:
        for l in s["logos"]:
            if not l["remote"]:
                key = l["url"]
                local.append({"service": s["medium_name"], "url": key, "width": l["width"], "height": l["height"],
                              "matched": key in imp["files"] and "error" not in imp["files"][key],
                              "error": imp["files"].get(key, {}).get("error")})
    existing = {}
    for r in db.q("SELECT id, bearers FROM services"):
        for b in json.loads(r["bearers"])[:1]:
            existing[b["sid"]] = r["id"]
    services = [{"short_name": s["short_name"], "medium_name": s["medium_name"],
                 "sid": s["bearers"][0]["sid"] if s["bearers"] else None,
                 "bearers": len(s["bearers"]), "logos": len(s["logos"]), "genres": len(s["genres"]),
                 "exists": bool(s["bearers"]) and s["bearers"][0]["sid"] in existing} for s in p["services"]]
    return {"id": iid, "kind": imp["kind"], "ensemble": p.get("ensemble"), "services": services,
            "warnings": p.get("warnings", []), "fixes": p.get("fixes", []), "local_logos": local,
            "remote_logos": sum(1 for s in p["services"] for l in s["logos"] if l["remote"])}


@bp.post("/api/import/legacy")
@require("editor")
def import_legacy():
    f = request.files.get("file")
    raw = f.read(importers.MAX_IMPORT_BYTES + 1) if f else (request.form.get("xml") or "").encode()
    if not raw:
        raise ApiError("Upload or paste an XML file.")
    try:
        parsed = importers.parse_legacy_si(raw)
    except ValueError as e:
        raise ApiError(str(e))
    except Exception as e:
        raise ApiError(f"Could not parse XML: {e.__class__.__name__}: {str(e)[:200]}")
    iid = _new_import("legacy", parsed)
    return jsonify(_import_summary(iid, _imports[iid]))


@bp.post("/api/import/dabmux")
@require("editor")
def import_dabmux():
    u = current_user()
    f = request.files.get("file")
    if f:
        raw = f.read(importers.MAX_IMPORT_BYTES + 1)
    else:
        path = (request.form.get("path") or "").strip()
        if not path:
            raise ApiError("Upload a file or choose one on the server.")
        if u["role"] != "admin":
            raise ApiError("Only administrators can read files on the server.", 403)
        path = os.path.realpath(path)
        if not os.path.isfile(path):
            raise ApiError("File not found.")
        with open(path, "rb") as fh:
            raw = fh.read(importers.MAX_IMPORT_BYTES + 1)
    if len(raw) > importers.MAX_IMPORT_BYTES:
        raise ApiError("File is too large.")
    try:
        parsed = importers.parse_dabmux(raw.decode("utf-8", "replace"))
    except ValueError as e:
        raise ApiError(str(e))
    iid = _new_import("dabmux", parsed)
    audit("import.dabmux.parse", f.filename if f else path)
    return jsonify(_import_summary(iid, _imports[iid]))


def _attach(imp, key, raw, w, h):
    try:
        try:
            data, mime, _, _ = media.normalise(raw, w, h)
            note = None
        except media.ImageError as e:
            if "expected" not in str(e):
                raise
            data, mime, _, _ = media.normalise(raw, w, h, fit=True)
            note = f"{str(e)} - scaled to fit"
        imp["files"][key] = {"file": media.store(data, mime), "mime": mime, "size": len(data), "note": note}
    except media.ImageError as e:
        imp["files"][key] = {"error": str(e)}


@bp.post("/api/import/<iid>/files")
@require("editor")
def import_files(iid):
    imp = _get_import(iid)
    uploads = request.files.getlist("files")
    if len(uploads) > 1000:
        raise ApiError("Too many files.")
    by_path, by_name = {}, {}
    for up in uploads:
        rel = (up.filename or "").replace("\\", "/")
        parts = [p for p in rel.split("/") if p]
        if not parts:
            continue
        by_path["/".join(parts[1:]).lower() if len(parts) > 1 else parts[0].lower()] = up
        by_name.setdefault(parts[-1].lower(), up)
    for s in imp["parsed"]["services"]:
        for l in s["logos"]:
            if l["remote"]:
                continue
            key = l["url"]
            norm = key.replace("\\", "/").lstrip("./").lower()
            up = by_path.get(norm) or by_name.get(norm.rsplit("/", 1)[-1])
            if up:
                up.stream.seek(0)
                _attach(imp, key, up.read(media.MAX_LOGO_BYTES + 1), l["width"], l["height"])
    return jsonify(_import_summary(iid, imp))


@bp.post("/api/import/<iid>/folder")
@require("admin")
def import_folder(iid):
    imp = _get_import(iid)
    folder = os.path.realpath(_str(json_body(), "path", 1024, True, "Folder"))
    if not os.path.isdir(folder):
        raise ApiError("Folder not found.")
    try:
        names = {n.lower(): n for n in os.listdir(folder)}
    except PermissionError:
        raise ApiError("The service user cannot read that folder.", 403)
    for s in imp["parsed"]["services"]:
        for l in s["logos"]:
            if l["remote"]:
                continue
            p = importers.safe_local_file(folder, l["url"])
            if not p:
                base = os.path.basename(l["url"].replace("\\", "/")).lower()
                if base in names:
                    p = importers.safe_local_file(folder, names[base])
            if p:
                with open(p, "rb") as fh:
                    _attach(imp, l["url"], fh.read(media.MAX_LOGO_BYTES + 1), l["width"], l["height"])
    audit("import.folder", folder)
    return jsonify(_import_summary(iid, imp))


@bp.post("/api/import/<iid>/commit")
@require("editor")
def import_commit(iid):
    imp = _get_import(iid)
    data = json_body()
    mode = data.get("mode", "merge")
    if mode not in ("merge", "replace", "add"):
        raise ApiError("Invalid import mode.")
    p = imp["parsed"]
    now = time.time()
    created = updated = 0
    url_logos = []
    with db.transaction():
        if mode == "replace":
            db.x("DELETE FROM logos WHERE owner_id != 0")
            db.x("DELETE FROM services")
        existing = {}
        for r in db.q("SELECT id, bearers FROM services"):
            for b in json.loads(r["bearers"])[:1]:
                existing[b["sid"]] = r["id"]
        if data.get("import_ensemble") and p.get("ensemble"):
            ens = dict(db.get_setting("ensemble"))
            for k, v in p["ensemble"].items():
                if v:
                    ens[k] = v
            db.set_setting("ensemble", ens)
        for s in p["services"]:
            fields = {k: s[k] for k in ("short_name", "medium_name", "long_name", "short_description",
                                        "long_description", "website")}
            fields["genres"] = json.dumps(s["genres"][:10])
            fields["bearers"] = json.dumps(_bearers(s["bearers"]))
            sid = existing.get(s["bearers"][0]["sid"]) if (s["bearers"] and mode == "merge") else None
            if sid:
                keep = {k: v for k, v in fields.items() if v not in ("", "[]")}
                keep["updated_at"] = now
                db.x(f"UPDATE services SET {', '.join(k + ' = ?' for k in keep)} WHERE id = ?",
                     (*keep.values(), sid))
                updated += 1
            else:
                fields.update(created_at=now, updated_at=now)
                sid = db.x(f"INSERT INTO services({','.join(fields)}) VALUES ({','.join('?' * len(fields))})",
                           tuple(fields.values())).lastrowid
                created += 1
            for l in s["logos"]:
                if l["remote"]:
                    lid = _upsert_logo(sid, l["width"], l["height"], source="url", url=l["url"])
                    url_logos.append(lid)
                else:
                    f = imp["files"].get(l["url"])
                    if f and "file" in f:
                        _upsert_logo(sid, l["width"], l["height"], source="upload", url="", file=f["file"],
                                     mime=f["mime"], size=f["size"], fetch_status="", fetch_error="",
                                     fetched_at=None)
    db.mark_dirty()
    with _imports_lock:
        _imports.pop(iid, None)
    audit(f"import.{imp['kind']}.commit", mode, {"created": created, "updated": updated})
    if url_logos:
        allow = bool(db.get_setting("allow_private_urls"))

        def fetch_all():
            for lid in url_logos:
                logo = db.q1("SELECT * FROM logos WHERE id = ?", (lid,))
                if logo:
                    build.refresh_logo(logo, allow)
        threading.Thread(target=fetch_all, daemon=True).start()
    return jsonify(created=created, updated=updated, fetching=len(url_logos))


# --- EPG API templates --------------------------------------------------------------------

def _template_row(r, usage):
    return {"id": r["id"], "name": r["name"], "sample": bool(r["sample"]), "updated_at": r["updated_at"],
            "definition": json.loads(r["definition"]), "used_by": usage.get(f"tpl:{r['id']}", 0)}


def _template_body():
    data = json_body()
    try:
        return feed_templates.validate(data.get("definition"))
    except feed_templates.TemplateError as e:
        raise ApiError(f"Template: {e}")


@bp.get("/api/feed-templates")
@require()
def list_templates():
    usage = {r["epg_feed_type"]: r["n"] for r in
             db.q("SELECT epg_feed_type, COUNT(*) AS n FROM services GROUP BY epg_feed_type")}
    rows = db.q("SELECT * FROM feed_templates ORDER BY name COLLATE NOCASE")
    return jsonify([_template_row(r, usage) for r in rows])


@bp.post("/api/feed-templates")
@require("editor")
def create_template():
    t = _template_body()
    if db.q1("SELECT id FROM feed_templates WHERE name = ?", (t["name"],)):
        raise ApiError("A template with that name already exists.")
    if db.q1("SELECT COUNT(*) AS n FROM feed_templates")["n"] >= 200:
        raise ApiError("Too many templates.")
    tid = db.x("INSERT INTO feed_templates(name, definition, sample, created_at, updated_at) VALUES (?,?,0,?,?)",
               (t["name"], json.dumps(t), time.time(), time.time())).lastrowid
    audit("template.create", t["name"])
    return jsonify(id=tid)


@bp.put("/api/feed-templates/<int:tid>")
@require("editor")
def update_template(tid):
    if not db.q1("SELECT id FROM feed_templates WHERE id = ?", (tid,)):
        raise ApiError("Template not found.", 404)
    t = _template_body()
    if db.q1("SELECT id FROM feed_templates WHERE name = ? AND id != ?", (t["name"], tid)):
        raise ApiError("A template with that name already exists.")
    db.x("UPDATE feed_templates SET name = ?, definition = ?, updated_at = ? WHERE id = ?",
         (t["name"], json.dumps(t), time.time(), tid))
    audit("template.update", t["name"])
    return jsonify(ok=True)


@bp.delete("/api/feed-templates/<int:tid>")
@require("editor")
def delete_template(tid):
    r = db.q1("SELECT * FROM feed_templates WHERE id = ?", (tid,))
    if not r:
        raise ApiError("Template not found.", 404)
    n = db.q1("SELECT COUNT(*) AS n FROM services WHERE epg_feed_type = ?", (f"tpl:{tid}",))["n"]
    if n:
        raise ApiError(f"{n} station(s) use this template - switch them to another format first.")
    db.x("DELETE FROM feed_templates WHERE id = ?", (tid,))
    audit("template.delete", r["name"])
    return jsonify(ok=True)


@bp.post("/api/feed-templates/restore-samples")
@require("editor")
def restore_templates():
    added = db.seed_sample_templates()
    audit("template.restore_samples", "", {"added": added})
    return jsonify(added=added)


@bp.post("/api/feed-templates/test")
@require("editor")
def test_template():
    t = _template_body()
    url = _url(json_body().get("url"), "Test URL")
    if not url:
        raise ApiError("Enter a URL to test with.")
    allow = bool(db.get_setting("allow_private_urls"))
    requests = []

    def fetcher(u):
        requests.append(u)
        return fetch.fetch(u, allow_private=allow, max_bytes=5 * 1024 * 1024, accept="application/json")[0]
    tz = epg.get_tz(db.get_setting("timezone"))
    try:
        progs = feed_templates.run(t, url, 7, tz, fetcher)
    except fetch.FetchError as e:
        raise ApiError(f"Fetch failed: {e}")
    except feed_templates.TemplateError as e:
        raise ApiError(str(e))
    audit("template.test", t["name"], {"url": url})
    return jsonify(count=len(progs), requests=requests[:14], timezone=str(tz), programmes=[
        {"start": p["start"], "end": p["end"], "title": p["title"], "description": p["description"][:200]}
        for p in progs[:60]])


# --- one-click update (admin) -------------------------------------------------------------

def _update_paths():
    cfg = current_app.config["ODR_CFG"]
    return {
        "request": os.path.join(cfg["data_dir"], "update-request"),
        "status": cfg.get("update_status", "/var/lib/odr-spi-generator-update/status.json"),
        "conf": cfg.get("update_conf", "/etc/odr-spi-generator/update.conf"),
        "commit": cfg.get("installed_commit", "/opt/odr-spi-generator/COMMIT"),
    }


def _read_small(path, limit=65536):
    try:
        with open(path, "rb") as f:
            return f.read(limit).decode("utf-8", "replace")
    except OSError:
        return None


def _update_info():
    paths = _update_paths()
    conf = {}
    for line in (_read_small(paths["conf"]) or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            conf[k.strip()] = v.strip()
    status = {}
    try:
        status = json.loads(_read_small(paths["status"]) or "{}")
    except ValueError:
        pass
    source = re.sub(r"(://)[^/@]*@", r"\1", conf.get("REPO_URL", ""), count=1)  # hide embedded credentials
    return {
        "enabled": bool(conf.get("REPO_URL") and conf.get("BRANCH")),
        "version": __version__,
        "current_commit": (_read_small(paths["commit"]) or "").strip(),
        "source": source, "branch": conf.get("BRANCH", ""),
        "status": status if isinstance(status, dict) else {},
        "pending": os.path.exists(paths["request"]),
    }


@bp.get("/api/update")
@require("admin")
def update_info():
    return jsonify(_update_info())


@bp.post("/api/update")
@require("admin")
def request_update():
    action = json_body().get("action")
    if action not in ("check", "apply"):
        raise ApiError("Action must be check or apply.")
    info = _update_info()
    if not info["enabled"]:
        raise ApiError("Updates are not configured - reinstall from a git checkout with install.sh.")
    if info["status"].get("state") == "running" or info["pending"]:
        raise ApiError("An update task is already running.", 409)
    path = _update_paths()["request"]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o640)
    with os.fdopen(fd, "w") as f:
        f.write(action)
    audit("update." + action)
    return jsonify(ok=True)


# --- audit --------------------------------------------------------------------------------

@bp.get("/api/audit")
@require("admin")
def audit_log():
    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        offset = 0
    rows = db.q("SELECT * FROM audit ORDER BY id DESC LIMIT 100 OFFSET ?", (offset,))
    for r in rows:
        r["details"] = json.loads(r["details"])
    return jsonify(rows)
