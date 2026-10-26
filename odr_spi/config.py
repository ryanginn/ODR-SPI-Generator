"""Daemon configuration (/etc/odr-spi-generator/config.json).

Only things needed before the web UI is reachable live here; everything else
is stored in the database and edited through the UI."""

import json
import os

DEFAULT_PATH = "/etc/odr-spi-generator/config.json"

DEFAULTS = {
    "bind": "0.0.0.0",
    "port": 8090,
    "data_dir": "/var/lib/odr-spi-generator",
    "tls_cert": "",
    "tls_key": "",
    # set true only when running behind a reverse proxy that sets X-Forwarded-For/-Proto
    "behind_proxy": False,
}


def load(path=None):
    path = path or os.environ.get("ODR_SPI_CONFIG", DEFAULT_PATH)
    cfg = dict(DEFAULTS)
    if os.path.exists(path):
        with open(path) as f:
            cfg.update(json.load(f))
    for key in ("bind", "data_dir"):
        env = os.environ.get("ODR_SPI_" + key.upper())
        if env:
            cfg[key] = env
    if os.environ.get("ODR_SPI_PORT"):
        cfg["port"] = int(os.environ["ODR_SPI_PORT"])
    cfg["port"] = int(cfg["port"])
    return cfg
