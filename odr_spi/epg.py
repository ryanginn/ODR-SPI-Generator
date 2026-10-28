"""EPG schedule expansion and feed parsing (XMLTV and SPI Programme Information XML;
JSON APIs are handled by feed_templates)."""

import json
import os
import re
import zlib
from datetime import date, datetime, time, timedelta, timezone

from defusedxml import ElementTree as ET

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover
    ZoneInfo = None

_cache_dir = None


def init(data_dir):
    global _cache_dir
    _cache_dir = os.path.join(data_dir, "epg-cache")
    os.makedirs(_cache_dir, mode=0o750, exist_ok=True)


def get_tz(name):
    if name and ZoneInfo:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return datetime.now().astimezone().tzinfo


def valid_tz(name):
    if not name:
        return True
    try:
        ZoneInfo(name)
        return True
    except Exception:
        return False


def _cache_path(service_id):
    return os.path.join(_cache_dir, f"{int(service_id)}.json")


def save_feed(service_id, programmes):
    tmp = _cache_path(service_id) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(programmes, f)
    os.replace(tmp, _cache_path(service_id))


def load_feed(service_id):
    try:
        with open(_cache_path(service_id)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def delete_feed(service_id):
    try:
        os.remove(_cache_path(service_id))
    except OSError:
        pass


def _local(day, hhmm, tz):
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.combine(day, time(h, m)).replace(tzinfo=tz)


def expand_day(entries, feed, day: date, tz):
    """Return the programmes starting on `day` (local time) for one service,
    sorted, with hand-entered entries taking precedence over feed entries."""
    start_of_day = datetime.combine(day, time(0)).replace(tzinfo=tz)
    end_of_day = datetime.combine(day + timedelta(days=1), time(0)).replace(tzinfo=tz)
    manual = []
    for e in entries:
        if e["kind"] == "weekly":
            if not (e["days"] >> day.weekday()) & 1:
                continue
            if e.get("valid_from") and day.isoformat() < e["valid_from"]:
                continue
            if e.get("valid_to") and day.isoformat() > e["valid_to"]:
                continue
        elif e.get("date") != day.isoformat():
            continue
        start = _local(day, e["start_time"], tz)
        manual.append({
            "start": start, "end": start + timedelta(minutes=e["duration"]),
            "title": e["title"], "short_title": e.get("short_title", ""),
            "description": e.get("description", ""), "genres": e.get("genres", []),
        })
    out = list(manual)
    for p in feed:
        try:
            start = datetime.fromisoformat(p["start"])
            end = datetime.fromisoformat(p["end"])
        except (KeyError, ValueError):
            continue
        if not (start_of_day <= start < end_of_day) or end <= start:
            continue
        if any(start < m["end"] and m["start"] < end for m in manual):
            continue
        out.append({"start": start, "end": end, "title": p.get("title", ""), "short_title": "",
                    "description": p.get("description", ""), "genres": p.get("genres", [])})
    out.sort(key=lambda p: p["start"])
    return [p for p in out if p["title"]]


def short_id(service_key, start: datetime):
    v = zlib.crc32(f"{service_key}/{start.astimezone(timezone.utc).isoformat()}".encode()) & 0xFFFFFF
    return v or 1


# --- feed parsing -----------------------------------------------------------------------

def _strip_ns(tag):
    return tag.rsplit("}", 1)[-1]


def _xmltv_time(s):
    s = s.strip()
    m = re.match(r"(\d{14})\s*([+-]\d{4})?", s)
    if not m:
        raise ValueError(s)
    t = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    off = m.group(2) or "+0000"
    sign = 1 if off[0] == "+" else -1
    return t.replace(tzinfo=timezone(sign * timedelta(hours=int(off[1:3]), minutes=int(off[3:5]))))


def _iso_duration(s):
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", s.strip())
    if not m:
        raise ValueError(s)
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return timedelta(days=d, hours=h, minutes=mi, seconds=se)


def parse_feed(data: bytes, feed_type: str, channel: str = ""):
    """Return a list of {start, end, title, description, genres} with ISO times."""
    root = ET.fromstring(data, forbid_dtd=True)
    out = []
    if feed_type == "xmltv":
        for p in root.iter("programme"):
            if channel and p.get("channel") != channel:
                continue
            try:
                start = _xmltv_time(p.get("start", ""))
                end = _xmltv_time(p.get("stop", "")) if p.get("stop") else None
            except ValueError:
                continue
            title = (p.findtext("title") or "").strip()
            desc = (p.findtext("desc") or "").strip()
            out.append({"start": start, "end": end, "title": title, "description": desc, "genres": []})
        out.sort(key=lambda p: p["start"])
        for i, p in enumerate(out):  # XMLTV stop is optional: run until the next programme
            if p["end"] is None:
                p["end"] = out[i + 1]["start"] if i + 1 < len(out) else p["start"] + timedelta(hours=1)
    else:  # SPI / RadioDNS programme information XML
        for p in root.iter():
            if _strip_ns(p.tag) != "programme":
                continue
            names = {}
            desc = ""
            genres = []
            times = []
            for c in p.iter():
                tag = _strip_ns(c.tag)
                if tag in ("shortName", "mediumName", "longName") and c.text:
                    names[tag] = c.text.strip()
                elif tag in ("shortDescription", "longDescription") and c.text and not desc:
                    desc = c.text.strip()
                elif tag == "genre" and c.get("href"):
                    genres.append(c.get("href"))
                elif tag == "time" and c.get("time") and c.get("duration"):
                    try:
                        t = datetime.fromisoformat(c.get("time").replace("Z", "+00:00"))
                        times.append((t, t + _iso_duration(c.get("duration"))))
                    except ValueError:
                        continue
            title = names.get("longName") or names.get("mediumName") or names.get("shortName") or ""
            for start, end in times[:1]:
                out.append({"start": start, "end": end, "title": title, "description": desc, "genres": genres})
    result = []
    for p in out:
        if p["start"].tzinfo is None:
            p["start"] = p["start"].replace(tzinfo=timezone.utc)
            p["end"] = p["end"].replace(tzinfo=timezone.utc)
        result.append({"start": p["start"].isoformat(), "end": p["end"].isoformat(),
                       "title": p["title"][:128], "description": p["description"][:1200],
                       "genres": p["genres"][:8]})
    return result

