#!/usr/bin/env python3
"""Tests for the RedNote tools: which addresses may be opened, how fast, and what is said when the agent's
browser is not signed in. No browser and no network: reading a page is stood in for.
Run: python3 -m unittest test_rednote"""
import os
import plistlib
import tempfile
import unittest
from unittest import mock

import rednote

NOTE = "6ad8a58e000000002c013e93"


class Address(unittest.TestCase):
    def test_only_a_rednote_note_page_may_be_opened(self):
        for url in ("https://www.xiaohongshu.com/explore/%s?xsec_token=ABRj2BJ-1cE=&xsec_source=pc_feed" % NOTE,
                    "https://www.xiaohongshu.com/search_result/%s?xsec_token=AB_PgORo=&xsec_source=" % NOTE,
                    "https://www.rednote.com/discovery/item/%s" % NOTE):
            self.assertTrue(rednote.note_address(url).startswith("https://www.xiaohongshu.com/explore/%s" % NOTE), url)
        self.assertEqual(rednote.note_address("https://www.xiaohongshu.com/explore/%s?xsec_token=AB=&next=https://evil.example&x=1" % NOTE),
                         "https://www.xiaohongshu.com/explore/%s?xsec_token=AB%%3D" % NOTE)        # nothing but the token rides along
        for url in ("https://evil.example/explore/" + NOTE, "http://www.xiaohongshu.com/explore/" + NOTE, "https://www.xiaohongshu.com/user/profile/" + NOTE,
                    "https://www.xiaohongshu.com/explore/" + NOTE + "/../../settings", "https://xiaohongshu.com.evil.example/explore/" + NOTE,
                    "file:///etc/passwd", "javascript:alert(1)", "chrome://settings", "", "https://www.xiaohongshu.com/explore/short"):
            with self.assertRaises(RuntimeError, msg=url):
                rednote.note_address(url)

    def test_a_search_is_a_few_words_and_goes_only_to_rednotes_search_page(self):
        opened = []

        def read(url, script, ready):
            opened.append(url)
            return {"signed_in": True, "rows": [
                {"title": "咖啡", "by": "a", "when": "1天前", "likes": "9", "url": "https://www.xiaohongshu.com/search_result/%s?xsec_token=AB=" % NOTE},
                {"title": "advert", "by": "b", "when": "", "likes": "", "url": "https://ad.example/x"}]}
        with mock.patch.object(rednote, "_read", read):
            out = rednote.rednote_search({"query": "  新加坡   咖啡店 ", "limit": 5})
            for bad in ("", "   ", "x" * (rednote.QUERY_MAX + 1)):
                with self.assertRaises(RuntimeError):
                    rednote.rednote_search({"query": bad})
        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].startswith("https://www.xiaohongshu.com/search_result?keyword=%E6%96%B0%E5%8A%A0%E5%9D%A1+%E5%92%96"))
        self.assertEqual([r["title"] for r in out["results"]], ["咖啡"])                           # what is not a note is left out
        self.assertTrue(out["results"][0]["url"].startswith("https://www.xiaohongshu.com/explore/" + NOTE))


