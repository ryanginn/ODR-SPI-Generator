"""Declarative EPG API templates.

A template describes how to turn an arbitrary JSON schedule API into
programmes, without running any code from the template:

  fetch        "per_weekday" - one request per weekday (day=Monday ...)
               "per_date"    - one request per calendar date (day=2026-10-27)
               "once"        - a single request that covers the whole week
  day_param    query parameter set to the day value (ignored when the URL
               contains a {day} placeholder)
  day_value    how the day is written: tokens {weekday} Monday,
               {weekday_lower} monday, {weekday_short} Mon, {weekday_num}
               1-7 (Monday = 1), {date} 2026-10-27, {yyyymmdd} 20261027
  items_path   dotted path to the list of shows in the response, may use the
               day tokens (e.g. "{weekday_lower}" for {"monday": [...]})
  title, description, start, end, duration, days
               dotted field paths inside each show; "a|b" tries a then b
  time_format  "clock" (HH:MM[:SS] on that day, 24:00 = midnight),
               "datetime" (YYYY-MM-DD HH:MM[:SS] local), "iso" or "unix"

  format       "json" (above), or "text" for a dated text listing: a web
               page or published document where a line holding a date
               (7.11.2026) starts each day and "H.MM Title" / "HH:MM Title"
               lines start programmes; other lines describe the programme
               before them
  format       "html" for a weekly timetable on a web page, read by CSS class:
               html_item (one per programme), html_title, html_time
               ("06:00" or "06:00 - 10:00"), html_days ("Monday-Thursday",
               "ma-pe", "arkisin" ...; empty = every day), html_description
  timezone     IANA zone the times are in (empty = the server's setting)
  title_split  text listing only: "|"-separated markers; text from the first
               marker on moves from the title to the description

The station's feed URL is supplied separately, so one template serves any
number of stations using the same API.
"""

import json
import re
from datetime import date, datetime, time, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
FETCH_MODES = ("per_weekday", "per_date", "once")
FORMATS = ("json", "text", "html")
HTML_FIELDS = ("html_item", "html_title", "html_time", "html_days", "html_description")
_CLASS = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
TIME_FORMATS = ("clock", "datetime", "iso", "unix")
FIELDS = ("title", "description", "start", "end", "duration", "days")
MAX_ITEMS = 1000

_HMS = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")
_PATH = re.compile(r"^[\w\-{}.|]*$")
_TOKEN = re.compile(r"\{(\w+)\}")

