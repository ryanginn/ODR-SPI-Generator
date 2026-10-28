#!/usr/bin/env bash
# MPBNL SPI WebFrontend installer.
#
#   sudo ./install.sh                 interactive install / upgrade
#   sudo ./install.sh --yes           accept defaults
#   sudo ./install.sh --port 8090 --bind 0.0.0.0 --user odr
#
# Re-running the installer upgrades the code and keeps config and data.
set -euo pipefail
# installed files must be readable by the unprivileged service user, whatever
# umask the caller has (the one-click updater runs with 027)
umask 022

APP=odr-spi-generator
PREFIX=/opt/$APP
CONF_DIR=/etc/$APP
CONF=$CONF_DIR/config.json
DATA=/var/lib/$APP
UNIT=/etc/systemd/system/$APP.service
WRAPPER=/usr/local/bin/$APP
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PORT=""
BIND=""
RUN_USER=""
ASSUME_YES=0

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  \033[36m•\033[0m %s\n' "$*"; }
ok() { printf '  \033[32m✔\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die() { printf '\033[31mError:\033[0m %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
    case "$1" in
        --port) PORT="$2"; shift 2 ;;
        --bind) BIND="$2"; shift 2 ;;
        --user) RUN_USER="$2"; shift 2 ;;
        -y|--yes) ASSUME_YES=1; shift ;;
        -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
        *) die "unknown option $1" ;;
    esac
done

ask() { # ask "question" default -> echoes answer
    local q="$1" def="$2" a
    if [ "$ASSUME_YES" = 1 ] || [ ! -t 0 ]; then echo "$def"; return; fi
    read -r -p "  $q [$def]: " a </dev/tty || true
    echo "${a:-$def}"
}

[ "$(id -u)" = 0 ] || die "run as root: sudo $0"
command -v systemctl >/dev/null || die "systemd is required"
[ -f "$SRC/odr_spi/__init__.py" ] || die "run this script from the source directory (the git checkout)"

bold "MPBNL SPI WebFrontend installer"
UPGRADE=0
[ -f "$CONF" ] && UPGRADE=1 && info "Existing installation found - upgrading (config and data are kept)."

# ---------------------------------------------------------------- packages
if command -v apt-get >/dev/null; then
    info "Installing system packages…"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq python3 python3-venv python3-pip python3-pil python3-defusedxml \
        tzdata ca-certificates curl git >/dev/null
    ok "System packages installed"
else
    warn "Not a Debian/Ubuntu system - make sure python3 (>= 3.9) with venv, Pillow build deps and curl are installed."
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || die "Python 3.9 or newer is required"

# ---------------------------------------------------------------- settings
if [ "$UPGRADE" = 1 ]; then
    PORT=$(python3 -c "import json;print(json.load(open('$CONF')).get('port', 8090))")
    BIND=$(python3 -c "import json;print(json.load(open('$CONF')).get('bind', '0.0.0.0'))")
    [ -z "$RUN_USER" ] && [ -f "$UNIT" ] && RUN_USER=$(sed -n 's/^User=//p' "$UNIT")
fi
[ -z "$PORT" ] && PORT=$(ask "Web UI port" 8090)
[ -z "$BIND" ] && BIND=$(ask "Listen address (0.0.0.0 = all interfaces, 127.0.0.1 = behind a reverse proxy)" 0.0.0.0)
[[ "$PORT" =~ ^[0-9]+$ ]] && [ "$PORT" -ge 1 ] && [ "$PORT" -le 65535 ] || die "invalid port $PORT"

if [ -z "$RUN_USER" ]; then
    DEFAULT_USER=odr-spi
    if id odr >/dev/null 2>&1; then DEFAULT_USER=odr; fi
    info "The service user needs write access to the folder you will choose for the SPI output file."
    [ "$DEFAULT_USER" = odr ] && info "An 'odr' user exists (ODR-mmbTools) - running as it lets you write into its folders."
    RUN_USER=$(ask "Run the service as user" "$DEFAULT_USER")
