"""Snapshotting, URL refresh and carousel generation."""

import hashlib
import json
import logging
import os
import secrets
import stat
import threading
import time
import zlib
from datetime import datetime, timedelta, timezone

from . import db, epg, feed_templates, fetch, media
from .encoder import mot, msc, spi_binary

log = logging.getLogger("odr_spi.build")

BITRATES = tuple(range(8, 97, 8))
SLOW_CYCLE = "slow_cycle"
SLOW_CYCLE_SECONDS = 300
_lock = threading.Lock()
_state = {"running": False, "build_id": None}


def packet_size_for(bitrate):
    """Largest DAB packet size that fits a whole number of times into one 24 ms
    frame (bitrate x 3 bytes), as recommended by Opendigitalradio:
    8->24, 16->48, 24->72, 32->96, 48->72, 64->96 ... 96->96."""
    frame = int(bitrate) * 3
    return next(s for s in (96, 72, 48, 24) if frame % s == 0)


def fmt_duration(seconds):
    m, s = divmod(int(round(seconds)), 60)
    return f"{m} min {s} s" if m else f"{s} s"


def warning_key(text):
    """Stable identity of a warning, used to remember dismissals across builds."""
    if text.startswith("Carousel takes "):
        return SLOW_CYCLE
    return "w:" + hashlib.sha1(text.encode()).hexdigest()[:16]


def split_dismissed(warnings, stats):
    """Separate warnings the user dismissed. A dismissed slow-carousel warning
    comes back if the cycle grows more than 25% beyond the dismissed length."""
    dismissed = db.get_setting("dismissed_warnings") or {}
    keep, hidden = [], []
    for w in warnings:
        key = warning_key(w)
        if key in dismissed and (key != SLOW_CYCLE
                                 or stats.get("cycle_seconds", 0) <= float(dismissed[key]) * 1.25):
            hidden.append(w)
        else:
            keep.append(w)
    return keep, hidden


def parse_hex(v, bits):
    if isinstance(v, int):
        n = v
    else:
        v = (v or "").strip().lower()
        if v.startswith("0x"):
            v = v[2:]
        n = int(v, 16)
    if not 0 <= n < (1 << bits):
        raise ValueError("out of range")
    return n


# --- snapshot ---------------------------------------------------------------------------

def current_state():
    """Everything a build needs, as plain JSON-able data."""
    services = db.q("SELECT * FROM services ORDER BY sort, id")
    logos = db.q("SELECT * FROM logos ORDER BY owner_id, width, height")
    progs = db.q("SELECT * FROM programmes ORDER BY service_id, id")
    for s in services:
        s["genres"] = json.loads(s["genres"])
        s["bearers"] = json.loads(s["bearers"])
        s["logos"] = [l for l in logos if l["owner_id"] == s["id"]]
        s["programmes"] = [dict(p, genres=json.loads(p["genres"])) for p in progs if p["service_id"] == s["id"]]
    settings = db.all_settings()
    return {
        "ensemble": settings["ensemble"],
        "ensemble_logos": [l for l in logos if l["owner_id"] == 0],
        "services": services,
        "settings": {k: settings[k] for k in ("output_path", "bitrate", "packet_address", "datagroup_mode",
                                                "write_mode", "epg_days", "timezone", "optimise_logos")},
    }


def latest_snapshot():
    r = db.q1("SELECT * FROM snapshots ORDER BY id DESC LIMIT 1")
    return json.loads(r["data"]) if r else None


def save_snapshot(user):
    data = current_state()
    db.x("INSERT INTO snapshots(created_at, user_id, data) VALUES (?,?,?)",
         (time.time(), user["id"] if user else None, json.dumps(data)))
    # keep the last 20 snapshots
    db.x("DELETE FROM snapshots WHERE id NOT IN (SELECT id FROM snapshots ORDER BY id DESC LIMIT 20)")
    db.set_meta("dirty_since", "")
    return data