SAMPLES = [
    {
        "name": "MPBNL",
        "description": "JSON list of shows, one request per weekday (day=Monday ... Sunday). "
                       "Shows have showname, showdesc, days, fromTime and tilTime.",
        "example_url": "https://example.com/api/getShowDay?id=1&day=Monday",
        "fetch": "per_weekday", "day_param": "day", "day_value": "{weekday}", "items_path": "",
        "title": "showname", "description_field": "showdesc", "start": "fromTime", "end": "tilTime",
        "duration": "", "days": "days", "time_format": "clock",
    },
    {
        "name": "Coast FM",
        "description": "One JSON file for the whole week, keyed by weekday: "
                       "{\"monday\": [{start, end, title, description}, ...], ...}.",
        "example_url": "https://www.coast.fm/canary-islands/data/schedule.json",
        "fetch": "once", "timezone": "Atlantic/Canary", "day_param": "", "day_value": "", "items_path": "{weekday_lower}",
        "title": "title", "description_field": "description", "start": "start", "end": "end",
        "duration": "", "days": "", "time_format": "clock",
    },
    {
        "name": "Radio Slovenija (RTV SLO)",
        "description": "RTV Slovenija catch-up API, one request per date (day=YYYY-MM-DD). "
                       "Pick the station with station= (ra1, ra2 = Val 202, ra3 ...).",
        "example_url": "https://api.rtvslo.si/pipes/catchup?client_id=82013fb3a531d5414f478747c1aca622"
                       "&day=2026-10-27&station=ra2",
        "fetch": "per_date", "timezone": "Europe/Ljubljana", "day_param": "day", "day_value": "{date}",
        "items_path": "response.items",
        "title": "title", "description_field": "napovednik", "start": "start_time", "end": "end_time",
        "duration": "duration", "days": "", "time_format": "clock",
    },
    {
        "name": "Rayo / Planet Radio (Bauer)",
        "description": "Bauer Media listen API behind rayo.fi, planetradio.co.uk and the Rayo apps. One request covers "
                       "the coming week: put the station code in the URL (e.g. nfi = Radio Nova). Use +14%20days "
                       "for two weeks.",
        "example_url": "https://listenapi.planetradio.co.uk/api9.2/schedule/nfi/today/+7%20days",
        "fetch": "once", "day_param": "", "day_value": "", "items_path": "{date}",
        "title": "title", "description_field": "shortdesc", "start": "start", "end": "",
        "duration": "duration", "days": "", "time_format": "iso",
    },
    {
        "name": "Järviradio (published Google Doc)",
        "description": "Text listing: the week's programme as a published Google Doc. A date line "
                       "(LAUANTAI 07.11.2026) starts each day and \"9.30 Title\" lines start programmes; "
                       "phone numbers and \"toim.\" credits move to the description.",
        "example_url": "https://docs.google.com/document/d/e/2PACX-1vStDvnIht6MdcyKTzMipUiDJeZhoj87UlktQMhzpp_F0"
                       "tEOtzDX6wgkxnsfstncsxPlqfrBrJUczjBP/pub?embedded=true",
        "format": "text", "fetch": "once", "timezone": "Europe/Helsinki",
        "title_split": " puh.| puh | toim.|, seurassanne",
        "day_param": "", "day_value": "", "items_path": "", "title": "", "description_field": "", "start": "",
        "end": "", "duration": "", "days": "", "time_format": "clock",
    },    {
        "name": "Sea FM (WordPress radio theme)",
        "description": "Weekly timetable on a WordPress site using the QantumThemes radio theme (also used by "
                       "other stations): each programme has a title, a start time and its days, e.g. "
                       "\"06:00 Monday-Thursday\".",
        "example_url": "https://www.seafm.fi/ohjelma/",
        "format": "html", "fetch": "once", "timezone": "Europe/Helsinki", "title_split": "",
        "html_item": "qt-part-show-schedule-day-item", "html_title": "qt-item-title", "html_time": "qt-time",
        "html_days": "qt-day", "html_description": "qt-ellipsis-2",
        "day_param": "", "day_value": "", "items_path": "", "title": "", "description_field": "", "start": "",
        "end": "", "duration": "", "days": "", "time_format": "clock",
    },
]


class TemplateError(ValueError):
    pass


def _s(d, key, maxlen, default=""):
    v = d.get(key, default)
    if v is None:
        v = ""
    if not isinstance(v, str):
        raise TemplateError(f"{key} must be text")
    v = v.strip()
    if len(v) > maxlen or "\x00" in v:
        raise TemplateError(f"{key} is too long")
    return v


