"""Flask application factory, request security and permission helpers."""

import hmac
import os
import secrets
from functools import wraps
from urllib.parse import urlsplit

from flask import Flask, abort, g, jsonify, request, send_from_directory

from .. import db, security

COOKIE = "odrspi_session"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# fields a station owner may change on their own services
STATION_FIELDS = {"short_description", "long_description", "website", "genres"}
ALL_SERVICE_FIELDS = STATION_FIELDS | {"short_name", "medium_name", "long_name", "bearers", "enabled", "sort"}


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def client_ip():
    return request.remote_addr or ""


def current_user():
    return getattr(g, "user", None)


def require(role=None):
    """Require a logged-in user; role 'editor' admits admins too."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                raise ApiError("Not logged in.", 401)
            if u["must_change_pw"] and request.endpoint not in ("api.change_password", "api.logout", "api.state"):
                raise ApiError("You must change your password first.", 403)
            if role == "admin" and u["role"] != "admin":
                raise ApiError("Administrator access required.", 403)
            if role == "editor" and u["role"] not in ("admin", "editor"):
                raise ApiError("Editor access required.", 403)
            return fn(*a, **kw)
        return wrapper
    return deco


def is_editor(u):
    return u and u["role"] in ("admin", "editor")


def allowed_service_ids(u):
    if is_editor(u):
        return None  # all
    return {r["service_id"] for r in db.q("SELECT service_id FROM user_services WHERE user_id = ?", (u["id"],))}


def check_service_access(u, service_id):
    ids = allowed_service_ids(u)
    if ids is not None and int(service_id) not in ids:
        raise ApiError("You do not have access to this station.", 403)
    if not db.q1("SELECT id FROM services WHERE id = ?", (service_id,)):
        raise ApiError("Station not found.", 404)


def can_apply(u):
    return bool(u) and (is_editor(u) or bool(u["can_apply"]))


def audit(action, target="", details=None):
    db.audit(current_user(), client_ip(), action, target, details)


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Expected a JSON object body.")
    return data


def create_app(cfg):
    app = Flask(__name__, static_folder=None)
    app.config.update(MAX_CONTENT_LENGTH=40 * 1024 * 1024, JSON_SORT_KEYS=False)
    app.secret_key = secrets.token_bytes(32)  # unused (server-side sessions), set for safety
    app.config["ODR_CFG"] = cfg

    if cfg.get("behind_proxy"):
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    @app.before_request
    def load_user():
        g.user = None
        g.session_token = request.cookies.get(COOKIE)
        if g.session_token:
            s = security.load_session(g.session_token)
            if s:
                g.user = {"id": s["user_id"], "username": s["username"], "display_name": s["display_name"],
                          "role": s["role"], "can_apply": s["can_apply"], "must_change_pw": s["must_change_pw"],
                          "csrf": s["csrf"]}
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            _check_origin()
            if request.path.startswith("/api/"):
                if request.headers.get("X-Requested-With") != "odr-spi":
                    abort(403)
                if g.user and not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), g.user["csrf"]):
                    raise ApiError("Invalid CSRF token - reload the page.", 403)

    @app.after_request
    def headers(resp):
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.is_secure:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        resp.headers.pop("Server", None)
        return resp

    @app.errorhandler(ApiError)
    def api_error(e):
        return jsonify(error=str(e)), e.status

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error="Upload is too large."), 413

    @app.errorhandler(404)
    def not_found(_):
        if request.path.startswith("/api/"):
            return jsonify(error="Not found."), 404
        return index()

    @app.errorhandler(403)
    def forbidden(_):
        return jsonify(error="Forbidden."), 403

    @app.errorhandler(500)
    def server_error(_):
        return jsonify(error="Internal server error - see the service log (journalctl -u odr-spi-generator)."), 500

    from .api import bp
    app.register_blueprint(bp)

    @app.route("/static/<path:name>")
    def static_files(name):
        resp = send_from_directory(STATIC_DIR, name, max_age=0)
        return resp

    @app.route("/")
    def index():
        resp = send_from_directory(STATIC_DIR, "index.html", max_age=0)
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    return app


def _check_origin():
    """Reject cross-site state-changing requests (defence in depth on top of
    SameSite=Strict cookies and the CSRF token)."""
    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if not origin:
        return
    if urlsplit(origin).netloc != request.host:
        abort(403)