fi
if ! id "$RUN_USER" >/dev/null 2>&1; then
    [ "$RUN_USER" = odr-spi ] || die "user $RUN_USER does not exist"
    useradd --system --home-dir "$DATA" --no-create-home --shell /usr/sbin/nologin odr-spi
    ok "Created system user odr-spi"
fi
[ "$RUN_USER" = root ] && die "refusing to run the web service as root"
RUN_GROUP=$(id -gn "$RUN_USER")

# ---------------------------------------------------------------- code
# The running service is left up while the new code is installed and only
# restarted at the end; if anything fails, make sure it is running again
# (one-click updates run this unattended, so nobody would notice otherwise).
on_exit() {
    local rc=$?
    if [ "$rc" -ne 0 ] && [ -f "$UNIT" ] && ! systemctl is-active --quiet "$APP"; then
        warn "Installation failed - starting $APP again"
        systemctl start "$APP" 2>/dev/null || true
    fi
}
trap on_exit EXIT

info "Installing application to $PREFIX…"
mkdir -p "$PREFIX"
rm -rf "$PREFIX/src"
mkdir -p "$PREFIX/src"
cp -r "$SRC/odr_spi" "$SRC/pyproject.toml" "$SRC/README.md" "$SRC/LICENSE" "$PREFIX/src/"
find "$PREFIX/src" -name '__pycache__' -prune -exec rm -rf {} +
if [ ! -x "$PREFIX/venv/bin/python" ]; then
    python3 -m venv --system-site-packages "$PREFIX/venv"
fi
"$PREFIX/venv/bin/pip" install -q --upgrade pip >/dev/null 2>&1 || true
"$PREFIX/venv/bin/pip" install -q "$PREFIX/src" || die "pip install failed"
# record the installed commit and, for git checkouts, where updates come from
srcgit() { git -c safe.directory="$SRC" -C "$SRC" "$@"; }  # SRC may belong to another user
COMMIT=unknown
if srcgit rev-parse HEAD >/dev/null 2>&1; then
    COMMIT=$(srcgit rev-parse HEAD)
fi
echo "$COMMIT" > "$PREFIX/COMMIT"
chown -R root:root "$PREFIX"
# readable (not writable) by the service user; this also repairs installs
# made with a restrictive umask, which pip would otherwise keep
chmod 755 "$PREFIX"
chmod -R u=rwX,go=rX "$PREFIX/venv" "$PREFIX/src"
chmod 644 "$PREFIX/COMMIT"
[ -d "$PREFIX/repo" ] && chmod 700 "$PREFIX/repo"   # updater checkout: root only
ok "Application installed (${COMMIT:0:7})"

cat > "$WRAPPER" <<EOF
#!/bin/sh
# Runs odr-spi-generator commands as the service user.
export ODR_SPI_CONFIG=$CONF
if [ "\$(id -u)" = 0 ]; then
    exec runuser -u $RUN_USER -- $PREFIX/venv/bin/odr-spi-generator "\$@"
fi
exec $PREFIX/venv/bin/odr-spi-generator "\$@"
EOF
chmod 755 "$WRAPPER"

# ---------------------------------------------------------------- config & data
mkdir -p "$CONF_DIR"
if [ ! -f "$CONF" ]; then
    cat > "$CONF" <<EOF
{
  "bind": "$BIND",
  "port": $PORT,
  "data_dir": "$DATA",
  "tls_cert": "",
  "tls_key": "",
  "behind_proxy": false
}
EOF
fi
chown root:"$RUN_GROUP" "$CONF_DIR" "$CONF"
chmod 750 "$CONF_DIR"
chmod 640 "$CONF"
mkdir -p "$DATA"
chown -R "$RUN_USER:$RUN_GROUP" "$DATA"
chmod 750 "$DATA"

