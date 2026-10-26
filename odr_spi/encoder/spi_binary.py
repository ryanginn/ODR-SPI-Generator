"""SPI binary encoding (ETSI TS 102 371) for Service Information and
Programme Information documents."""

from datetime import datetime, timezone

from .mot import mjd

# element tags
T_CDATA = 0x01
T_EPG = 0x02
T_SERVICE_INFORMATION = 0x03
T_SHORT_NAME = 0x10
T_MEDIUM_NAME = 0x11
T_LONG_NAME = 0x12
T_MEDIA_DESCRIPTION = 0x13
T_GENRE = 0x14
T_LINK = 0x18
T_LOCATION = 0x19
T_SHORT_DESCRIPTION = 0x1A
T_LONG_DESCRIPTION = 0x1B
T_PROGRAMME = 0x1C
T_SCHEDULE = 0x21
T_SCOPE = 0x24
T_SERVICE_SCOPE = 0x25
T_ENSEMBLE = 0x26
T_SERVICE = 0x28
T_MULTIMEDIA = 0x2B
T_TIME = 0x2C
T_BEARER = 0x2D

LOGO_UNRESTRICTED = 0x02
LOGO_COLOUR_SQUARE = 0x04

GENRE_CS = {
    "IntentionCS": 1, "FormatCS": 2, "ContentCS": 3, "OriginationCS": 5,
    "ContentAlertCS": 6, "MediaTypeCS": 7, "AtmosphereCS": 8,
}


def _length(n: int) -> bytes:
    if n <= 253:
        return bytes([n])
    if n <= 0xFFFF:
        return bytes([0xFE]) + n.to_bytes(2, "big")
    if n <= 0xFFFFFF:
        return bytes([0xFF]) + n.to_bytes(3, "big")
    raise ValueError("element too large")


def el(tag: int, *parts: bytes) -> bytes:
    data = b"".join(p for p in parts if p)
    return bytes([tag]) + _length(len(data)) + data


attr = el  # attributes share the tag/length/value layout


def cdata(text: str) -> bytes:
    return el(T_CDATA, text.encode("utf-8"))


def text_el(tag: int, text: str) -> bytes:
    return el(tag, cdata(text)) if text else b""


def u8(tag, v):
    return attr(tag, bytes([v & 0xFF]))


def u16(tag, v):
    return attr(tag, (v & 0xFFFF).to_bytes(2, "big"))


def u24(tag, v):
    return attr(tag, (v & 0xFFFFFF).to_bytes(3, "big"))


def s(tag, v: str):
    return attr(tag, v.encode("utf-8"))


def content_id(ecc: int, eid: int, sid: int, scids: int = 0) -> bytes:
    """DAB contentId with ensemble flag set and a 16-bit SId."""
    return bytes([0x40 | (scids & 0x0F), ecc & 0xFF]) + (eid & 0xFFFF).to_bytes(2, "big") \
        + (sid & 0xFFFF).to_bytes(2, "big")


def ensemble_id(ecc: int, eid: int) -> bytes:
    return bytes([ecc & 0xFF]) + (eid & 0xFFFF).to_bytes(2, "big")


def timepoint(t: datetime) -> bytes:
    """Encode a timepoint in UTC (no local time offset)."""
    if t.tzinfo:
        t = t.astimezone(timezone.utc)
    v = mjd(t.date()) << 14
    if t.second:
        v = ((v | (1 << 11) | (t.hour << 6) | t.minute) << 16) | (t.second << 10)
        return v.to_bytes(6, "big")
    return (v | (t.hour << 6) | t.minute).to_bytes(4, "big")


def genre_bytes(href: str):
    """urn:tva:metadata:cs:ContentCS:2002:3.6.8 -> b'\\x03\\x06\\x08'.

    Returns None when the href is not a valid TV-Anytime classification term."""
    parts = href.split(":")
    if len(parts) < 7 or parts[0] != "urn" or parts[4] not in GENRE_CS:
        return None
    cs = GENRE_CS[parts[4]]
    try:
        levels = [int(x) for x in parts[6].split(".")]
    except ValueError:
        return None
    if not levels or levels[0] != cs or any(not 0 <= x <= 255 for x in levels):
        return None
    return bytes([cs]) + bytes(levels[1:])


