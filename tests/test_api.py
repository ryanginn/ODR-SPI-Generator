"""End-to-end API tests using the Flask test client."""
import io
import json
import os
import shutil
import tempfile
import time
import unittest

from PIL import Image

from odr_spi import __main__ as cli, build, config, db, security
from odr_spi.web import create_app

LEGACY_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<serviceInformation xmlns="http://www.worlddab.org/schemas/spi/31" creationTime="2014-06-13T10:32:41+01:00">
  <services id="e32ea1">
    <service>
      <shortName>Demo R1</shortName>
      <mediumName>Demo Radio 1</mediumName>
      <mediaDescription><multimedia url="radio1_32x32.png" mimeValue="image/png" width="32" height="32"/></mediaDescription>
      <mediaDescription><multimedia url="../../etc/passwd" mimeValue="image/png" width="32" height="32"/></mediaDescription>
      <mediaDescription><shortDescription>Number one for hits</shortDescription></mediaDescription>
      <genre href="urn:tva:metadata:cs:ContentCS:2002:10" type="rds_pty">Pop</genre>
      <genre href="urn:tva:metadata:cs:ContentCS:2002:3.6.8" type="other">Dance</genre>
      <bearer id="dab:2e3.2ea1.2491.0" cost="10"/>
    </service>
    <service>
      <shortName>Ri Ra</shortName>
      <mediumName>Raidi\xc3\x83\xc2\xb3 R\xc3\x83\xc2\xad R\xc3\x83\xc2\xa1</mediumName>
      <bearer id="dab:2e3.2ea1.2493.0" cost="10"/>
      <bearer id="dab:2e3.2ea1.2491.1" cost="10"/>
    </service>
  </services>
