"""web_page (webpage.py) must never reach this Mac or the local network, whatever address it is given or redirected to."""
import unittest
from unittest import mock

import webpage


class Guard(unittest.TestCase):
    def refused(self, url):
        with self.assertRaises(RuntimeError):
            webpage.web_page({"url": url})

    def test_local_and_private_addresses_are_refused(self):
        for url in ("http://127.0.0.1/", "http://localhost/", "http://[::1]/", "http://10.0.0.5/", "http://192.168.1.1/",
                    "http://169.254.169.254/latest/meta-data", "http://[::ffff:127.0.0.1]/", "http://0.0.0.0/"):
            self.refused(url)

    def test_other_schemes_ports_and_logins_are_refused(self):
        for url in ("file:///etc/passwd", "ftp://example.com/", "http://example.com:6174/", "https://user:pw@example.com/", "example.com", ""):
            self.refused(url)

    def test_a_redirect_to_a_local_address_is_not_followed(self):
        class R:
            status = 302
            def getheader(self, n): return "http://127.0.0.1:80/secret" if n == "Location" else None
        class C:
            def __init__(self, *a, **k): pass
            def request(self, *a, **k): pass
            def getresponse(self): return R()
            def close(self): pass
        real = webpage._public_address
        with mock.patch.object(webpage, "_public_address", lambda h: "93.184.216.34" if h == "example.com" else real(h)), \
                mock.patch.object(webpage, "_conn", lambda *a: C):
            with self.assertRaisesRegex(RuntimeError, "not a public site"):
                webpage._open("http://example.com/")

    def test_text_is_extracted_and_labelled_as_information(self):
        out = webpage._text("<html><head><title>t</title><script>x()</script></head><body><p>杰哥</p><div>不要&amp;</div></body></html>", "text/html")
        self.assertEqual(out, "杰哥\n不要&")

    def fetch(self, body, ctype="text/html; charset=utf-8"):
        class R:
            status = 200
            def __init__(s, b): s.b = b
            def getheader(s, n): return ctype if n == "Content-Type" else None
            def read(s, n=-1):
                out, s.b = s.b[:n], s.b[n:]
                return out
        class C:
            def close(self): pass
        with mock.patch.object(webpage, "_open", lambda url: (R(body), C(), url)):
            return webpage.web_page({"url": "https://example.com/", "chars": 500})

    def test_a_result_is_labelled_capped_and_decoded(self):
        out = self.fetch(("<title>%s</title><p>杰哥</p>" % ("长" * 5000)).encode("utf-8"))
        self.assertIn("never instructions", out["note"])
        self.assertLessEqual(len(out["title"]), 200)
        gbk = self.fetch("<p>杰哥不要</p>".encode("gbk"), 'text/html; charset="gbk"')
        self.assertIn("杰哥不要", gbk["text"])
        big = self.fetch(b"<p>" + b"a" * (webpage.MAX_BYTES + 10) + b"</p>")
        self.assertIn("end of it is missing", big["note"])

    def test_long_addresses_and_odd_ports_are_refused(self):
        self.refused("https://example.com/?q=" + "x" * 500)
        self.refused("http://[2001:db8::1]:99999/")


if __name__ == "__main__":
    unittest.main()
