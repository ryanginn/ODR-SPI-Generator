"""Importers for legacy SPI/XSI service information XML and ODR-DabMux configs."""

import os
import re

from defusedxml import ElementTree as ET

from .encoder.spi_binary import genre_bytes

MAX_IMPORT_BYTES = 5 * 1024 * 1024


def fix_mojibake(text):
    """Repair UTF-8 that was decoded as Latin-1 ('RaidiÃ³' -> 'Raidió')."""
    if not text or not re.search(r"[Â-ô][\u0080-¿]", text):
        return text
    for enc in ("latin-1", "cp1252"):
        try:
            fixed = text.encode(enc).decode("utf-8")
            if fixed != text:
                return fixed
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return text


def _tag(e):
    return e.tag.rsplit("}", 1)[-1]


def _children(e, name):
    return [c for c in e if _tag(c) == name]


def _text(e, name):
    for c in e:
        if _tag(c) == name and c.text and c.text.strip():
            return c.text.strip()
    return ""


def parse_bearer_id(bid):
    """'dab:2e3.2ea1.2491.0' -> {ecc, eid, sid, scids}."""
    m = re.fullmatch(r"dab:([0-9a-fA-F])([0-9a-fA-F]{2})\.([0-9a-fA-F]{4})\.([0-9a-fA-F]{4})\.([0-9a-fA-F])",
                     (bid or "").strip())
    if not m:
        return None
    return {"ecc": m.group(2).lower(), "eid": m.group(3).lower(), "sid": m.group(4).lower(),
            "scids": int(m.group(5), 16)}


def parse_legacy_si(data: bytes):
    if len(data) > MAX_IMPORT_BYTES:
        raise ValueError("File is too large.")
    root = ET.fromstring(data, forbid_dtd=True)
    if _tag(root) != "serviceInformation":
        raise ValueError("Not an SPI serviceInformation document.")
    warnings, fixes = [], []

    def clean(s, field):
        f = fix_mojibake(s)
        if f != s:
            fixes.append(f"{field}: '{s}' -> '{f}'")
        return f

    ensemble = {}
    containers = [c for c in root if _tag(c) in ("services", "ensemble")]
    for c in containers:
        cid = (c.get("id") or "").strip().lower()
        if re.fullmatch(r"[0-9a-f]{6}", cid):
            ensemble = {"ecc": cid[:2], "eid": cid[2:]}
        elif re.fullmatch(r"[0-9a-f]{3}\.[0-9a-f]{4}", cid):  # 'e1.c185' style
            ensemble = {"ecc": cid[1:3], "eid": cid[4:]}
        if _tag(c) == "ensemble":
            ensemble.update({"short_name": clean(_text(c, "shortName"), "ensemble"),
                             "medium_name": clean(_text(c, "mediumName"), "ensemble")})

    services = []
    for c in containers:
        for s in _children(c, "service"):
            name = fix_mojibake(_text(s, "mediumName") or _text(s, "shortName"))
            svc = {
                "short_name": clean(_text(s, "shortName"), name)[:8],
                "medium_name": clean(_text(s, "mediumName"), name)[:16],
                "long_name": clean(_text(s, "longName"), name)[:128],
                "short_description": "", "long_description": "", "website": "",
                "genres": [], "bearers": [], "logos": [],
            }
            for md in _children(s, "mediaDescription"):
                sd, ld = _text(md, "shortDescription"), _text(md, "longDescription")
                if sd and not svc["short_description"]:
                    svc["short_description"] = clean(sd, name)[:180]
                if ld and not svc["long_description"]:
                    svc["long_description"] = clean(ld, name)[:1200]
                for mm in _children(md, "multimedia"):
                    url = (mm.get("url") or "").strip()
                    try:
                        w, h = int(mm.get("width") or 0), int(mm.get("height") or 0)
                    except ValueError:
                        w = h = 0
                    if not url:
                        continue
                    if not (w and h):
                        mtype = mm.get("type", "")
                        w, h = {"logo_colour_square": (32, 32), "logo_colour_rectangle": (112, 32)}.get(mtype, (0, 0))
                    if not (w and h) or w > 2000 or h > 2000:
                        warnings.append(f"{name}: logo {url} has no usable width/height - skipped")
                        continue
                    remote = url.lower().startswith(("http://", "https://"))
                    svc["logos"].append({"url": url, "width": w, "height": h, "remote": remote})
            for g in _children(s, "genre"):
                href = (g.get("href") or "").strip()
                if not href or href in svc["genres"]:
                    continue
                if genre_bytes(href) is None:
                    warnings.append(f"{name}: genre '{href}' is not a valid TV-Anytime term - skipped")
                else:
                    svc["genres"].append(href)
            for l in _children(s, "link"):
                uri = (l.get("uri") or l.get("url") or "").strip()
                if uri.lower().startswith(("http://", "https://")) and not svc["website"]:
                    svc["website"] = uri[:300]
            for b in _children(s, "bearer") + _children(s, "serviceID"):
                pb = parse_bearer_id(b.get("id"))
                if pb:
                    svc["bearers"].append(pb)
                elif b.get("id"):
                    warnings.append(f"{name}: bearer '{b.get('id')}' is not a DAB bearer - skipped")
            if not svc["bearers"]:
                warnings.append(f"{name}: no DAB bearer - imported but will be skipped until a SId is set")
            services.append(svc)
    if not ensemble and services and services[0]["bearers"]:
        b = services[0]["bearers"][0]
        ensemble = {"ecc": b["ecc"], "eid": b["eid"]}
    return {"ensemble": ensemble, "services": services, "warnings": warnings, "fixes": fixes}