</serviceInformation>"""


def png(w, h, color=(200, 0, 0, 255)):
    b = io.BytesIO()
    Image.new("RGBA", (w, h), color).save(b, "PNG")
    return b.getvalue()


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.cfg = dict(config.DEFAULTS, data_dir=os.path.join(self.dir, "data"))
        cli.init(self.cfg)
        security.setup_limiter.hits.clear()  # limiters are process-wide; start each test fresh
        security.login_limiter.hits.clear()
        self.token = cli.setup_token(self.cfg)
        self.app = create_app(self.cfg)
        self.c = self.app.test_client()
        self.csrf = None

    def tearDown(self):
        db._local.conn.close()
        db._local.conn = None
        shutil.rmtree(self.dir)

    def call(self, method, url, body=None, client=None, csrf=None, **kw):
        c = client or self.c
        headers = {"X-Requested-With": "odr-spi"}
        tok = csrf if csrf is not None else self.csrf
        if tok:
            headers["X-CSRF-Token"] = tok
        if body is not None:
            kw["json"] = body
        r = getattr(c, method)(url, headers=headers, **kw)
        return r.status_code, r.get_json(silent=True)

    def login_admin(self):
        st, _ = self.call("post", "/api/setup", {"token": self.token, "username": "rian",
                                                  "password": "correct horse battery"})
        self.assertEqual(st, 200)
        self.csrf = self.call("get", "/api/state")[1]["csrf"]

    def test_setup_requires_token_and_runs_once(self):
        st, _ = self.call("post", "/api/setup", {"token": "nope", "username": "x", "password": "y" * 12})
        self.assertEqual(st, 403)
        self.login_admin()
        st, _ = self.call("post", "/api/setup", {"token": self.token, "username": "evil",
                                                  "password": "another long password"})
        self.assertEqual(st, 409)

    def test_csrf_and_header_required(self):
        self.login_admin()
        st, _ = self.call("post", "/api/services", {"short_name": "A", "medium_name": "A"}, csrf="bad")
        self.assertEqual(st, 403)
        r = self.c.post("/api/services", json={"short_name": "A", "medium_name": "A"},
                        headers={"X-CSRF-Token": self.csrf})
        self.assertEqual(r.status_code, 403)
        r = self.c.post("/api/services", json={"short_name": "A", "medium_name": "A"},
                        headers={"X-CSRF-Token": self.csrf, "X-Requested-With": "odr-spi",
                                 "Origin": "http://evil.example"})
        self.assertEqual(r.status_code, 403)

    def test_full_flow(self):
        self.login_admin()
        out = os.path.join(self.dir, "out")
        os.mkdir(out)
        st, body = self.call("put", "/api/settings", {"output_path": os.path.join(out, "spi.dat"), "bitrate": 16,
                                                      "epg_days": 2})
        self.assertEqual(st, 200, body)
        st, body = self.call("put", "/api/ensemble", {"ecc": "e3", "eid": "2ea1", "short_name": "DEMO",
                                                      "medium_name": "Demo DAB"})
        self.assertEqual(st, 200, body)

        # legacy import with a local folder upload
        st, imp = self.call("post", "/api/import/legacy", data={"file": (io.BytesIO(LEGACY_XML), "si.xml")})
        self.assertEqual(st, 200, imp)
        self.assertEqual(len(imp["services"]), 2)
        self.assertTrue(any("Raidió Rí Rá" in f for f in imp["fixes"]), imp["fixes"])
        st, imp = self.call("post", f"/api/import/{imp['id']}/files",
                            data={"files": [(io.BytesIO(png(32, 32)), "logos/radio1_32x32.png"),
                                            (io.BytesIO(b"root:x:0:0"), "logos/passwd")]})
        self.assertEqual(st, 200, imp)
        matched = {l["url"]: l["matched"] for l in imp["local_logos"]}
        self.assertTrue(matched["radio1_32x32.png"])
        self.assertFalse(matched["../../etc/passwd"])
        st, res = self.call("post", f"/api/import/{imp['id']}/commit", {"mode": "merge"})
        self.assertEqual((st, res["created"]), (200, 2), res)

        services = self.call("get", "/api/services")[1]
        r1 = next(s for s in services if s["short_name"] == "Demo R1")
        self.assertEqual(r1["genres"], ["urn:tva:metadata:cs:ContentCS:2002:3.6.8"])
        self.assertEqual(len(r1["logos"]), 1)

        # upload validation
        st, body = self.call("post", f"/api/logos/{r1['id']}/320x240/upload",
                             data={"file": (io.BytesIO(png(100, 100)), "x.png")})
        self.assertEqual(st, 400)
        st, body = self.call("post", f"/api/logos/{r1['id']}/320x240/upload",
                             data={"file": (io.BytesIO(png(100, 100)), "x.png"), "fit": "1"})
        self.assertEqual(st, 200, body)
        st, body = self.call("post", f"/api/logos/{r1['id']}/32x32/upload",
                             data={"file": (io.BytesIO(b"<svg onload=alert(1)>"), "x.png")})
        self.assertEqual(st, 400)

        # SSRF guard
        st, body = self.call("put", f"/api/logos/{r1['id']}/128x128/url", {"url": "http://127.0.0.1:22/x.png"})
        self.assertEqual(st, 200)
        self.assertIn("private", body["error"])

        # EPG
        st, body = self.call("post", f"/api/services/{r1['id']}/programmes",
                             {"kind": "weekly", "days": 127, "start_time": "07:00", "duration": 180,
                              "title": "The Breakfast Show", "description": "Wake up with us"})
        self.assertEqual(st, 200, body)
        st, body = self.call("put", f"/api/services/{r1['id']}/epg", {"epg_enabled": True})
        self.assertEqual(st, 200, body)
        prev = self.call("get", f"/api/services/{r1['id']}/epg/preview")[1]
        self.assertEqual(prev["days"][0]["programmes"][0]["title"], "The Breakfast Show")

        # station owner permissions
        st, u = self.call("post", "/api/users", {"username": "owner1", "role": "station",
                                                 "password": "station owner pw!", "services": [r1["id"]]})
        self.assertEqual(st, 200, u)
        oc = self.app.test_client()
        self.call("post", "/api/login", {"username": "owner1", "password": "station owner pw!"}, client=oc, csrf="")
        ocsrf = self.call("get", "/api/state", client=oc, csrf="")[1]["csrf"]
        st, _ = self.call("post", "/api/account/password", {"current": "station owner pw!",
                                                             "new": "a brand new secret"}, client=oc, csrf=ocsrf)
        self.assertEqual(st, 200)
        listed = self.call("get", "/api/services", client=oc, csrf=ocsrf)[1]
        self.assertEqual([s["id"] for s in listed], [r1["id"]])
        st, _ = self.call("patch", f"/api/services/{r1['id']}", {"short_description": "New text"},
                          client=oc, csrf=ocsrf)
        self.assertEqual(st, 200)
        st, _ = self.call("patch", f"/api/services/{r1['id']}", {"medium_name": "Hijack"}, client=oc, csrf=ocsrf)
        self.assertEqual(st, 403)
        other = next(s for s in services if s["id"] != r1["id"])
        st, _ = self.call("patch", f"/api/services/{other['id']}", {"short_description": "x"}, client=oc, csrf=ocsrf)
        self.assertEqual(st, 403)
        st, _ = self.call("post", "/api/apply", {}, client=oc, csrf=ocsrf)
        self.assertEqual(st, 403)
        st, _ = self.call("get", "/api/fs?path=/", client=oc, csrf=ocsrf)
        self.assertEqual(st, 403)
        st, _ = self.call("get", "/api/settings", client=oc, csrf=ocsrf)
        self.assertEqual(st, 403)

        # apply and check the output decodes
        bid = build.run("test", None, apply_changes=True, refresh=False)
        b = db.q1("SELECT * FROM builds WHERE id = ?", (bid,))
        self.assertIn(b["status"], ("ok", "warning"), b)
        stats = json.loads(b["stats"])
        self.assertEqual(stats["services"], 2)
        self.assertEqual(stats["epg_objects"], 2)
        self.assertEqual(stats["payload_bytes"] + stats["overhead_bytes"], stats["stream_bytes"])
        self.assertLess(stats["overhead_bytes"], stats["payload_bytes"] * 0.25)  # one pass, not a repeated carousel
        data = open(os.path.join(out, "spi.dat"), "rb").read()
        self.assertEqual(len(data), stats["stream_bytes"])
        from tests.test_encoder_roundtrip import decode_packets
        self.assertTrue(decode_packets(data, 48))

        # build details (paths, other stations' warnings) are hidden from station owners
        st_owner = self.call("get", "/api/status", client=oc, csrf=ocsrf)[1]
        self.assertEqual((st_owner["build"]["message"], st_owner["build"]["warnings"]), ("", []))
        self.assertNotIn("output_path", st_owner)
        builds_owner = self.call("get", "/api/builds", client=oc, csrf=ocsrf)[1]
        self.assertEqual(builds_owner[0]["message"], "")

        snippet = self.call("get", "/api/mux-snippet")[1]
        self.assertIn("inputuri", snippet["blocks"]["subchannels"])

    def test_output_path_validation(self):
        self.login_admin()
        st, body = self.call("put", "/api/settings", {"output_path": "/etc/passwd"})
        self.assertEqual(st, 400)
        os.symlink("/etc/passwd", os.path.join(self.dir, "link.dat"))
        st, body = self.call("put", "/api/settings", {"output_path": os.path.join(self.dir, "link.dat")})
        self.assertEqual(st, 400)
        self.assertIn("symlink", body["error"])

    def test_update_requests(self):
        self.login_admin()
        cfg = self.app.config["ODR_CFG"]
        cfg.update(update_conf=os.path.join(self.dir, "update.conf"), installed_commit=os.path.join(self.dir, "COMMIT"),
                   update_status=os.path.join(self.dir, "status.json"))
        st, body = self.call("post", "/api/update", {"action": "apply"})
        self.assertEqual(st, 400)  # not installed from git
        with open(cfg["update_conf"], "w") as f:
            f.write("REPO_URL=https://user:secret@example.com/owner/repo.git\nBRANCH=main\n")
        with open(cfg["installed_commit"], "w") as f:
            f.write("abc1234def\n")
        info = self.call("get", "/api/update")[1]
        self.assertTrue(info["enabled"])
        self.assertEqual(info["source"], "https://example.com/owner/repo.git")
        self.assertEqual(info["current_commit"], "abc1234def")
        st, _ = self.call("post", "/api/update", {"action": "rm -rf /"})
        self.assertEqual(st, 400)
        st, _ = self.call("post", "/api/update", {"action": "check"})
        self.assertEqual(st, 200)
        with open(os.path.join(cfg["data_dir"], "update-request")) as f:
            self.assertEqual(f.read(), "check")
        st, _ = self.call("post", "/api/update", {"action": "apply"})
        self.assertEqual(st, 409)  # previous request not picked up yet
        # editors cannot trigger updates
        self.call("post", "/api/users", {"username": "ed1", "role": "editor", "password": "editor password 1"})
        ec = self.app.test_client()
        self.call("post", "/api/login", {"username": "ed1", "password": "editor password 1"}, client=ec, csrf="")
        ecsrf = self.call("get", "/api/state", client=ec, csrf="")[1]["csrf"]
        self.call("post", "/api/account/password", {"current": "editor password 1", "new": "editor password 2"},
                  client=ec, csrf=ecsrf)
        self.assertEqual(self.call("get", "/api/services", client=ec, csrf=ecsrf)[0], 200)
        st, body = self.call("get", "/api/update", client=ec, csrf=ecsrf)
        self.assertEqual((st, body["error"]), (403, "Administrator access required."))

    def test_bitrates_and_mux_name(self):
        self.assertEqual({k: build.packet_size_for(k) for k in (8, 16, 24, 32, 48, 64, 96)},
                         {8: 24, 16: 48, 24: 72, 32: 96, 48: 72, 64: 96, 96: 96})
        self.login_admin()
        self.assertEqual(self.call("put", "/api/settings", {"bitrate": 64})[0], 200)
        self.assertEqual(self.call("put", "/api/settings", {"bitrate": 100})[0], 400)
        self.assertEqual(self.call("put", "/api/settings", {"bitrate": 60})[0], 400)
        self.call("put", "/api/ensemble", {"ecc": "e1", "eid": "c0de", "short_name": "Demo", "medium_name": "Demo Mux"})
        anon = self.app.test_client()
        self.assertEqual(self.call("get", "/api/state", client=anon, csrf="")[1]["mux_name"], "Demo Mux")
        self.call("put", "/api/settings", {"mux_name": "Region North"})
        self.assertEqual(self.call("get", "/api/state", client=anon, csrf="")[1]["mux_name"], "Region North")

    def test_warning_dismissal(self):
        self.login_admin()
        out = os.path.join(self.dir, "spi.dat")
        self.call("put", "/api/settings", {"output_path": out})
        self.call("put", "/api/ensemble", {"ecc": "e1", "eid": "c0de", "short_name": "Demo", "medium_name": "Demo Mux"})
        self.call("post", "/api/services", {"medium_name": "No SId", "short_name": "NoSId"})
        bid = build.run("test", None, apply_changes=True, refresh=False)
        st = self.call("get", "/api/status")[1]["build"]
        self.assertEqual(st["status"], "warning")
        self.assertEqual(len(st["warnings"]), 1)
        self.assertEqual(self.call("post", f"/api/builds/{bid}/dismiss", {"warning": st["warnings"][0]})[0], 200)
        st = self.call("get", "/api/status")[1]["build"]
        self.assertEqual((st["status"], st["warnings"]), ("ok", []))
        build.run("test", None, refresh=False)  # the same warning stays hidden on later builds
        st = self.call("get", "/api/status")[1]["build"]
        self.assertEqual((st["status"], st["stats"]["dismissed_warnings"]), ("ok", 1))
        self.call("post", "/api/warnings/restore", {})
        build.run("test", None, refresh=False)
        self.assertEqual(self.call("get", "/api/status")[1]["build"]["status"], "warning")

    def test_slow_cycle_dismissal_returns_when_much_slower(self):
        w = build.warning_key("Carousel takes 8 min 19 s to cycle at 32 kbps - consider ...")
        self.assertEqual(w, build.SLOW_CYCLE)
        db.set_setting("dismissed_warnings", {build.SLOW_CYCLE: 499})
        text = ["Carousel takes 9 min 0 s to cycle at 32 kbps"]
        self.assertEqual(build.split_dismissed(text, {"cycle_seconds": 540}), ([], text))
        self.assertEqual(build.split_dismissed(text, {"cycle_seconds": 700}), (text, []))

    def test_feed_templates(self):
        self.login_admin()
        tpls = self.call("get", "/api/feed-templates")[1]
        self.assertEqual({t["name"] for t in tpls}, {"MPBNL", "Coast FM", "Radio Slovenija (RTV SLO)"})
        coast = next(t for t in tpls if t["name"] == "Coast FM")
        new = dict(coast["definition"], name="My API")
        st, body = self.call("post", "/api/feed-templates", {"definition": new})
        self.assertEqual(st, 200, body)
        tid = body["id"]
        self.assertEqual(self.call("post", "/api/feed-templates", {"definition": new})[0], 400)  # duplicate
        bad = dict(new, title="x; import os")
        self.assertEqual(self.call("put", f"/api/feed-templates/{tid}", {"definition": bad})[0], 400)
        # a station using the template; deleting it is refused
        sid = self.call("post", "/api/services", {"medium_name": "Demo", "short_name": "Demo",
                                                  "bearers": [{"sid": "c0de"}]})[1]["id"]
        st, body = self.call("put", f"/api/services/{sid}/epg", {"epg_enabled": True, "epg_feed_type": f"tpl:{tid}",
                                                                 "epg_feed_url": "https://example.com/x.json"})
        self.assertEqual(st, 200, body)
        self.assertEqual(self.call("put", f"/api/services/{sid}/epg", {"epg_feed_type": "tpl:9999"})[0], 400)
        self.assertEqual(self.call("delete", f"/api/feed-templates/{tid}")[0], 400)
        self.assertEqual(next(t for t in self.call("get", "/api/feed-templates")[1] if t["id"] == tid)["used_by"], 1)
        # SSRF guard applies to template tests too
        st, body = self.call("post", "/api/feed-templates/test", {"definition": new, "url": "http://127.0.0.1/x"})
        self.assertEqual(st, 400)
        self.assertIn("private", body["error"])
        # samples can be restored after deletion
        mp = next(t for t in tpls if t["name"] == "MPBNL")
        self.assertEqual(self.call("delete", f"/api/feed-templates/{mp['id']}")[0], 200)
        self.assertEqual(self.call("post", "/api/feed-templates/restore-samples", {})[1]["added"], 1)
        # station owners can list templates (to pick one) but not change them
        self.call("post", "/api/users", {"username": "own1", "role": "station", "password": "owner password 1",
                                         "services": [sid]})
        oc = self.app.test_client()
        self.call("post", "/api/login", {"username": "own1", "password": "owner password 1"}, client=oc, csrf="")
        ocsrf = self.call("get", "/api/state", client=oc, csrf="")[1]["csrf"]
        self.call("post", "/api/account/password", {"current": "owner password 1", "new": "owner password 2"},
                  client=oc, csrf=ocsrf)
        self.assertEqual(self.call("get", "/api/feed-templates", client=oc, csrf=ocsrf)[0], 200)
        self.assertEqual(self.call("post", "/api/feed-templates", {"definition": dict(new, name="Z")},
                                   client=oc, csrf=ocsrf)[0], 403)
        self.assertEqual(self.call("post", "/api/feed-templates/test", {"definition": new, "url": "https://x.y"},
                                   client=oc, csrf=ocsrf)[0], 403)

    def test_legacy_mpbnl_feed_type_is_migrated(self):
        self.login_admin()
        sid = self.call("post", "/api/services", {"medium_name": "Old", "short_name": "Old"})[1]["id"]
        db.x("UPDATE services SET epg_feed_type = 'mpbnl' WHERE id = ?", (sid,))
        db.init(self.cfg["data_dir"])
        mp = db.q1("SELECT id FROM feed_templates WHERE name = 'MPBNL'")
        self.assertEqual(db.q1("SELECT epg_feed_type FROM services WHERE id = ?", (sid,))["epg_feed_type"],
                         f"tpl:{mp['id']}")

    def test_logo_broadcast_variant(self):
        from odr_spi import media
        import random
        random.seed(2)
        img = Image.new("RGB", (320, 240))
        img.putdata([(random.randint(0, 255), x % 256, 128) for x in range(320 * 240)])
        b = io.BytesIO()
        img.save(b, "PNG")
        name = media.store(b.getvalue(), "image/png")
        data, mime = media.broadcast_variant(name, "image/png")
        self.assertLess(len(data), len(b.getvalue()) * 0.9)
        Image.open(io.BytesIO(data)).verify()
        self.assertEqual(media.read(name), b.getvalue())  # original untouched
        tiny = media.store(png(32, 32), "image/png")
        self.assertEqual(media.broadcast_variant(tiny, "image/png")[1], "image/png")

    def test_login_lockout(self):
        self.login_admin()
        c2 = self.app.test_client()
        for _ in range(8):
            self.call("post", "/api/login", {"username": "rian", "password": "wrong password"}, client=c2, csrf="")
        st, body = self.call("post", "/api/login", {"username": "rian", "password": "correct horse battery"},
                             client=c2, csrf="")
        self.assertEqual(st, 429, body)


if __name__ == "__main__":
    unittest.main()