def referenced_media():
    names = {r["file"] for r in db.q("SELECT file FROM logos WHERE file != ''")}
    for r in db.q("SELECT data FROM snapshots"):
        d = json.loads(r["data"])
        for l in d.get("ensemble_logos", []):
            names.add(l.get("file"))
        for s in d.get("services", []):
            for l in s.get("logos", []):
                names.add(l.get("file"))
    names.discard("")
    names.discard(None)
    return names


# --- refresh ----------------------------------------------------------------------------

def refresh_logo(logo, allow_private):
    """Fetch a URL logo; on failure keep the existing file. Returns error text or ''."""
    now = time.time()
    try:
        data, _, _ = fetch.fetch(logo["url"], allow_private=allow_private, max_bytes=media.MAX_LOGO_BYTES,
                                 accept="image/png,image/jpeg")
        data, mime, w, h = media.normalise(data, logo["width"], logo["height"])
        name = media.store(data, mime)
        db.x("UPDATE logos SET file=?, mime=?, size=?, fetch_status='ok', fetch_error='', fetched_at=? WHERE id=?",
             (name, mime, len(data), now, logo["id"]))
        return ""
    except (fetch.FetchError, media.ImageError) as e:
        db.x("UPDATE logos SET fetch_status='error', fetch_error=?, fetched_at=? WHERE id=?",
             (str(e)[:300], now, logo["id"]))
        return str(e)


def refresh_feed(service, allow_private):
    now = time.time()
    try:
        if service["epg_feed_type"].startswith("tpl:"):
            row = db.q1("SELECT definition FROM feed_templates WHERE id = ?",
                        (int(service["epg_feed_type"][4:]),))
            if not row:
                raise feed_templates.TemplateError("the feed's API template has been deleted")
            days = max(7, int(db.get_setting("epg_days") or 0))
            progs = feed_templates.run(
                feed_templates.validate(json.loads(row["definition"])), service["epg_feed_url"], days,
                epg.get_tz(db.get_setting("timezone")),
                lambda u: fetch.fetch(u, allow_private=allow_private, max_bytes=5 * 1024 * 1024,
                                      accept="application/json")[0])
        else:
            data, _, _ = fetch.fetch(service["epg_feed_url"], allow_private=allow_private,
                                     max_bytes=20 * 1024 * 1024)
            progs = epg.parse_feed(data, service["epg_feed_type"], service["epg_feed_channel"])
        horizon_lo = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        horizon_hi = (datetime.now(timezone.utc) + timedelta(days=35)).isoformat()
        progs = [p for p in progs if horizon_lo <= p["start"] <= horizon_hi][:5000]
        epg.save_feed(service["id"], progs)
        db.x("UPDATE services SET epg_feed_status=?, epg_feed_checked=? WHERE id=?",
             (f"ok: {len(progs)} programmes", now, service["id"]))
        return ""
    except Exception as e:  # parse errors from arbitrary feeds included
        msg = str(e)[:300] if isinstance(e, fetch.FetchError) else f"{e.__class__.__name__}: {str(e)[:250]}"
        db.x("UPDATE services SET epg_feed_status=?, epg_feed_checked=? WHERE id=?",
             ("error: " + msg, now, service["id"]))
        return msg


def refresh_all():
    """Fetch every URL logo and EPG feed. Returns a list of warning strings."""
    allow_private = bool(db.get_setting("allow_private_urls"))
    warnings = []
    for logo in db.q("SELECT * FROM logos WHERE source = 'url'"):
        err = refresh_logo(logo, allow_private)
        if err:
            warnings.append(f"Logo {logo['width']}x{logo['height']} ({logo['url'][:80]}): {err} - kept previous image")
    for s in db.q("SELECT * FROM services WHERE epg_feed_url != ''"):
        err = refresh_feed(s, allow_private)
        if err:
            warnings.append(f"EPG feed for {s['medium_name'] or s['id']}: {err} - kept previous data")
    return warnings


