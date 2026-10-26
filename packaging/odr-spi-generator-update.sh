#!/usr/bin/env bash
# Root-side updater for ODR SPI Generator, started by odr-spi-generator-update.path
# when the web UI drops a request file, or by hand: sudo odr-spi-generator-update [check|apply]
#
# The request file only selects "check" or "apply"; everything else (repository,
# branch) comes from root-owned /etc/odr-spi-generator/update.conf, so the
# unprivileged web service cannot influence what gets installed.
set -uo pipefail

APP=odr-spi-generator
REQ=/var/lib/$APP/update-request
OUT=/var/lib/$APP-update
STATUS=$OUT/status.json
LOG=$OUT/update.log
CONF=/etc/$APP/update.conf
REPO=/opt/$APP/repo
COMMIT_FILE=/opt/$APP/COMMIT

umask 027
mkdir -p "$OUT"

action="${1:-}"
if [ -z "$action" ]; then
    action=check
    # never follow a symlink or read anything but a small regular file
    if [ -f "$REQ" ] && [ ! -L "$REQ" ]; then
        [ "$(head -c 16 "$REQ" | tr -cd 'a-z')" = apply ] && action=apply
    fi
    rm -f "$REQ"
fi
case "$action" in check|apply) ;; *) echo "usage: $0 [check|apply]" >&2; exit 2 ;; esac

conf() { sed -n "s/^$1=//p" "$CONF" 2>/dev/null | head -n 1; }
REPO_URL=$(conf REPO_URL)
BRANCH=$(conf BRANCH)
CURRENT=$(cat "$COMMIT_FILE" 2>/dev/null || echo unknown)

status() { # state message [remote_commit]
    python3 - "$STATUS" "$1" "$2" "${3:-}" "$CURRENT" "$action" <<'EOF'
import json, os, sys, time
path, state, message, remote, current, action = sys.argv[1:7]
old = {}
try:
    old = json.load(open(path))
except Exception:
    pass
data = {"state": state, "message": message, "action": action, "current_commit": current,
        "remote_commit": remote or old.get("remote_commit", ""), "updated_at": time.time(),
        "checked_at": time.time() if remote else old.get("checked_at")}
data["available"] = bool(data["remote_commit"]) and data["remote_commit"] != current
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(data, f)
os.replace(tmp, path)
EOF
}

fail() { status error "$1"; echo "$1" >&2; exit 1; }
gitmsg() { grep -m 1 -iE 'fatal|error' "$LOG" || tail -n 1 "$LOG"; }

[ -n "$REPO_URL" ] && [ -n "$BRANCH" ] || fail "Updates are not configured (install from a git checkout to enable them)."
[[ "$BRANCH" =~ ^[A-Za-z0-9._/-]+$ ]] || fail "Invalid branch name in $CONF."

status running "$( [ "$action" = apply ] && echo 'Downloading update…' || echo 'Checking for updates…')"

export GIT_TERMINAL_PROMPT=0
if [ ! -d "$REPO/.git" ]; then
    rm -rf "$REPO"
    git clone -q --branch "$BRANCH" --single-branch -- "$REPO_URL" "$REPO" >"$LOG" 2>&1 \
        || fail "Could not clone the update source: $(gitmsg)"
fi
git -C "$REPO" remote set-url origin "$REPO_URL"
git -C "$REPO" fetch -q origin "$BRANCH" >"$LOG" 2>&1 || fail "Could not reach the update source: $(gitmsg)"
REMOTE=$(git -C "$REPO" rev-parse FETCH_HEAD)

if [ "$action" = check ]; then
    if [ "$REMOTE" = "$CURRENT" ]; then
        status idle "You are on the latest version." "$REMOTE"
    else
        status idle "An update is available." "$REMOTE"
    fi
    exit 0
fi

if [ "$REMOTE" = "$CURRENT" ]; then
    status idle "Already up to date." "$REMOTE"
    exit 0
fi

status running "Installing update…" "$REMOTE"
git -C "$REPO" checkout -q -B "$BRANCH" FETCH_HEAD >>"$LOG" 2>&1 || fail "git checkout failed"
git -C "$REPO" reset -q --hard FETCH_HEAD >>"$LOG" 2>&1
git -C "$REPO" clean -qfdx >>"$LOG" 2>&1
if "$REPO/install.sh" --yes >>"$LOG" 2>&1; then
    CURRENT=$(cat "$COMMIT_FILE" 2>/dev/null || echo "$REMOTE")
    status idle "Updated to ${REMOTE:0:7}." "$REMOTE"
else
    fail "Installation failed - see $LOG. The previous version keeps running if the service restarted cleanly."
fi