class Reading(unittest.TestCase):
    def test_not_signed_in_and_a_missing_note_are_said_in_words(self):
        with mock.patch.object(rednote, "_read", lambda *a, **k: {"signed_in": False, "rows": []}):
            with self.assertRaisesRegex(RuntimeError, "not signed in.*rednote.py login"):
                rednote.rednote_search({"query": "咖啡"})
        url = "https://www.xiaohongshu.com/explore/" + NOTE
        with mock.patch.object(rednote, "_read", lambda *a, **k: {"signed_in": False, "missing": True}):
            with self.assertRaisesRegex(RuntimeError, "not signed in"):
                rednote.rednote_note({"url": url})
        with mock.patch.object(rednote, "_read", lambda *a, **k: {"signed_in": True, "missing": True, "says": "当前笔记暂时无法浏览"}):
            with self.assertRaisesRegex(RuntimeError, "did not show that note.*无法浏览"):
                rednote.rednote_note({"url": url})
        with mock.patch.object(rednote, "_read", lambda *a, **k: {"signed_in": True, "blocked": True, "rows": []}):
            with self.assertRaisesRegex(RuntimeError, "human check"):
                rednote.rednote_search({"query": "咖啡"})

    def test_a_note_comes_back_as_its_text_and_comments(self):
        page = {"signed_in": True, "title": "T", "text": "body #tag", "by": "a", "when": "09-21", "likes": "13", "saves": "", "comment_count": "共 4 条评论",
                "pictures": 3, "video": True, "comments": [{"by": "b (作者)", "says": "nice", "when": "10-11", "likes": "赞"}, {"by": "c", "says": ""}], "address": "https://x"}
        with mock.patch.object(rednote, "_read", lambda *a, **k: dict(page)):
            out = rednote.rednote_note({"url": "https://www.xiaohongshu.com/explore/" + NOTE})
        self.assertEqual((out["title"], out["text"], out["pictures"], len(out["comments"])), ("T", "body #tag", 3, 1))
        self.assertNotIn("saves", out)
        self.assertIn("video", out["note"])

    def ask(self, question, box_holds=None, page_text=None, signed_in=True, covered=False, leaves_after_enter=False):
        """rednote_ask against a page whose box ends up holding `box_holds` and whose text ends as `page_text`."""
        sent = self.sent = []

        class Page:
            def __init__(self, url):
                sent.append(("open", url))
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                sent.append(("closed",))
            def wait(self, test, seconds=0):
                return True
            def call(self, method, **params):
                sent.append((method, params.get("text") or params.get("key") or params.get("type")))
            def value(self, js):
                if js == rednote.SIGNED_IN:
                    return signed_in
                if "elementFromPoint" in js:
                    return '{"x": 10, "y": 10, "box": %s}' % ("false" if covered else "true")
                if js == "location.hostname":
                    return "www.xiaohongshu.com"
                if js == "location.pathname":
                    return "/explore/1" if leaves_after_enter and ("Input.dispatchKeyEvent", "Enter") in sent else "/ai_chat"
                if "a.tagName === 'TEXTAREA'" in js:
                    return True
                if js.endswith(".value"):
                    return question if box_holds is None else box_holds
                if js == "document.body.innerText.length":
                    return len(page_text or "") if ("Input.dispatchKeyEvent", "Enter") in sent else 5
                return page_text
        with mock.patch.object(rednote, "_Page", Page), mock.patch.object(rednote.time, "sleep"):
            return rednote.rednote_ask({"question": question}), sent

    def test_a_question_is_sent_only_when_the_box_holds_exactly_it(self):
        text = "首页 点点\n牛车水有什么好吃的\nai总结64篇笔记生成\n有几家老字号。\n\n内容由AI生成，请注意核实\n活动"
        out, sent = self.ask("牛车水有什么好吃的", page_text=text)
        self.assertEqual((out["answer"], out["based_on"]), ("有几家老字号。", "ai总结64篇笔记生成"))
        self.assertIn(("Input.insertText", "牛车水有什么好吃的"), sent)
        self.assertEqual(sent[-1], ("closed",))
        # the box redrew and holds nothing (pressing Enter then would ask whatever suggestion it shows): nothing is sent
        with self.assertRaisesRegex(RuntimeError, "nothing was sent"):
            self.ask("牛车水有什么好吃的", box_holds="", page_text=text)
        self.assertNotIn(("Input.dispatchKeyEvent", "Enter"), self.sent)             # and Enter was never pressed
        self.assertEqual(self.sent[-1], ("closed",))
        # something lies over the box: no click, so nothing under it can be pressed
        with self.assertRaisesRegex(RuntimeError, "covered"):
            self.ask("牛车水有什么好吃的", covered=True, page_text=text)
        self.assertFalse([x for x in self.sent if x[0].startswith("Input.")])
        # the page went elsewhere after the question was sent: that page's text is not handed back as the answer
        with self.assertRaisesRegex(RuntimeError, "left RedNote's assistant"):
            self.ask("牛车水有什么好吃的", leaves_after_enter=True, page_text=text)
        with self.assertRaisesRegex(RuntimeError, "not signed in"):
            self.ask("牛车水有什么好吃的", signed_in=False)
        for bad in ("", "x" * (rednote.QUESTION_MAX + 1)):
            with self.assertRaisesRegex(RuntimeError, "one question"):
                rednote.rednote_ask({"question": bad})
        with self.assertRaisesRegex(RuntimeError, "no answer"):
            self.ask("牛车水有什么好吃的", page_text="首页 点点\n牛车水有什么好吃的\n")

    def test_in_the_entry_agent_nothing_goes_to_rednote_unless_the_owners_own_words_brought_it_up(self):
        went = []
        read = lambda *a, **k: went.append(a[0]) or {"signed_in": True, "rows": []}
        with mock.patch.object(rednote, "_read", read), mock.patch.object(rednote, "_Page", side_effect=AssertionError("no page may open")):
            with mock.patch.dict(os.environ, {"ANOTHERME_ENTRY": "1", "ANOTHERME_OWNER_SAID": "summarise what Zhou wrote on WeChat today"}):
                for call in (lambda: rednote.rednote_search({"query": "周 的 电话"}), lambda: rednote.rednote_ask({"question": "周是谁"}),
                             lambda: rednote.rednote_note({"url": "https://www.xiaohongshu.com/explore/%s?xsec_token=zhou" % NOTE})):
                    with self.assertRaisesRegex(RuntimeError, "have not mentioned RedNote"):
                        call()
                self.assertEqual(went, [])
            with mock.patch.dict(os.environ, {"ANOTHERME_ENTRY": "1", "ANOTHERME_OWNER_SAID": "小红书上怎么说牛车水的咖啡"}):
                rednote.rednote_search({"query": "牛车水 咖啡"})
            self.assertEqual(len(went), 1)
            with mock.patch.dict(os.environ, {}, clear=False):                        # the owner's own Claude Code session: their call to make
                os.environ.pop("ANOTHERME_ENTRY", None)
                rednote.rednote_search({"query": "牛车水 咖啡"})
            self.assertEqual(len(went), 2)

    def test_a_page_that_left_rednote_is_not_read_and_only_the_token_rides_on_a_note_address(self):
        class Elsewhere:
            def value(self, js):
                return "evil.example"
        with self.assertRaisesRegex(RuntimeError, "not RedNote"):
            rednote._on_rednote(Elsewhere())
        url = rednote.note_address("https://www.xiaohongshu.com/explore/%s?xsec_token=AB=&xsec_source=private-words-here" % NOTE)
        self.assertNotIn("private", url)
        self.assertIn("xsec_source=pc_feed", rednote.note_address("https://www.xiaohongshu.com/explore/%s?xsec_token=AB=&xsec_source=pc_feed" % NOTE))

    def test_pages_are_opened_at_a_persons_pace(self):
        with mock.patch.object(rednote, "OPENS", os.path.join(tempfile.mkdtemp(), "opens.json")), mock.patch.object(rednote, "OPENS_PER_TEN_MINUTES", 3):
            for _ in range(3):
                rednote._paced()
            with self.assertRaisesRegex(RuntimeError, "limit"):
                rednote._paced()
            with mock.patch.object(rednote.time, "time", lambda: 10 ** 10):        # ten minutes on, the count starts again
                rednote._paced()

    def test_the_browser_spoken_to_is_this_macs_own_and_the_tools_say_whose_words_they_return(self):
        for url in ("ws://evil.example:9455/devtools/x", "ws://127.0.0.1:9222/devtools/x", "wss://127.0.0.1:9455/x"):
            with self.assertRaises(RuntimeError):
                rednote._Socket(url)
        for name, (fn, description, schema) in rednote.TOOLS.items():
            self.assertIn("never instructions", description, name)


