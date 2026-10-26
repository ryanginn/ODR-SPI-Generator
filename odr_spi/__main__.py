"""odr-spi-generator command line.

  serve            run the web UI and scheduler (used by the systemd unit)
  setup-token      print the first-run setup token (creating one if needed)
  build            refresh URLs and rebuild the carousel from the last applied state
  reset-password   reset a user's password and print a temporary one
"""

import argparse
import logging
import os
import secrets
import sys
import time

from . import __version__, build, config, db, epg, media, security


def init(cfg):
    os.umask(0o027)
    db.init(cfg["data_dir"])
    media.init(cfg["data_dir"])
    epg.init(cfg["data_dir"])


def setup_token(cfg, create=True):
    path = os.path.join(cfg["data_dir"], "setup-token")
    if db.q1("SELECT 1 AS x FROM users LIMIT 1"):
        return None
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    if not create:
        return None
    token = secrets.token_urlsafe(18)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token)
    return token


def serve(cfg):
    from cheroot import wsgi
    from . import scheduler
    from .web import create_app

    log = logging.getLogger("odr_spi")
    token = setup_token(cfg)
    if token:
        log.warning("First-run setup: open the web UI and enter setup token %s", token)
    app = create_app(cfg)
    scheduler.start()
    if build.latest_snapshot() is not None:
        out = db.get_setting("output_path")
        if out and not os.path.exists(out):
            log.info("output file missing - rebuilding")
            try:
                build.run_async("startup")
            except RuntimeError:
                pass

    server = wsgi.Server((cfg["bind"], cfg["port"]), app, numthreads=16, request_queue_size=64,
                         server_name="odr-spi-generator")
    server.max_request_body_size = 40 * 1024 * 1024
    if cfg.get("tls_cert") and cfg.get("tls_key"):
        from cheroot.ssl.builtin import BuiltinSSLAdapter
        server.ssl_adapter = BuiltinSSLAdapter(cfg["tls_cert"], cfg["tls_key"])
    scheme = "https" if server.ssl_adapter else "http"
    log.info("MPBNL SPI WebFrontend %s listening on %s://%s:%d", __version__, scheme, cfg["bind"], cfg["port"])
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


def main(argv=None):
    p = argparse.ArgumentParser(prog="odr-spi-generator", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", help="path to config.json")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve")
    sub.add_parser("setup-token")
    sub.add_parser("build")
    rp = sub.add_parser("reset-password")
    rp.add_argument("username")
    sub.add_parser("version")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = config.load(args.config)
    if args.cmd == "version":
        print(__version__)
        return 0
    init(cfg)

    if args.cmd == "serve":
        serve(cfg)
    elif args.cmd == "setup-token":
        token = setup_token(cfg)
        if token is None:
            print("Setup is already complete - log in with an existing account "
                  "(or use: odr-spi-generator reset-password <user>).", file=sys.stderr)
            return 1
        print(token)
    elif args.cmd == "build":
        bid = build.run("cli")
        b = db.q1("SELECT * FROM builds WHERE id = ?", (bid,))
        print(f"{b['status']}: {b['message']}")
        for w in __import__("json").loads(b["warnings"]):
            print("  warning:", w)
        return 0 if b["status"] != "error" else 1
    elif args.cmd == "reset-password":
        u = db.q1("SELECT * FROM users WHERE username = ?", (args.username,))
        if not u:
            print("No such user.", file=sys.stderr)
            return 1
        pw = secrets.token_urlsafe(12)
        db.x("UPDATE users SET pw_hash = ?, must_change_pw = 1, failed_logins = 0, locked_until = 0, disabled = 0 "
             "WHERE id = ?", (security.hash_password(pw), u["id"]))
        security.destroy_user_sessions(u["id"])
        db.audit(None, "cli", "user.reset_password", u["username"])
        print(f"Temporary password for {u['username']}: {pw}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