def safe_local_file(folder, rel):
    """Resolve a relative logo URL inside folder; None if it escapes it."""
    if not rel or "\x00" in rel or rel.startswith("/") or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", rel):
        return None
    base = os.path.realpath(folder)
    p = os.path.realpath(os.path.join(base, rel))
    if os.path.commonpath([base, p]) != base or not os.path.isfile(p):
        return None
    return p


# --- ODR-DabMux (boost property_tree INFO format) -------------------------------------

_TOKEN = re.compile(r'\s*(?:(;[^\n]*)|(\{)|(\})|"((?:[^"\\]|\\.)*)"|([^\s{};"]+))')


def parse_info(text):
    pos, stack = 0, [{}]
    key = None
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        comment, opn, cls, quoted, word = m.groups()
        if comment:
            continue
        if opn:
            child = {}
            if key is not None:
                stack[-1][key] = child
                key = None
            stack.append(child)
        elif cls:
            if key is not None:
                stack[-1][key] = ""
                key = None
            if len(stack) > 1:
                stack.pop()
        else:
            tok = word if word is not None else re.sub(r"\\(.)", r"\1", quoted)
            if key is None:
                key = tok
            else:
                stack[-1][key] = tok
                key = None
        # a bare key followed by a newline has an empty value
        if key is not None and text[pos:pos + 1] == "\n":
            rest = re.sub(r"(\s+|;[^\n]*)+", "", text[pos:pos + 400], count=1)
            if not rest.startswith("{"):
                stack[-1][key] = ""
                key = None
    return stack[0]


def _int(v):
    v = str(v).strip().lower()
    return int(v, 16) if v.startswith("0x") else int(v)


def parse_dabmux(text):
    cfg = parse_info(text)
    ens = cfg.get("ensemble", {}) if isinstance(cfg.get("ensemble"), dict) else {}
    try:
        ecc = _int(ens.get("ecc", "0"))
        eid = _int(ens.get("id", "0"))
    except ValueError:
        raise ValueError("Could not read ensemble id/ecc from the multiplexer config.")
    out = {"ensemble": {"ecc": f"{ecc:02x}", "eid": f"{eid:04x}",
                        "medium_name": ens.get("label", "")[:16], "short_name": ens.get("shortlabel", "")[:8]},
           "services": [], "warnings": []}
    for uid, s in (cfg.get("services") or {}).items():
        if not isinstance(s, dict):
            continue
        try:
            sid = _int(s.get("id", ""))
        except ValueError:
            out["warnings"].append(f"{uid}: no valid id - skipped")
            continue
        if sid > 0xFFFF:
            continue  # data services (e.g. the SPI service itself)
        secc = s.get("ecc")
        label = s.get("label", uid)
        out["services"].append({
            "medium_name": label[:16], "short_name": (s.get("shortlabel") or label)[:8], "long_name": "",
            "short_description": "", "long_description": "", "website": "", "genres": [], "logos": [],
            "bearers": [{"ecc": f"{_int(secc):02x}" if secc else f"{ecc:02x}", "eid": f"{eid:04x}",
                         "sid": f"{sid:04x}", "scids": 0}],
        })
    return out
