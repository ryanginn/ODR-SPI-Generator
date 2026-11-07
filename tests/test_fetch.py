import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from odr_spi import fetch


class _Handler(BaseHTTPRequestHandler):
    seen_cookies = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        cookie = self.headers.get("Cookie") or ""
        _Handler.seen_cookies.append(cookie)
        if self.path.startswith("/challenge"):
            # bot protection: set a cookie and send the client back to the same page
            if "verified=yes" not in cookie:
                self.send_response(302)
                self.send_header("Set-Cookie", "verified=yes; Path=/; HttpOnly")
                self.send_header("Location", self.path)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<p>schedule</p>")
        elif self.path.startswith("/loop"):
            self.send_response(301)
            self.send_header("Location", "/loop")
            self.end_headers()


class FetchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_cookie_challenge_redirect(self):
        _Handler.seen_cookies.clear()
        data, ctype, final = fetch.fetch(self.base + "/challenge", allow_private=True)
        self.assertEqual(data, b"<p>schedule</p>")
        self.assertEqual(_Handler.seen_cookies, ["", "verified=yes"])

    def test_cookies_do_not_persist_between_fetches(self):
        fetch.fetch(self.base + "/challenge", allow_private=True)
        _Handler.seen_cookies.clear()
        fetch.fetch(self.base + "/challenge", allow_private=True)
        self.assertEqual(_Handler.seen_cookies[0], "")

    def test_redirect_loop_reports_the_chain(self):
        with self.assertRaises(fetch.FetchError) as cm:
            fetch.fetch(self.base + "/loop", allow_private=True)
        self.assertIn("/loop", str(cm.exception))
        self.assertIn("bot protection", str(cm.exception))

    def test_private_addresses_still_refused(self):
        with self.assertRaises(fetch.FetchError):
            fetch.fetch(self.base + "/challenge")


if __name__ == "__main__":
    unittest.main()