def _refresh_snapshot_files(snap):
    """URL logos in the published snapshot follow the latest successfully
    fetched file for the same URL/size."""
    current = {(l["url"], l["width"], l["height"]): l for l in db.q("SELECT * FROM logos WHERE source='url'")}
    for l in snap["ensemble_logos"] + [x for s in snap["services"] for x in s["logos"]]:
        if l["source"] == "url":
            c = current.get((l["url"], l["width"], l["height"]))
            if c and c["file"]:
                l.update(file=c["file"], mime=c["mime"], size=c["size"])


# --- generation -------------------------------------------------------------------------

def _tid_allocator():
    used = set()

    def alloc(key=None):
        tid = (zlib.crc32(key.encode()) & 0xFFFF) if key else secrets.randbelow(0x10000)
        while tid in used or tid == 0:
            tid = (tid + 1) & 0xFFFF
        used.add(tid)
        return tid
    return alloc


def generate(snap, now=None):
    """Return (stream_bytes, stats, warnings)."""
    now = now or datetime.now(timezone.utc)
    warnings = []
    s = snap["settings"]
    ens = snap["ensemble"]
    try:
        ecc, eid = parse_hex(ens["ecc"], 8), parse_hex(ens["eid"], 16)
    except (ValueError, KeyError):
        raise ValueError("Ensemble ECC/EId are not configured.")
    alloc = _tid_allocator()
    objects = []
    version = int(now.timestamp()) & 0x7FFFFFFF

    logo_sizes = []  # (bytes, label) for the stats breakdown
    optimise = s.get("optimise_logos", True)

    def logo_objects(owner_key, logos, label):
        refs = []
        for l in logos:
            if not l.get("file"):
                if l["source"] == "url":
                    warnings.append(f"{owner_key}: {l['width']}x{l['height']} logo URL has never been fetched")
                continue
            try:
                if optimise:
                    body, mime = media.broadcast_variant(l["file"], l["mime"])
                else:
                    body, mime = media.read(l["file"]), l["mime"]
            except (OSError, ValueError):
                warnings.append(f"{owner_key}: {l['width']}x{l['height']} logo file is missing")
                continue
            ext = "png" if mime == "image/png" else "jpg"
            name = f"{owner_key}_{l['width']}x{l['height']}_{l['file'][:8]}.{ext}"
            ct = mot.CT_IMAGE_PNG if mime == "image/png" else mot.CT_IMAGE_JFIF
            objects.append(mot.MotObject(name, body, ct, alloc(name))
                           .add(mot.UniqueBodyVersion(zlib.crc32(body))))
            refs.append((name, mime, l["width"], l["height"]))
            logo_sizes.append((len(body), f"{label} {l['width']}x{l['height']}"))
        return refs

    ensemble = {"ecc": ecc, "eid": eid, "short_name": ens.get("short_name", ""),
                "medium_name": ens.get("medium_name", ""),
                "media": logo_objects(f"ens{eid:04x}", snap["ensemble_logos"],
                                      ens.get("medium_name") or "Ensemble")}

    tz = epg.get_tz(s.get("timezone"))
    today = now.astimezone(tz).date()
    epg_days = max(0, min(int(s.get("epg_days") or 0), 14))
    services = []
    pi_count = 0
    for svc in snap["services"]:
        if not svc["enabled"]:
            continue
        bearers = []
        for b in svc["bearers"]:
            try:
                bearers.append((parse_hex(b.get("ecc") or ens["ecc"], 8), parse_hex(b.get("eid") or ens["eid"], 16),
                                parse_hex(b["sid"], 16), int(b.get("scids") or 0) & 0xF))
            except (ValueError, KeyError, TypeError):
                warnings.append(f"{svc['medium_name']}: invalid bearer {b} skipped")
        if not bearers:
            warnings.append(f"{svc['medium_name'] or svc['id']}: no valid bearer (SId) - service skipped")
            continue
        key = f"{bearers[0][2]:04x}"
        services.append({
            "short_name": svc["short_name"], "medium_name": svc["medium_name"], "long_name": svc["long_name"],
            "bearers": bearers, "media": logo_objects(key, svc["logos"], svc["medium_name"] or key),
            "short_description": svc["short_description"], "long_description": svc["long_description"],
            "genres": svc["genres"], "links": [svc["website"]] if svc["website"] else [],
        })
        if svc["epg_enabled"] and epg_days:
            feed = epg.load_feed(svc["id"]) if svc.get("epg_feed_url") else []
            for d in range(epg_days):
                day = today + timedelta(days=d)
                progs = epg.expand_day(svc["programmes"], feed, day, tz)
                if not progs:
                    continue
                start = datetime.combine(day, datetime.min.time()).replace(tzinfo=tz)
                end = start + timedelta(days=1)
                pdata = [{
                    "crid": f"crid://odr-spi/{key}/{epg.short_id(key, p['start'])}",
                    "short_id": epg.short_id(key, p["start"]),
                    "short_name": p["short_title"][:8], "medium_name": p["title"][:16],
                    "long_name": p["title"] if len(p["title"]) > 16 else "",
                    "start": p["start"], "duration": int((p["end"] - p["start"]).total_seconds()),
                    "short_description": p["description"][:180],
                    "long_description": p["description"] if len(p["description"]) > 180 else "",
                    "genres": p["genres"],
                } for p in progs]
                body = spi_binary.programme_information(bearers[0], start, end, pdata, created=now)
                name = f"pi_{key}_{day.strftime('%Y%m%d')}"
                objects.append(mot.MotObject(name, body, mot.CT_SPI_PI, alloc(name))
                               .add(mot.UniqueBodyVersion(zlib.crc32(body)))
                               .add(mot.ScopeStart(start)).add(mot.ScopeEnd(end))
                               .add(mot.ScopeId(spi_binary.content_id(*bearers[0]))))
                pi_count += 1

    si = spi_binary.service_information(ensemble, services)
    objects.insert(0, mot.MotObject("0", si, mot.CT_SPI_SI, alloc("0"))
                   .add(mot.UniqueBodyVersion(version))
                   .add(mot.ScopeId(spi_binary.ensemble_id(ecc, eid))))

    groups = msc.encode_directorymode(objects, alloc)
    bitrate = int(s.get("bitrate") or 16)
    if s.get("datagroup_mode"):
        stream = b"".join(groups)
    else:
        stream = b"".join(msc.encode_packets(groups, address=int(s.get("packet_address") or 1),
                                             size=packet_size_for(bitrate)))
    payload = sum(len(o.body) for o in objects)
    logo_bytes = sum(b for b, _ in logo_sizes)
    epg_bytes = sum(len(o.body) for o in objects if o.content_type == mot.CT_SPI_PI)
    stats = {
        "services": len(services), "objects": len(objects), "logos": len(logo_sizes),
        "epg_objects": pi_count, "payload_bytes": payload, "stream_bytes": len(stream),
        "logo_bytes": logo_bytes, "epg_bytes": epg_bytes, "si_bytes": len(si),
        "overhead_bytes": len(stream) - payload,
        "largest_logos": [{"label": label, "bytes": b} for b, label in sorted(logo_sizes, reverse=True)[:5]],
        "bitrate": bitrate, "cycle_seconds": round(len(stream) * 8 / (bitrate * 1000), 1),
    }
    if stats["cycle_seconds"] > SLOW_CYCLE_SECONDS:
        biggest = max((logo_bytes, "logos"), (epg_bytes, "EPG"), (len(si), "service information"))
        warnings.append(f"Carousel takes {fmt_duration(stats['cycle_seconds'])} to cycle at {bitrate} kbps - "
                        f"{biggest[1]} make up {biggest[0] * 100 // max(payload, 1)}% of it; consider a higher "
                        "bitrate, fewer EPG days or smaller logos")
    return stream, stats, warnings