def validate(d):
    """Normalise a template definition, raising TemplateError on bad input."""
    if not isinstance(d, dict):
        raise TemplateError("template must be an object")
    t = {
        "name": _s(d, "name", 64),
        "description": _s(d, "description", 500),
        "example_url": _s(d, "example_url", 500),
        "fetch": _s(d, "fetch", 16, "per_weekday"),
        "day_param": _s(d, "day_param", 64),
        "day_value": _s(d, "day_value", 64),
        "items_path": _s(d, "items_path", 200),
        "title": _s(d, "title", 200),
        "description_field": _s(d, "description_field", 200),
        "start": _s(d, "start", 200),
        "end": _s(d, "end", 200),
        "duration": _s(d, "duration", 200),
        "days": _s(d, "days", 200),
        "time_format": _s(d, "time_format", 16, "clock"),
        "format": _s(d, "format", 8, "json") or "json",
        "timezone": _s(d, "timezone", 64),
        "title_split": _s(d, "title_split", 200),
        **{k: _s(d, k, 80) for k in HTML_FIELDS},
    }
    if not t["name"]:
        raise TemplateError("name is required")
    if t["format"] not in FORMATS:
        raise TemplateError("format must be json or text")
    if t["timezone"]:
        try:
            ZoneInfo(t["timezone"])
        except Exception:
            raise TemplateError(f"unknown timezone {t['timezone']}")
    if t["format"] in ("text", "html"):
        if t["fetch"] != "once":
            raise TemplateError("a text listing or HTML timetable is fetched with one request")
        if t["format"] == "html":
            for k in HTML_FIELDS:
                if t[k] and not _CLASS.match(t[k]):
                    raise TemplateError(f"{k} must be a single CSS class name")
            if not (t["html_item"] and t["html_title"] and t["html_time"]):
                raise TemplateError("an HTML timetable needs the item, title and time classes")
        return t
    if t["fetch"] not in FETCH_MODES:
        raise TemplateError("fetch must be one of " + ", ".join(FETCH_MODES))
    if t["time_format"] not in TIME_FORMATS:
        raise TemplateError("time_format must be one of " + ", ".join(TIME_FORMATS))
    if not t["title"] or not t["start"]:
        raise TemplateError("title and start fields are required")
    if not (t["end"] or t["duration"]):
        raise TemplateError("set an end or a duration field")
    for k in ("items_path", "title", "description_field", "start", "end", "duration", "days"):
        if not _PATH.match(t[k]):
            raise TemplateError(f"{k} may only contain letters, digits, _ - . | and {{tokens}}")
    for k in ("day_value", "items_path"):
        for tok in _TOKEN.findall(t[k]):
            if tok not in day_tokens(date(2000, 1, 3)):
                raise TemplateError(f"unknown token {{{tok}}} in {k}")
    if t["day_param"] and not re.fullmatch(r"[\w.\-\[\]]+", t["day_param"]):
        raise TemplateError("day_param must be a plain query parameter name")
    if t["fetch"] != "once" and not t["day_value"]:
        raise TemplateError("day_value is required when fetching per weekday or per date")
    return t


def day_tokens(d: date):
    return {
        "weekday": WEEKDAYS[d.weekday()], "weekday_lower": WEEKDAYS[d.weekday()].lower(),
        "weekday_short": WEEKDAYS[d.weekday()][:3], "weekday_num": str(d.weekday() + 1),
        "date": d.isoformat(), "yyyymmdd": d.strftime("%Y%m%d"),
    }


def _fill(pattern, d: date):
    toks = day_tokens(d)
    return _TOKEN.sub(lambda m: toks.get(m.group(1), m.group(0)), pattern)


def day_url(url, t, d: date):
    """The URL to request for day d."""
    value = _fill(t["day_value"], d)
    if "{day}" in url:
        return url.replace("{day}", quote(value))
    if not t["day_param"]:
        return url
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != t["day_param"]]
    query.append((t["day_param"], value))
    return urlunsplit(parts._replace(query=urlencode(query)))


def _get(obj, path):
    """Follow a dotted path ("a.b.0.c"); returns None when missing."""
    if not path:
        return obj
    for part in path.split("."):
        if isinstance(obj, dict):
            obj = obj.get(part)
        elif isinstance(obj, list) and part.isdigit() and int(part) < len(obj):
            obj = obj[int(part)]
        else:
            return None
    return obj


def _field(item, spec):
    for path in (spec or "").split("|"):
        if path:
            v = _get(item, path)
            if v not in (None, ""):
                return v
    return None


def _clock(value):
    m = _HMS.match(str(value).strip())
    if not m:
        raise ValueError(value)
    h, mi, sec = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if h > 24 or mi > 59 or sec > 59 or (h == 24 and (mi or sec)):
        raise ValueError(value)
    return timedelta(hours=h, minutes=mi, seconds=sec)


def _time(value, fmt, day: date, tz):
    if value is None:
        return None
    if fmt == "clock":
        return datetime.combine(day, time(0)).replace(tzinfo=tz) + _clock(value)
    if fmt == "unix":
        return datetime.fromtimestamp(float(value), timezone.utc)
    s = str(value).strip().replace("Z", "+00:00")
    t = datetime.fromisoformat(s.replace(" ", "T", 1) if fmt == "datetime" else s)
    return t if t.tzinfo else t.replace(tzinfo=tz)


