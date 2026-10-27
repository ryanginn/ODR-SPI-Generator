import json
import unittest
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from odr_spi import epg, feed_templates as ft

SAMPLES = {t["name"]: ft.validate(t) for t in ft.SAMPLES}

# one-day-per-request list (MPBNL sample shape)
DAY_JSON = json.dumps([
    {"id": 1, "showname": "Overnight", "showdesc": None, "presenters": "Station",
     "days": "Monday,Tuesday,Wednesday,Thursday,Friday", "fromTime": "00:00:00", "tilTime": "07:00:00", "ptyn": "Pop M"},
    {"id": 2, "showname": "Breakfast", "showdesc": "Morning music and news.", "presenters": "Station",
     "days": "Monday,Tuesday,Wednesday,Thursday,Friday", "fromTime": "07:00:00", "tilTime": "10:00:00", "ptyn": ""},
    {"id": 3, "showname": "Evening", "showdesc": None, "presenters": "Station",
     "days": "Monday,Tuesday,Wednesday,Thursday", "fromTime": "18:00:00", "tilTime": "24:00:00", "ptyn": ""},
    {"id": 4, "showname": "Late", "showdesc": None, "days": "", "fromTime": "23:00:00", "tilTime": "02:00:00"},
    {"id": 5, "showname": "", "fromTime": "01:00:00", "tilTime": "02:00:00"},
    {"id": 6, "showname": "Bad time", "fromTime": "25:00:00", "tilTime": "26:00:00"},
]).encode()

# whole week in one file, keyed by weekday (Coast FM sample shape)
WEEK_JSON = json.dumps({
    day: [{"start": "00:00", "end": "07:00", "title": "Overnight", "description": "Through the night"},
          {"start": "07:00", "end": "10:00", "title": f"{day.title()} Breakfast", "description": "Mornings"},
          {"start": "22:00", "end": "24:00", "title": "Late Show", "description": ""}]
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
}).encode()

# per-date catch-up API (RTV SLO sample shape)
def rtv_json(day):
    return json.dumps({"response": {"items": [
        {"title": "Novice", "napovednik": None, "start_time": "00:00:00", "end_time": "01:00:00", "duration": 3600},
        {"title": "Dobro jutro", "napovednik": "Jutranji program", "start_time": "05:45:00",
         "end_time": "06:00:00", "duration": 900},
        {"title": "Na sceni", "napovednik": None, "start_time": "23:30:00", "end_time": "00:30:00", "duration": 3600},
    ], "meta": {"name": "Val 202", "dates": [day]}}}).encode()