def check_output_path(path):
    if not path or not os.path.isabs(path):
        raise ValueError("Output path must be an absolute path.")
    if not path.endswith(".dat"):
        raise ValueError("Output file name must end in .dat")
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        raise ValueError(f"Directory {parent} does not exist.")
    if os.path.lexists(path):
        st = os.lstat(path)
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            raise ValueError("Output path exists and is not a regular file (symlinks are refused).")
    if not os.access(parent, os.W_OK) and not (os.path.exists(path) and os.access(path, os.W_OK)):
        raise ValueError(f"The service user cannot write to {parent}.")


def write_output(path, stream, mode):
    check_output_path(path)
    if mode == "atomic":
        tmp = os.path.join(os.path.dirname(path), f".{os.path.basename(path)}.{secrets.token_hex(4)}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, "wb") as f:
            os.fchmod(f.fileno(), 0o644)  # odr-dabmux usually runs as another user
            f.write(stream)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    else:
        # in place: ODR-DabMux keeps the file open and rewinds at EOF, so the
        # same inode must be rewritten for it to pick up the new carousel
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, "wb") as f:
            os.fchmod(f.fileno(), 0o644)
            f.write(stream)
            f.truncate()
            f.flush()
            os.fsync(f.fileno())


# --- orchestration ----------------------------------------------------------------------

