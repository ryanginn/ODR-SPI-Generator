"""Outbound HTTP(S) fetching for logo URLs and EPG feeds.

Guards against server-side request forgery: only http/https, every hop's
host is resolved once and the connection is pinned to that address (no DNS
rebinding), private/loopback/link-local targets are refused unless the admin
allows them, redirects are re-validated, and responses are size-capped."""

import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urljoin, urlsplit

from . import __version__

USER_AGENT = f"ODR-SPI-Generator/{__version__}"
TIMEOUT = 15
MAX_REDIRECTS = 4


class FetchError(Exception):
    pass


def validate_url(url: str):
    if not isinstance(url, str) or len(url) > 2048:
        raise FetchError("URL is too long.")
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("Only http:// and https:// URLs are supported.")
    if parts.username or parts.password:
        raise FetchError("URLs with embedded credentials are not allowed.")
    return parts


def _is_public(ip):
    ip = ipaddress.ip_address(ip)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def _resolve(host, port, allow_private):
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise FetchError(f"Could not resolve host {host}.")
    addrs = []
    for family, _, _, _, sockaddr in infos:
        ip = sockaddr[0]
        if not allow_private and not _is_public(ip):
            raise FetchError(f"{host} resolves to a private or reserved address, which is not allowed.")
        addrs.append((family, sockaddr))
    if not addrs:
        raise FetchError(f"Could not resolve host {host}.")
    return addrs[0]


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, port, addr, **kw):
        super().__init__(host, port, **kw)
        self._addr = addr

    def connect(self):
        family, sockaddr = self._addr
        self.sock = socket.socket(family, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(sockaddr)


class _PinnedHTTPSConnection(_PinnedHTTPConnection):
    def connect(self):
        super().connect()
        ctx = ssl.create_default_context()
        self.sock = ctx.wrap_socket(self.sock, server_hostname=self.host)


def fetch(url, allow_private=False, max_bytes=2 * 1024 * 1024, accept="*/*"):
    """Return (bytes, content_type, final_url)."""
    for _ in range(MAX_REDIRECTS + 1):
        parts = validate_url(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        addr = _resolve(parts.hostname, port, allow_private)
        cls = _PinnedHTTPSConnection if parts.scheme == "https" else _PinnedHTTPConnection
        c = cls(parts.hostname, port, addr, timeout=TIMEOUT)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        try:
            c.request("GET", path, headers={"User-Agent": USER_AGENT, "Accept": accept,
                                            "Accept-Encoding": "identity"})
            r = c.getresponse()
            if r.status in (301, 302, 303, 307, 308):
                loc = r.getheader("Location")
                if not loc:
                    raise FetchError(f"HTTP {r.status} without Location header.")
                url = urljoin(url, loc)
                continue
            if r.status != 200:
                raise FetchError(f"HTTP {r.status} {r.reason}")
            length = r.getheader("Content-Length")
            if length and length.isdigit() and int(length) > max_bytes:
                raise FetchError("Response is too large.")
            data = r.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise FetchError("Response is too large.")
            return data, (r.getheader("Content-Type") or "").split(";")[0].strip(), url
        except (OSError, http.client.HTTPException) as e:
            raise FetchError(f"Connection failed: {e.__class__.__name__}: {e}"[:300])
        finally:
            c.close()
    raise FetchError("Too many redirects.")
