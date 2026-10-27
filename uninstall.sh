#!/usr/bin/env bash
# Remove MPBNL SPI WebFrontend.
#   sudo ./uninstall.sh           keep configuration and data (/etc, /var/lib)
#   sudo ./uninstall.sh --purge   also delete configuration, data and the odr-spi user
set -euo pipefail
APP=odr-spi-generator
[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
systemctl disable --now "$APP" "$APP-update.path" 2>/dev/null || true
rm -f "/etc/systemd/system/$APP.service" "/etc/systemd/system/$APP-update.service" \
    "/etc/systemd/system/$APP-update.path" "/usr/local/bin/$APP" "/usr/local/sbin/$APP-update"
systemctl daemon-reload
rm -rf "/opt/$APP"
if [ "${1:-}" = "--purge" ]; then
    rm -rf "/etc/$APP" "/var/lib/$APP" "/var/lib/$APP-update"
    id odr-spi >/dev/null 2>&1 && userdel odr-spi || true
    echo "Removed $APP including configuration and data."
else
    echo "Removed $APP. Configuration (/etc/$APP) and data (/var/lib/$APP) were kept."
fi
echo "The SPI output .dat file was not touched."
