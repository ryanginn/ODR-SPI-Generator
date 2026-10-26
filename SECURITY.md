# Security

## Model

| Actor | Trust |
| :-- | :-- |
| **Administrator** | Fully trusted. Can choose the output file, browse server directories (names only), read files on the server for imports, manage users and allow fetching from private networks. |
| **Editor** | Trusted with all station data, the ensemble and imports. No server filesystem access, users or settings. |
| **Station owner** | Untrusted outside their assigned stations. Can change logos, descriptions, website, genres and EPG only for those stations. Can publish only if an admin allows it. |
| **Network** | Untrusted. Anyone who can reach the port must log in, except for first-run setup, which needs the token from the installer. |

## Controls

- **Authentication**: scrypt password hashes (N=2¹⁵, r=8). Minimum 10 characters. An account locks for 15 minutes after 8 failures. Login attempts are rate-limited per IP. Lookups of unknown usernames take the same time as real ones. Temporary passwords must be changed at first login.
- **Sessions**: 256-bit random tokens, stored server-side only as SHA-256 hashes. The cookie is `HttpOnly` and `SameSite=Strict`, and `Secure` over HTTPS. Sessions expire after an absolute lifetime and after 8 hours idle. Changing a password, resetting it, disabling the user or changing their role signs out other sessions.
- **CSRF**: every state-changing request needs a custom `X-Requested-With` header, which forces a CORS preflight. Logged-in requests also need a per-session CSRF token. Cross-origin `Origin`/`Referer` headers are rejected.
- **First-run takeover protection**: the first admin can only be created with a random setup token. It is written `0600` by the service and removed once setup is done.
- **Authorization**: checked on the server for every route. Station access is checked on every service, logo, programme and media request. Station owners get redacted build information, with no server paths and no other stations' warnings.
- **XSS**: the UI builds its DOM from text nodes only (no `innerHTML` or `eval`). A strict CSP (`script-src 'self'`, no inline code, `frame-ancestors 'none'`) is set, and uploaded images are served with `sandbox`.
- **Uploads**: only PNG and JPEG, at most 2 MB, with a decompression-bomb limit. Every image is decoded and re-encoded, so no file bytes from users are served or broadcast unchanged.
- **XML**: parsed with `defusedxml` with DTDs forbidden, which blocks XXE and entity expansion.
- **SSRF**: only `http(s)`. URLs with embedded credentials are refused. Every redirect hop is resolved and checked against private, loopback, link-local and reserved ranges unless an admin allows them. The connection is pinned to the checked address, which blocks DNS rebinding. Responses are size-capped.
- **Filesystem**: imported logo paths are confined to the chosen folder (realpath containment). The output must be an absolute `.dat` path. Symlinks are refused, and the file is opened with `O_NOFOLLOW`.
- **SQL**: every query is parameterised. Column names come only from fixed server-side lists.
- **Service**: runs as an unprivileged user, never root. The systemd sandbox has no capabilities, `NoNewPrivileges`, `ProtectSystem=full`, `PrivateTmp`/`PrivateDevices`, a syscall filter and `MemoryDenyWriteExecute`. `systemd-analyze security` exposure is 1.9 ("OK").
- **One-click updates**: the web service never updates itself. An admin's click writes a request file that holds only `check` or `apply`. A root-owned systemd path unit then runs the updater, which pulls from the git source and branch recorded in root-owned `/etc/odr-spi-generator/update.conf` at install time. The request file is never followed if it is a symlink, and status is written to a separate root-owned directory. A compromised web service can therefore start an update but cannot choose what gets installed. Updating does run the fetched `install.sh` as root, so only install from a repository you control.
- **Audit log**: logins, failures and every change, with user and IP address.

## Audit (v2.0.0)

The release was reviewed for injection (SQL, command, XXE, path traversal), authentication and session flaws, privilege escalation between roles, CSRF, XSS, SSRF, unsafe deserialization and data exposure.

| Finding | Severity | Status |
| :-- | :-- | :-- |
| `/api/status` returned the latest build's warnings and message to station owners. They could see other stations' logo/EPG URLs and the server output path. `/api/builds` already redacted these. | Medium | **Fixed**: shared redaction for both endpoints, with a regression test |

Verified as sound: authorization on every route, including programme updates bound to the existing row's station. Also verified: parameterised SQL with fixed column lists, `/media` scoping, CSRF layers, session handling, SSRF guard (redirects, rebinding), defusedxml use, path containment, DOM construction without `innerHTML`, image re-encoding, setup-token handling and the installer.

Residual risks and recommendations:

- **Use HTTPS.** Plain HTTP exposes passwords and session cookies on the network. Use the built-in TLS or a reverse proxy (see the README).
- **Admins can read server directory names and parse files** readable by the service user. Give the admin role only to people who should have that access.
- A locked account returns a distinct message, which shows that the account exists. This is an accepted usability trade-off.

## Reporting

Please report vulnerabilities privately to the repository owner rather than in a public issue.
