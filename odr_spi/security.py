"""Password hashing, sessions and login throttling."""

import base64
import hashlib
import hmac
import secrets
import threading
import time

from . import db

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 15, 8, 1
SCRYPT_MAXMEM = 64 * 1024 * 1024

MIN_PASSWORD_LEN = 10
MAX_PASSWORD_LEN = 256
LOCKOUT_THRESHOLD = 8
LOCKOUT_SECONDS = 15 * 60

IDLE_TIMEOUT = 8 * 3600

# each scrypt call uses ~32 MB; cap concurrency so a login flood cannot exhaust memory
_hash_slots = threading.BoundedSemaphore(3)

_b64 = lambda b: base64.b64encode(b).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    with _hash_slots:
        dk = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                            maxmem=SCRYPT_MAXMEM, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, dk = stored.split("$")
        if algo != "scrypt":
            return False
        with _hash_slots:
            calc = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r),
                                  p=int(p), maxmem=SCRYPT_MAXMEM, dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except (ValueError, TypeError):
        return False


# a hash to burn equivalent CPU time when the username does not exist
_DUMMY_HASH = None


def dummy_verify(password):
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_hex(8))
    verify_password(password, _DUMMY_HASH)


def password_problem(password: str, username: str = ""):
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters."
    if len(password) > MAX_PASSWORD_LEN:
        return "Password is too long."
    if username and username.lower() in password.lower():
        return "Password must not contain the username."
    if len(set(password)) < 5:
        return "Password is too repetitive."
    return None


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id, ip, user_agent, hours):
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    now = time.time()
    db.x("INSERT INTO sessions(token_hash, user_id, csrf, created_at, last_seen, expires_at, ip, user_agent) "
         "VALUES (?,?,?,?,?,?,?,?)",
         (_token_hash(token), user_id, csrf, now, now, now + hours * 3600, ip, (user_agent or "")[:200]))
    return token, csrf


def load_session(token):
    if not token or len(token) > 128:
        return None
    now = time.time()
    s = db.q1("SELECT s.*, u.username, u.display_name, u.role, u.can_apply, u.disabled, u.must_change_pw "
              "FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?", (_token_hash(token),))
    if not s or s["expires_at"] < now or s["disabled"]:
        if s:
            db.x("DELETE FROM sessions WHERE token_hash = ?", (s["token_hash"],))
        return None
    if now - s["last_seen"] > IDLE_TIMEOUT:
        db.x("DELETE FROM sessions WHERE token_hash = ?", (s["token_hash"],))
        return None
    if now - s["last_seen"] > 60:
        db.x("UPDATE sessions SET last_seen = ? WHERE token_hash = ?", (now, s["token_hash"]))
    return s


def destroy_session(token):
    db.x("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


def destroy_user_sessions(user_id, except_token=None):
    if except_token:
        db.x("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (user_id, _token_hash(except_token)))
    else:
        db.x("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def purge_sessions():
    db.x("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))


class RateLimiter:
    """Sliding-window limiter keyed by e.g. client IP."""

    def __init__(self, limit, window):
        self.limit, self.window = limit, window
        self.hits = {}
        self.lock = threading.Lock()

    def hit(self, key) -> bool:
        now = time.time()
        with self.lock:
            if len(self.hits) > 10000:
                self.hits = {k: v for k, v in self.hits.items() if v and v[-1] > now - self.window}
            q = [t for t in self.hits.get(key, []) if t > now - self.window]
            allowed = len(q) < self.limit
            if allowed:
                q.append(now)
            self.hits[key] = q
            return allowed


login_limiter = RateLimiter(20, 15 * 60)
setup_limiter = RateLimiter(10, 15 * 60)
