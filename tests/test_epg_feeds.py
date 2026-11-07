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
        self.assertEqual(set(SAMPLES), {"MPBNL", "Coast FM", "Radio Slovenija (RTV SLO)", "Rayo / Planet Radio (Bauer)",
                                        "Järviradio (published Google Doc)"})

    def test_text_listing(self):
        doc = """<html><head><title>x</title><style>p{color:red}</style></head><body>
        <p><span>Viikon 45 lintu: Pensaskerttu</span></p>
        <p><span>LAUANTAI 07.11.2026</span></p>
        <p><span>9.00 Nimip&auml;iv&auml;t</span></p>
        <p><span>10.05 Lauantain toiveet puh. 0700-\u00ad88200 (10,16 &euro;/puh+mpm)</span></p>
        <p><span>15.15 Kullan maailmanmarkkinahinnat t&auml;n&auml;&auml;n.</span></p>
        <p><span>Kullan markkinahinnan tarjoaa Suomen Arvokierto.</span></p>
        <p><span>23.00 J&auml;rviradio soi</span></p>
        <p><span>SUNNUNTAI 08.11.2026 IS&Auml;NP&Auml;IV&Auml;</span></p>
        <p><span>10.00 Jumalanpalvelus toim. Alavuden Helluntaiseurakunta</span></p>
        <p><span>VK 46</span></p>
        <p><span>MAANANTAI 09.11.2026</span></p>
        <p><span>17.00 Klassisen musiikin salaisuudet,</span></p><p><span>seurassanne Henrik Lamberg</span></p>
        <p><span>25.00 Not a time</span></p>
        <p><span>MAANANTAI 16.11.2026</span></p><p><span>8.00 Outside the window</span></p>
        </body></html>""".encode()
        t = SAMPLES["Järviradio (published Google Doc)"]
        progs = ft.run(t, "https://example.com/doc", 7, timezone.utc, lambda u: doc, today=date(2026, 11, 7))
        self.assertEqual([p["title"] for p in progs], ["Nimipäivät", "Lauantain toiveet", "Kullan maailmanmarkkinahinnat tänään.",
                                                      "Järviradio soi", "Jumalanpalvelus", "Klassisen musiikin salaisuudet"])
        self.assertEqual(progs[0]["start"], "2026-11-07T09:00:00+02:00")  # template timezone, not the server's
        self.assertEqual(progs[1]["description"], "puh. 0700-88200 (10,16 €/puh+mpm)")  # soft hyphen removed
        self.assertEqual(progs[2]["description"], "Kullan markkinahinnan tarjoaa Suomen Arvokierto.")
        self.assertEqual(progs[3]["end"], "2026-11-08T10:00:00+02:00")  # runs to the next programme
        self.assertEqual(progs[4]["description"], "toim. Alavuden Helluntaiseurakunta")  # "VK 46" ignored
        self.assertEqual(progs[5]["description"], "seurassanne Henrik Lamberg")

    def test_text_listing_plain_text_and_colon_times(self):
        body = "Monday 9.11.2026\n06:00 Breakfast\n07:30 News\n".encode()
        t = ft.validate({"name": "plain", "format": "text", "fetch": "once"})
        progs = ft.run(t, "https://example.com/x.txt", 7, timezone.utc, lambda u: body, today=date(2026, 11, 9))
        self.assertEqual([(p["start"], p["title"]) for p in progs],
                         [("2026-11-09T06:00:00+00:00", "Breakfast"), ("2026-11-09T07:30:00+00:00", "News")])
        with self.assertRaises(ft.TemplateError):
            ft.validate({"name": "x", "format": "text", "fetch": "per_date", "day_value": "{date}"})
        with self.assertRaises(ft.TemplateError):
            ft.validate({"name": "x", "format": "text", "fetch": "once", "timezone": "Mars/Olympus"})

    def test_rayo_week(self):
        # shape of listenapi.planetradio.co.uk/api9.2/schedule/<code>/today/+7 days: {date: [shows]}
        body = json.dumps({
            "2026-11-07": [
                {"episodeid": 1, "showid": 15396, "start": "2026-11-07T00:00:00+02:00", "title": "Paras Sekoitus",
                 "shortdesc": "Radio Nova - paras sekoitus.", "duration": 28800, "record": 0},
                {"episodeid": 2, "showid": 15395, "start": "2026-11-07T16:00:00+02:00",
                 "title": "Waldon Lauantailöylyt", "shortdesc": "Ladies and gentlemen!", "duration": 10800}],
            "2026-11-08": [
                {"episodeid": 3, "showid": 15396, "start": "2026-11-08T00:00:00+02:00", "title": "Paras Sekoitus",
                 "shortdesc": None, "duration": 36000}],
        }).encode()
        seen = []
        progs = ft.run(SAMPLES["Rayo / Planet Radio (Bauer)"], SAMPLES["Rayo / Planet Radio (Bauer)"]["example_url"],
                       7, ZoneInfo("Europe/Helsinki"), lambda u: seen.append(u) or body, today=date(2026, 11, 7))
        self.assertEqual(len(seen), 1)
        self.assertEqual([p["title"] for p in progs], ["Paras Sekoitus", "Waldon Lauantailöylyt", "Paras Sekoitus"])
        self.assertEqual(progs[1]["end"], "2026-11-07T19:00:00+02:00")  # start + duration
        self.assertEqual(progs[2]["description"], "")

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
