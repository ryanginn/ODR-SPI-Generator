import json
import unittest
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from odr_spi import epg

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


class DayParamFeedTest(unittest.TestCase):
    def test_day_url(self):
        self.assertEqual(epg.day_url("https://example.com/api/x?id=1&day=Monday", "Friday"),
                         "https://example.com/api/x?id=1&day=Friday")
        self.assertEqual(epg.day_url("https://example.com/api/x?id=1", "Sunday"),
                         "https://example.com/api/x?id=1&day=Sunday")
        self.assertEqual(epg.day_url("https://example.com/{day}/schedule", "Tuesday"),
                         "https://example.com/Tuesday/schedule")

    def test_parse_day(self):
        tz = ZoneInfo("Europe/Dublin")
        friday = date(2026, 10, 30)
        progs = epg.parse_mpbnl_day(DAY_JSON, friday, tz)
        titles = [p["title"] for p in progs]
        # "Evening" is Monday-Thursday only; nameless and invalid rows are skipped
        self.assertEqual(titles, ["Overnight", "Breakfast", "Late"])
        self.assertEqual(progs[1]["description"], "Morning music and news.")
        self.assertEqual(progs[0]["start"], "2026-10-30T00:00:00+00:00")
        self.assertEqual(progs[2]["end"], "2026-10-31T02:00:00+00:00")
        thursday = epg.parse_mpbnl_day(DAY_JSON, date(2026, 10, 29), tz)
        evening = next(p for p in thursday if p["title"] == "Evening")
        self.assertEqual(evening["end"], "2026-10-30T00:00:00+00:00")

    def test_fetch_requests_each_weekday_once(self):
        seen = []

        def fetcher(url):
            seen.append(url)
            return DAY_JSON
        progs = epg.fetch_mpbnl("https://example.com/s?id=7&day=Monday", 7, timezone.utc, fetcher)
        self.assertEqual(sorted(u.rsplit("=", 1)[1] for u in seen), sorted(epg.WEEKDAYS))
        self.assertTrue(all("id=7" in u for u in seen))
        self.assertTrue(progs)
        epg.fetch_mpbnl("https://example.com/s?day=Monday", 14, timezone.utc, fetcher)
        self.assertEqual(len(seen), 14)  # 14 days still needs only 7 requests

    def test_expand_uses_feed(self):
        tz = timezone.utc
        day = datetime.now(tz).date()
        feed = epg.fetch_mpbnl("https://example.com/s?day=Monday", 7, tz, lambda u: DAY_JSON)
        self.assertTrue(epg.expand_day([], feed, day, tz))

    def test_rejects_non_list(self):
        with self.assertRaises(ValueError):
            epg.parse_mpbnl_day(b'{"error": "nope"}', date(2026, 10, 26), timezone.utc)


if __name__ == "__main__":
    unittest.main()