def status():
    return dict(_state)


def run(trigger, user=None, apply_changes=False, refresh=True):
    """Run a build synchronously. Returns the build row id."""
    if not _lock.acquire(blocking=False):
        raise RuntimeError("A build is already running.")
    try:
        _state.update(running=True)
        bid = db.x("INSERT INTO builds(started_at, trigger, user_id, username) VALUES (?,?,?,?)",
                   (time.time(), trigger, user["id"] if user else None, user["username"] if user else "")).lastrowid
        _state["build_id"] = bid
        warnings = []
        try:
            if refresh:
                warnings += refresh_all()
            if apply_changes:
                snap = save_snapshot(user)
            else:
                snap = latest_snapshot()
                if snap is None:
                    raise ValueError("Nothing has been applied yet.")
            _refresh_snapshot_files(snap)
            stream, stats, w = generate(snap)
            warnings += w
            warnings, hidden = split_dismissed(warnings, stats)
            stats["dismissed_warnings"] = len(hidden)
            write_output(snap["settings"]["output_path"], stream, snap["settings"].get("write_mode", "inplace"))
            db.x("UPDATE builds SET finished_at=?, status=?, message=?, stats=?, warnings=? WHERE id=?",
                 (time.time(), "warning" if warnings else "ok",
                  f"Wrote {stats['stream_bytes']:,} bytes to {snap['settings']['output_path']}",
                  json.dumps(stats), json.dumps(warnings[:200]), bid))
            db.set_meta("last_success", time.time())
        except Exception as e:
            log.exception("build failed")
            msg = str(e) if isinstance(e, (ValueError, OSError)) else f"{e.__class__.__name__}: {e}"
            db.x("UPDATE builds SET finished_at=?, status='error', message=?, warnings=? WHERE id=?",
                 (time.time(), msg[:500], json.dumps(warnings[:200]), bid))
        db.x("DELETE FROM builds WHERE id NOT IN (SELECT id FROM builds ORDER BY id DESC LIMIT 500)")
        return bid
    finally:
        _state.update(running=False)
        _lock.release()


def run_async(trigger, user=None, apply_changes=False):
    if _state["running"]:
        raise RuntimeError("A build is already running.")
    t = threading.Thread(target=run, args=(trigger, user, apply_changes), daemon=True)
    t.start()
