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


class BearerImportTest(unittest.TestCase):
    def test_fm_bearer_ids(self):
        from odr_spi import importers
        self.assertEqual(importers.parse_fm_bearer("fm:ce1.6209.10620"),
                         {"type": "fm", "ecc": "e1", "pi": "6209", "freq": "106.2"})
        self.assertEqual(importers.parse_fm_bearer("fm:2e3.2491.09850")["freq"], "98.5")
        self.assertIsNone(importers.parse_fm_bearer("fm:ce1.6209.20000"))  # 200 MHz is not FM
        xml = b"""<serviceInformation xmlns="http://www.worlddab.org/schemas/spi/31"><services id="e1c0de"><service>
          <shortName>Nova</shortName><mediumName>Radio Nova</mediumName>
          <bearer id="fm:ce1.6209.10620" cost="40"/><bearer id="dab:ce1.c0de.6209.0" cost="20"/>
          <bearer id="http://stream.example/nova.mp3" cost="100"/></service></services></serviceInformation>"""
        r = importers.parse_legacy_si(xml)
        bearers = r["services"][0]["bearers"]
        self.assertEqual([b.get("type", "dab") for b in bearers], ["dab", "fm"])  # DAB first
        self.assertEqual(bearers[1]["pi"], "6209")
        self.assertTrue(any("not a DAB or FM bearer" in w for w in r["warnings"]))  # the stream URL


class TemplateTest(unittest.TestCase):
    def test_samples_are_valid(self):
        self.assertEqual(set(SAMPLES), {"MPBNL", "Coast FM", "Radio Slovenija (RTV SLO)", "Rayo / Planet Radio (Bauer)",
                                        "Järviradio (published Google Doc)", "Sea FM (WordPress radio theme)"})

    def test_parse_days(self):
        cases = {"Monday-Thursday": {0, 1, 2, 3}, "Friday": {4}, "ma-pe": {0, 1, 2, 3, 4}, "la–su": {5, 6},
                 "Monday to Friday": {0, 1, 2, 3, 4}, "arkisin": {0, 1, 2, 3, 4}, "Weekends": {5, 6},
                 "lauantaisin": {5}, "Fri-Mon": {4, 5, 6, 0}, "Mon, Wed & Fri": {0, 2, 4}, "Päivittäin": set(range(7)),
                 "måndag till fredag": {0, 1, 2, 3, 4}, "Samstag": {5}, "": set(), "soon": set()}
        for text, want in cases.items():
            self.assertEqual(ft.parse_days(text), want, text)

    def test_html_timetable(self):
        def item(title, time, day, desc):
            return f"""<div class="col"><div class="qt-part-archive-item qt-part-show-schedule-day-item ">
              <h4 class="qt-item-title qt-title"><a href="#" class="qt-t">{title}</a></h4>
              <p class="qt-item-det"><span class="qt-time">{time}</span><span class="qt-day qt-capfont">{day}</span>
              <img src="x.jpg"><div class="qt-more"><p class="qt-ellipsis-2">{desc}</p></div>
              <p class="qt-item-det qt-accent"><span class="qt-time">99:99</span><span class="qt-day">Sunday</span></p>
              </div></div>"""
        page = ("<html><body><p>unclosed paragraph<div>" + item("Night", "00:00", "Monday-Thursday", "Overnight")
                + item("Aamu", "06:00", "Monday-Thursday", "Mornings.[...]") + item("Late", "21:00", "Friday", "x")
                + item("Friday Night", "22:00", "Friday", "")
                + item("Party", "18:00 - 21:00", "Friday", "Live &amp; loud") + item("Bad", "", "Friday", "no time")
                + item("Mystery", "10:00", "Someday", "unknown days") + "</div></body></html>").encode()
        t = SAMPLES["Sea FM (WordPress radio theme)"]
        shows = ft.parse_html_timetable(page, t)
        self.assertEqual([s["title"] for s in shows], ["Night", "Aamu", "Late", "Friday Night", "Party"])
        self.assertEqual(shows[0]["days"], {0, 1, 2, 3})  # the first time/day element wins
        self.assertEqual(shows[1]["description"], "Mornings.")  # "[...]" removed
        progs = ft.run(t, "https://example.com/ohjelma/", 7, timezone.utc, lambda u: page, today=date(2026, 11, 9))
        friday = [p for p in progs if p["start"].startswith("2026-11-13")]
        self.assertEqual([(p["start"][11:16], p["end"][11:16], p["title"]) for p in friday],
                         [("18:00", "21:00", "Party"), ("21:00", "22:00", "Late"), ("22:00", "23:00", "Friday Night")])  # nothing later in the window: one hour
        self.assertEqual(friday[0]["description"], "Live & loud")
        self.assertTrue(progs[0]["start"].endswith("+02:00"))  # Europe/Helsinki
        self.assertEqual(sum(p["title"] == "Night" for p in progs), 4)  # Mon-Thu in the week

    def test_html_template_validation(self):
        base = {"name": "x", "format": "html", "fetch": "once", "html_item": "a", "html_title": "b", "html_time": "c"}
        ft.validate(base)
        for bad in ({"html_item": ""}, {"html_title": "two classes"}, {"html_time": "x\" onload=\""},
                    {"fetch": "per_date", "day_value": "{date}"}):
            with self.assertRaises(ft.TemplateError, msg=bad):
                ft.validate(dict(base, **bad))

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