def multimedia(url: str, mime: str, width: int, height: int) -> bytes:
    logo_type = LOGO_COLOUR_SQUARE if (width, height) == (32, 32) else LOGO_UNRESTRICTED
    return el(T_MEDIA_DESCRIPTION, el(
        T_MULTIMEDIA,
        s(0x82, url), u8(0x83, logo_type), u16(0x84, width), u16(0x85, height), s(0x80, mime),
    ))


def names(short: str, medium: str, long: str = "") -> bytes:
    return text_el(T_SHORT_NAME, short[:8]) + text_el(T_MEDIUM_NAME, medium[:16]) \
        + text_el(T_LONG_NAME, long[:128])


def descriptions(short: str, long: str) -> bytes:
    out = b""
    if short:
        out += el(T_MEDIA_DESCRIPTION, text_el(T_SHORT_DESCRIPTION, short[:180]))
    if long:
        out += el(T_MEDIA_DESCRIPTION, text_el(T_LONG_DESCRIPTION, long[:1200]))
    return out


def genres(hrefs) -> bytes:
    out = b""
    for href in hrefs:
        g = genre_bytes(href)
        if g:
            out += el(T_GENRE, attr(0x80, g))
    return out


def service_information(ensemble: dict, services: list, originator="ODR") -> bytes:
    """ensemble: {ecc, eid, short_name, medium_name, media:[...]}
    service: {short_name, medium_name, long_name, bearers:[(ecc,eid,sid,scids)],
              media:[(url,mime,w,h)], short_description, long_description, genres, links}"""
    ens = [attr(0x80, ensemble_id(ensemble["ecc"], ensemble["eid"])),
           names(ensemble.get("short_name", ""), ensemble.get("medium_name", ""))]
    ens += [multimedia(*m) for m in ensemble.get("media", [])]
    for svc in services:
        parts = [names(svc.get("short_name", ""), svc.get("medium_name", ""), svc.get("long_name", ""))]
        parts += [el(T_BEARER, attr(0x80, content_id(*b))) for b in svc["bearers"]]
        parts += [multimedia(*m) for m in svc.get("media", [])]
        parts.append(descriptions(svc.get("short_description", ""), svc.get("long_description", "")))
        parts.append(genres(svc.get("genres", [])))
        parts += [el(T_LINK, s(0x80, url)) for url in svc.get("links", []) if url]
        ens.append(el(T_SERVICE, *parts))
    return el(T_SERVICE_INFORMATION, u16(0x80, 1), s(0x82, originator), el(T_ENSEMBLE, *ens))


def programme_information(bearer, start: datetime, end: datetime, programmes: list,
                          created: datetime, originator="ODR") -> bytes:
    """bearer: (ecc, eid, sid, scids).  programme: {crid, short_id, short_name,
    medium_name, long_name, start (aware datetime), duration (seconds),
    short_description, long_description, genres}"""
    cid = content_id(*bearer)
    progs = []
    for p in programmes:
        progs.append(el(
            T_PROGRAMME,
            s(0x80, p["crid"]), u24(0x81, p["short_id"]),
            names(p.get("short_name", ""), p.get("medium_name", ""), p.get("long_name", "")),
            el(T_LOCATION,
               el(T_TIME, attr(0x80, timepoint(p["start"])), u16(0x81, min(p["duration"], 0xFFFF))),
               el(T_BEARER, attr(0x80, cid))),
            descriptions(p.get("short_description", ""), p.get("long_description", "")),
            genres(p.get("genres", [])),
        ))
    scope = el(T_SCOPE, attr(0x80, timepoint(start)), attr(0x81, timepoint(end)),
               el(T_SERVICE_SCOPE, attr(0x80, cid)))
    return el(T_EPG, el(T_SCHEDULE, attr(0x81, timepoint(created)), s(0x82, originator), scope, *progs))
