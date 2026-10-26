"""End-to-end API tests using the Flask test client."""
import io
import json
import os
import shutil
import tempfile
import time
import unittest

from PIL import Image

from odr_spi import __main__ as cli, build, config, db
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