# one-click updates: the web UI drops a request file, a root-only path unit runs
# the updater against the git source recorded here (never anything from the UI)
REPO_URL=$(srcgit remote get-url origin 2>/dev/null || true)
BRANCH=$(srcgit rev-parse --abbrev-ref HEAD 2>/dev/null || true)
if [ -n "$REPO_URL" ] && [ -n "$BRANCH" ] && [ "$BRANCH" != HEAD ]; then
    printf 'REPO_URL=%s\nBRANCH=%s\n' "$REPO_URL" "$BRANCH" > "$CONF_DIR/update.conf"
    chown root:"$RUN_GROUP" "$CONF_DIR/update.conf"
    chmod 640 "$CONF_DIR/update.conf"
    ok "Updates from $BRANCH of ${REPO_URL##*@}"
else
    warn "Not installed from a git checkout - one-click updates are disabled."
fi
install -d -m 2750 -o root -g "$RUN_GROUP" "/var/lib/$APP-update"
install -m 755 "$SRC/packaging/$APP-update.sh" "/usr/local/sbin/$APP-update"
install -m 644 "$SRC/packaging/$APP-update.service" "/etc/systemd/system/$APP-update.service"
install -m 644 "$SRC/packaging/$APP-update.path" "/etc/systemd/system/$APP-update.path"

# ---------------------------------------------------------------- systemd
CAPS=""
[ "$PORT" -lt 1024 ] && CAPS="CAP_NET_BIND_SERVICE"
sed -e "s/@USER@/$RUN_USER/" -e "s/@GROUP@/$RUN_GROUP/" -e "s/@CAPS@/$CAPS/" \
    "$SRC/packaging/$APP.service" > "$UNIT"
chmod 644 "$UNIT"
systemctl daemon-reload
systemctl enable "$APP" >/dev/null 2>&1
systemctl enable --now "$APP-update.path" >/dev/null 2>&1
systemctl restart "$APP"

info "Waiting for the service to start…"
responds() {
    curl -fsS "http://127.0.0.1:$PORT/api/state" >/dev/null 2>&1 \
        || curl -fsSk "https://127.0.0.1:$PORT/api/state" >/dev/null 2>&1
}
main_pid() { systemctl show -p MainPID --value "$APP" 2>/dev/null; }
# healthy = active and answering, and still the same process a few seconds
# later (a crash-looping service can be briefly "active" between restarts)
for _ in $(seq 1 30); do
    if systemctl is-active --quiet "$APP" && responds; then
        PID=$(main_pid)
        sleep 3
        if systemctl is-active --quiet "$APP" && [ "$(main_pid)" = "$PID" ] && responds; then
            STARTED=1; break
        fi
    fi
    sleep 1
done
[ "${STARTED:-0}" = 1 ] || { journalctl -u "$APP" -n 30 --no-pager; die "service did not start - see the log above"; }
ok "Service $APP is running"

TOKEN=$("$WRAPPER" setup-token 2>/dev/null || true)
SCHEME=http
grep -q '"tls_cert": "[^"]' "$CONF" && SCHEME=https
HOSTS=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -v ':' | grep -v '^$' || true)
[ "$BIND" != "0.0.0.0" ] && HOSTS=$BIND
[ -z "$HOSTS" ] && HOSTS=$(hostname)

echo
bold "Installation complete."
echo
echo "  Open the web UI:"
for h in $HOSTS; do
    if [ -n "$TOKEN" ]; then echo "    $SCHEME://$h:$PORT/?token=$TOKEN"; else echo "    $SCHEME://$h:$PORT/"; fi
done
echo
if [ -n "$TOKEN" ]; then
    echo "  First-run setup token: $TOKEN"
    echo "  (show it again with: sudo $APP setup-token)"
    echo
fi
echo "  Service:   systemctl status $APP    ·    logs: journalctl -u $APP -f"
echo "  Runs as:   $RUN_USER  (it needs write access to the SPI output folder you choose)"
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
    warn "ufw is active - allow the port if needed: sudo ufw allow $PORT/tcp"
fi
if [ "$SCHEME" = http ] && [ "$BIND" != "127.0.0.1" ]; then
    warn "The UI is served over plain HTTP. On untrusted networks put it behind an HTTPS reverse proxy"
    warn "or set tls_cert/tls_key in $CONF (see README)."
fi