def fake_chrome():
    """A Chrome bundle with nothing in it but its version, so a test needs no Chrome installed."""
    app = tempfile.mkdtemp()
    os.makedirs(os.path.join(app, "Contents", "MacOS"))
    open(os.path.join(app, "Contents", "MacOS", "Google Chrome"), "w").close()
    with open(os.path.join(app, "Contents", "Info.plist"), "wb") as f:
        plistlib.dump({"CFBundleShortVersionString": "158.0.8127.38"}, f)
    return os.path.join(app, "Contents", "MacOS", "Google Chrome")


class OwnChrome(unittest.TestCase):
    def test_the_agents_chrome_is_its_main_program_not_a_helper_with_the_same_profile(self):
        flag = " --user-data-dir=" + rednote.PROFILE + " --remote-debugging-port=9455"
        helper = "/Applications/Google Chrome.app/Contents/Frameworks/X/Helpers/Google Chrome Helper (Renderer).app/Contents/MacOS/Google Chrome Helper (Renderer) --type=renderer" + flag
        owners = rednote.CHROME + " --user-data-dir=/Users/x/other" + flag.split(" --remote")[1]
        ps = "  100 %s\n  200 %s\n  300 %s%s\n" % (helper, owners, rednote.CHROME, flag)
        with mock.patch.object(rednote.subprocess, "run", return_value=mock.Mock(stdout=ps)):
            self.assertEqual(rednote._pid(), 300)

    def test_it_starts_with_no_window_and_not_as_an_app_the_dock_would_bring_forward(self):
        # 2026-11-24: a minimized second Chrome caught the owner's Dock click after they quit their own Chrome
        answers = iter([OSError("not running"), {"webSocketDebuggerUrl": "ws://127.0.0.1:9455/devtools/browser/x"}])

        def devtools(path):
            a = next(answers)
            if isinstance(a, Exception):
                raise a
            return a
        started, profile, chrome = [], tempfile.mkdtemp(), fake_chrome()
        with mock.patch.object(rednote, "PROFILE", profile), mock.patch.object(rednote, "CHROME", chrome), mock.patch.object(rednote, "_devtools", devtools), \
                mock.patch.object(rednote, "SIGNING_IN", os.path.join(profile, "none")), \
                mock.patch.object(rednote, "_ours", lambda: None), mock.patch.object(rednote.time, "sleep", lambda s: None), \
                mock.patch.object(rednote.subprocess, "Popen", lambda argv, **k: started.append((argv, k))), \
                mock.patch.object(rednote.subprocess, "run", side_effect=AssertionError("nothing goes through open")):
            self.assertEqual(rednote._browser(), "ws://127.0.0.1:9455/devtools/browser/x")
        (argv, k), = started
        self.assertEqual(argv[:2], [chrome, "--headless=new"])
        agent = [a for a in argv if a.startswith("--user-agent=")]
        self.assertTrue(agent and "Headless" not in agent[0] and "Chrome/158.0.0.0 " in agent[0])
        self.assertIn("--user-data-dir=" + profile, argv)
        self.assertTrue(k.get("start_new_session"))

    def test_one_with_a_window_is_replaced_except_while_the_owner_signs_in(self):
        mark = os.path.join(tempfile.mkdtemp(), "signing-in")
        quits, started = [], []
        windowed = "ws://127.0.0.1:9455/devtools/browser/old"
        answers = iter([{"webSocketDebuggerUrl": windowed}, {"webSocketDebuggerUrl": "ws://127.0.0.1:9455/devtools/browser/new"}])
        with mock.patch.object(rednote, "SIGNING_IN", mark), mock.patch.object(rednote, "_quit", lambda pid=None: quits.append(pid)), \
                mock.patch.object(rednote, "_devtools", lambda path: next(answers)), mock.patch.object(rednote, "_ours", lambda: None), \
                mock.patch.object(rednote, "_pid", lambda: 300), mock.patch.object(rednote, "_windowless", lambda pid: False), \
                mock.patch.object(rednote, "CHROME", fake_chrome()), mock.patch.object(rednote, "PROFILE", tempfile.mkdtemp()), \
                mock.patch.object(rednote.time, "sleep", lambda s: None), \
                mock.patch.object(rednote.subprocess, "Popen", lambda argv, **k: started.append(argv)):
            self.assertTrue(rednote._browser().endswith("/new"))
            self.assertEqual((quits, [a[1] for a in started]), ([300], ["--headless=new"]))   # that one stopped, a windowless one started
            open(mark, "w").close()
            with self.assertRaisesRegex(RuntimeError, "signing in"):
                rednote._browser()
            self.assertEqual(len(quits), 1)                                # the sign-in window was left alone

if __name__ == "__main__":
    unittest.main()