def parse_items(data, t, day: date, tz):
    """Programmes for one day's slice of a decoded JSON response."""
    items = _get(data, _fill(t["items_path"], day))
    if items is None:
        return []
    if not isinstance(items, list):
        raise TemplateError(f"items_path '{t['items_path']}' does not point to a list")
    name = WEEKDAYS[day.weekday()].lower()
    out = []
    for item in items[:MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        title = _field(item, t["title"])
        if not isinstance(title, (str, int, float)) or not str(title).strip():
            continue
        days = _field(item, t["days"]) if t["days"] else None
        if isinstance(days, str) and days.strip() and name not in [x.strip().lower() for x in days.split(",")]:
            continue
        if isinstance(days, list) and days and name not in [str(x).strip().lower() for x in days]:
            continue
        try:
            start = _time(_field(item, t["start"]), t["time_format"], day, tz)
            end = _time(_field(item, t["end"]), t["time_format"], day, tz) if t["end"] else None
            if end is None and t["duration"]:
                dur = _field(item, t["duration"])
                end = start + timedelta(seconds=float(dur)) if dur not in (None, "") else None
        except (ValueError, TypeError, OverflowError, OSError):
            continue
        if start is None:
            continue
        if end is not None and end <= start and t["time_format"] == "clock":
            end += timedelta(days=1)  # runs past midnight
        desc = _field(item, t["description_field"]) if t["description_field"] else None
        out.append({"start": start, "end": end, "title": str(title).strip()[:128],
                    "description": desc.strip()[:1200] if isinstance(desc, str) else "", "genres": []})
    return out


def run(t, url, days, tz, fetcher, today=None):
    """Fetch and parse `days` days starting today. fetcher(url) -> bytes.
    Returns programmes with ISO start/end, sorted and de-duplicated."""
    if t.get("timezone"):
        tz = ZoneInfo(t["timezone"])
    today = today or datetime.now(tz).date()
    if t.get("format") == "text":
        return _finish(parse_text_listing(fetcher(url), t, tz, today, days))
    if t.get("format") == "html":
        return _finish(expand_weekly(parse_html_timetable(fetcher(url), t), t, tz, today, days))
    cache = {}

    def load(u):
        if u not in cache:
            raw = fetcher(u)
            try:
                cache[u] = json.loads(raw.decode("utf-8-sig"))
            except (UnicodeDecodeError, ValueError):
                raise TemplateError("the response is not valid JSON")
        return cache[u]

    progs = []
    for n in range(days):
        day = today + timedelta(days=n)
        data = load(url if t["fetch"] == "once" else day_url(url, t, day))
        progs += parse_items(data, t, day, tz)
        if t["fetch"] == "once" and t["time_format"] != "clock" and not _TOKEN.search(t["items_path"]):
            break  # one list with absolute times covers every day

    return _finish(progs)


def _finish(progs):
    """Sort, de-duplicate and fill in missing end times; ISO strings out."""
    progs.sort(key=lambda p: p["start"])
    out, seen = [], set()
    for i, p in enumerate(progs):
        key = (p["start"], p["title"])
        if key in seen:
            continue
        seen.add(key)
        end = p["end"]
        if end is None or end <= p["start"]:  # fall back to the next show's start, else one hour
            nxt = next((q["start"] for q in progs[i + 1:] if q["start"] > p["start"]), None)
            end = nxt or p["start"] + timedelta(hours=1)
        out.append(dict(p, start=p["start"].isoformat(), end=end.isoformat()))
    return out


# --- dated text listings ------------------------------------------------------------------

_BLOCK_TAGS = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol"}
_DATE_LINE = re.compile(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(\d{4})(?!\d)")
_PROG_LINE = re.compile(r"^(\d{1,2})[.:](\d{2})\s+(\S.*)$")
_WEEK_LINE = re.compile(r"^(vk|viikko|vecka|week|wk|kw)\.?\s*\d{1,2}$", re.I)


class _TextExtractor(HTMLParser):
    """Visible text of an HTML document, one line per block element."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head", "title"):
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head", "title"):
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def text_lines(raw: bytes):
    text = raw.decode("utf-8-sig", "replace")
    if re.search(r"<(html|body|p|div|span)\b", text[:20000], re.I):
        ex = _TextExtractor()
        ex.feed(text)
        ex.close()
        text = "".join(ex.parts)
    text = text.replace("\u00ad", "").replace("\u200b", "")  # soft hyphens / zero-width spaces
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def parse_text_listing(raw: bytes, t, tz, today: date, days: int):
    markers = [m for m in t.get("title_split", "").split("|") if m.strip()]
    last_day = today + timedelta(days=days)
    out, day, current = [], None, None
    for line in text_lines(raw)[:20000]:
        m = _DATE_LINE.search(line)
        if m and not _PROG_LINE.match(line):
            try:
                day = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                day = None
            current = None
            continue
        m = _PROG_LINE.match(line)
        if m and day is not None:
            h, mi = int(m.group(1)), int(m.group(2))
            if h > 24 or mi > 59 or (h == 24 and mi):
                continue
            title, desc = m.group(3).strip(), ""
            for marker in markers:
                pos = title.find(marker)
                if pos > 0:
                    title, desc = title[:pos].strip(" -–,"), title[pos:].strip()
                    break
            title = title.rstrip(" ,-–")
            current = None
            if today <= day < last_day and title:
                start = datetime.combine(day, time(0)).replace(tzinfo=tz) + timedelta(hours=h, minutes=mi)
                current = {"start": start, "end": None, "title": title[:128], "description": desc, "genres": []}
                out.append(current)
            if len(out) >= MAX_ITEMS * 4:
                break
            continue
        if current is not None and not _WEEK_LINE.match(line):
            current["description"] = (current["description"] + " " + line).strip()[:1200]
    for p in out:
        p["description"] = p["description"][:1200]
    return out


# --- weekly HTML timetables ---------------------------------------------------------------

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class _ClassExtractor(HTMLParser):
    """Collects, for every element with class `item`, the text of the first
    descendant carrying each field's class."""

    def __init__(self, item, fields):
        super().__init__(convert_charrefs=True)
        self.item, self.fields = item, {k: v for k, v in fields.items() if v}
        self.stack, self.items, self.cur, self.open = [], [], None, {}

    def handle_starttag(self, tag, attrs):
        if tag in _VOID:
            if tag == "br":
                self.handle_data(" ")
            return
        classes = set((dict(attrs).get("class") or "").split())
        roles = set()
        if self.item in classes and len(self.items) < MAX_ITEMS:
            self.cur, self.open = {}, {}
            self.items.append(self.cur)
            roles.add("@item")
        if self.cur is not None:
            for field, cls in self.fields.items():
                if cls in classes and field not in self.cur and field not in self.open:
                    self.open[field] = []
                    roles.add(field)
        self.stack.append((tag, roles))
        if len(self.stack) > 500:  # malformed page: stop tracking runaway nesting
            self.stack.pop(0)

    def handle_endtag(self, tag):
        if tag in _VOID or not any(t == tag for t, _ in self.stack):
            return
        while self.stack:
            t, roles = self.stack.pop()
            for field in roles - {"@item"}:
                text = re.sub(r"\s+", " ", "".join(self.open.pop(field, []))).strip()
                if text and self.cur is not None:
                    self.cur.setdefault(field, text)
            if "@item" in roles:
                self.cur, self.open = None, {}
            if t == tag:
                break

    def handle_data(self, data):
        for parts in self.open.values():
            if sum(map(len, parts)) < 4000:
                parts.append(data)


_DAY_WORDS = {
    0: "monday mondays mon ma maanantai maanantaisin måndag måndagar mån montag montags mo",
    1: "tuesday tuesdays tue tues ti tiistai tiistaisin tisdag tisdagar tis dienstag dienstags di",
    2: "wednesday wednesdays wed ke keskiviikko keskiviikkoisin onsdag onsdagar ons mittwoch mittwochs mi",
    3: "thursday thursdays thu thur thurs to torstai torstaisin torsdag torsdagar tor donnerstag donnerstags do",
    4: "friday fridays fri pe perjantai perjantaisin fredag fredagar fre freitag freitags fr",
    5: "saturday saturdays sat la lauantai lauantaisin lördag lördagar lör samstag samstags sa",
    6: "sunday sundays sun su sunnuntai sunnuntaisin söndag söndagar sön sonntag sonntags so",
}
_DAY = {w: d for d, words in _DAY_WORDS.items() for w in words.split()}
_ALL_DAYS = {"daily", "everyday", "päivittäin", "dagligen", "täglich", "joka", "alle"}
_WEEKDAYS = {"weekdays", "weekday", "arkisin", "arkipäivisin", "vardagar", "werktags"}
_WEEKEND = {"weekend", "weekends", "viikonloppu", "viikonloppuisin", "helg", "helger", "wochenende"}


def parse_days(text):
    """'Monday-Thursday' -> {0,1,2,3}; 'ma-pe' -> Mon-Fri; 'arkisin' -> Mon-Fri; '' -> set()."""
    text = (text or "").lower().replace("–", "-").replace("—", "-")
    tokens = re.findall(r"[a-zåäöü]+|-", text)
    days = set()
    for tok in tokens:
        if tok in _ALL_DAYS:
            return set(range(7))
        if tok in _WEEKDAYS:
            days |= set(range(5))
        if tok in _WEEKEND:
            days |= {5, 6}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in _DAY:
            nxt = tokens[i + 1] if i + 1 < len(tokens) else None
            # "Monday-Thursday", "ma-to", "Monday to Friday", "måndag till fredag"
            if nxt in ("-", "to", "till", "bis", "until") and i + 2 < len(tokens) and tokens[i + 2] in _DAY:
                a, b = _DAY[tok], _DAY[tokens[i + 2]]
                d = a
                while True:
                    days.add(d)
                    if d == b:
                        break
                    d = (d + 1) % 7
                i += 3
                continue
            days.add(_DAY[tok])
        i += 1
    return days


_TIME = re.compile(r"(?<!\d)(\d{1,2})[.:](\d{2})(?!\d)")


def parse_html_timetable(raw: bytes, t):
    ex = _ClassExtractor(t["html_item"], {
        "title": t["html_title"], "time": t["html_time"], "days": t["html_days"],
        "description": t["html_description"]})
    ex.feed(raw.decode("utf-8-sig", "replace"))
    ex.close()
    markers = [m for m in t.get("title_split", "").split("|") if m.strip()]
    shows = []
    for it in ex.items:
        title = it.get("title", "").replace("\u00ad", "")
        times = [(int(h), int(m)) for h, m in _TIME.findall(it.get("time", ""))]
        times = [x for x in times if x[0] <= 24 and x[1] <= 59 and not (x[0] == 24 and x[1])]
        if not title or not times:
            continue
        # sites often cut descriptions with a literal "[...]"
        desc = re.sub(r"\s*\[\s*(?:\.\.\.|…)\s*\]\s*$", "", it.get("description", ""))
        for marker in markers:
            pos = title.find(marker)
            if pos > 0:
                title, desc = title[:pos].strip(" -–,"), (title[pos:].strip() + " " + desc).strip()
                break
        if t["html_days"]:
            days = parse_days(it.get("days", ""))
            if not days:
                continue  # a day label we cannot read: better to skip than to guess
        else:
            days = set(range(7))
        shows.append({"title": title[:128], "description": desc[:1200], "days": days,
                      "start": times[0], "end": times[1] if len(times) > 1 else None})
    return shows


def expand_weekly(shows, t, tz, today, days):
    out = []
    for n in range(days):
        day = today + timedelta(days=n)
        midnight = datetime.combine(day, time(0)).replace(tzinfo=tz)
        for s in shows:
            if day.weekday() not in s["days"]:
                continue
            start = midnight + timedelta(hours=s["start"][0], minutes=s["start"][1])
            end = None
            if s["end"]:
                end = midnight + timedelta(hours=s["end"][0], minutes=s["end"][1])
                if end <= start:
                    end += timedelta(days=1)
            out.append({"start": start, "end": end, "title": s["title"], "description": s["description"],
                        "genres": []})
    return out