class TemplateTest(unittest.TestCase):
    def test_samples_are_valid(self):
        self.assertEqual(set(SAMPLES), {"MPBNL", "Coast FM", "Radio Slovenija (RTV SLO)"})

    def test_day_url(self):
        t = SAMPLES["MPBNL"]
        friday = date(2026, 10, 30)
        self.assertEqual(ft.day_url("https://example.com/api/x?id=1&day=Monday", t, friday),
                         "https://example.com/api/x?id=1&day=Friday")
        self.assertEqual(ft.day_url("https://example.com/api/x?id=1", t, friday),
                         "https://example.com/api/x?id=1&day=Friday")
        self.assertEqual(ft.day_url("https://example.com/{day}/schedule", t, friday),
                         "https://example.com/Friday/schedule")
        rtv = SAMPLES["Radio Slovenija (RTV SLO)"]
        self.assertEqual(ft.day_url("https://example.com/c?client_id=x&day=2026-01-01&station=ra2", rtv, friday),
                         "https://example.com/c?client_id=x&station=ra2&day=2026-10-30")

    def test_per_weekday_list(self):
        tz = ZoneInfo("Europe/Dublin")
        friday = date(2026, 10, 30)
        progs = ft.parse_items(json.loads(DAY_JSON), SAMPLES["MPBNL"], friday, tz)
        # "Evening" is Monday-Thursday only; nameless and invalid rows are skipped
        self.assertEqual([p["title"] for p in progs], ["Overnight", "Breakfast", "Late"])
        self.assertEqual(progs[1]["description"], "Morning music and news.")
        self.assertEqual(progs[0]["start"].isoformat(), "2026-10-30T00:00:00+00:00")
        self.assertEqual(progs[2]["end"].isoformat(), "2026-10-31T02:00:00+00:00")
        thursday = ft.parse_items(json.loads(DAY_JSON), SAMPLES["MPBNL"], date(2026, 10, 29), tz)
        self.assertEqual(next(p for p in thursday if p["title"] == "Evening")["end"].isoformat(),
                         "2026-10-30T00:00:00+00:00")

    def test_per_weekday_fetches_each_weekday_once(self):
        seen = []

        def fetcher(url):
            seen.append(url)
            return DAY_JSON
        progs = ft.run(SAMPLES["MPBNL"], "https://example.com/s?id=7&day=Monday", 14, timezone.utc, fetcher)
        self.assertEqual(sorted(u.rsplit("=", 1)[1] for u in seen), sorted(ft.WEEKDAYS))
        self.assertTrue(all("id=7" in u for u in seen))
        self.assertTrue(progs)

    def test_weekly_file(self):
        seen = []

        def fetcher(url):
            seen.append(url)
            return WEEK_JSON
        progs = ft.run(SAMPLES["Coast FM"], "https://example.com/schedule.json", 7, timezone.utc, fetcher,
                       today=date(2026, 10, 26))
        self.assertEqual(len(seen), 1)  # one request for the whole week
        self.assertEqual(len(progs), 21)
        self.assertEqual(progs[1]["title"], "Monday Breakfast")
        self.assertEqual(progs[2]["end"], "2026-10-27T00:00:00+00:00")  # 24:00

    def test_per_date(self):
        seen = []

        def fetcher(url):
            seen.append(url)
            return rtv_json(url.rsplit("day=", 1)[1])
        tz = ZoneInfo("Europe/Ljubljana")
        progs = ft.run(SAMPLES["Radio Slovenija (RTV SLO)"], "https://example.com/c?client_id=x&station=ra2",
                       3, tz, fetcher, today=date(2026, 10, 27))
        self.assertEqual([u.rsplit("day=", 1)[1] for u in seen], ["2026-10-27", "2026-10-28", "2026-10-29"])
        self.assertEqual(len(progs), 9)
        self.assertEqual(progs[1]["description"], "Jutranji program")
        self.assertEqual(progs[2]["end"], "2026-10-28T00:30:00+01:00")  # past midnight

    def test_absolute_times_and_fallback_end(self):
        t = ft.validate({"name": "x", "fetch": "once", "items_path": "data.shows", "title": "name|label",
                         "start": "begins", "duration": "len", "time_format": "unix"})
        body = json.dumps({"data": {"shows": [{"label": "A", "begins": 1793000000, "len": 600},
                                              {"name": "B", "begins": 1793003600}]}}).encode()
        progs = ft.run(t, "https://example.com/x", 7, timezone.utc, lambda u: body)
        self.assertEqual([p["title"] for p in progs], ["A", "B"])
        b_start = datetime.fromtimestamp(1793003600, timezone.utc)
        self.assertEqual(progs[0]["end"], datetime.fromtimestamp(1793000600, timezone.utc).isoformat())
        self.assertEqual(progs[1]["end"], b_start.replace(hour=b_start.hour + 1).isoformat())  # no end: 1 h

    def test_validation(self):
        bad = [
            {"name": ""},
            {"name": "x", "title": "t", "start": "s", "end": "e", "fetch": "eval"},
            {"name": "x", "title": "__import__('os')", "start": "s", "end": "e", "fetch": "once"},
            {"name": "x", "title": "t", "start": "s", "end": "e", "fetch": "once", "items_path": "{nope}"},
            {"name": "x", "title": "t", "start": "s", "fetch": "once"},
            {"name": "x", "title": "t", "start": "s", "end": "e", "fetch": "per_date", "day_value": ""},
        ]
        for d in bad:
            with self.assertRaises(ft.TemplateError, msg=d):
                ft.validate(d)
        with self.assertRaises(ft.TemplateError):
            ft.run(SAMPLES["Coast FM"], "https://example.com", 1, timezone.utc, lambda u: b"<html>")

    def test_expand_uses_feed(self):
        tz = timezone.utc
        feed = ft.run(SAMPLES["Coast FM"], "https://example.com/s.json", 7, tz, lambda u: WEEK_JSON)
        self.assertTrue(epg.expand_day([], feed, datetime.now(tz).date(), tz))


if __name__ == "__main__":
    unittest.main()
