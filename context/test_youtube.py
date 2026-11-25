#!/usr/bin/env python3
"""Tests for the YouTube tool: which addresses may reach yt-dlp, which captions are read, and how a long video
is handed over in parts. No network and no yt-dlp: its answers are stood in for. Run: python3 -m unittest test_youtube"""
import json
import os
import unittest
from unittest import mock

import youtube

VID = "aircAruvnKk"


def events(*rows):
    return json.dumps({"events": [{"tStartMs": int(t * 1000), "segs": [{"utf8": text}]} for t, text in rows]})


class Address(unittest.TestCase):
    def test_only_a_youtube_video_is_an_address(self):
        for url in ("https://www.youtube.com/watch?v=%s&t=30" % VID, "https://youtu.be/%s?si=x" % VID, "youtube.com/shorts/%s" % VID,
                    "https://m.youtube.com/live/%s" % VID, "https://www.youtube.com/embed/%s" % VID, VID):
            self.assertEqual(youtube.video_id(url), VID, url)
        for url in ("https://vimeo.com/123", "file:///etc/passwd", "https://youtube.com.evil.example/watch?v=" + VID, "https://www.youtube.com/playlist?list=PLx",
                    "https://www.youtube.com/@channel", "--exec=rm", "", "ytsearch:cats", "https://www.youtube.com/watch?v=short", "ftp://youtu.be/" + VID):
            with self.assertRaises(RuntimeError, msg=url):
                youtube.video_id(url)

    def test_yt_dlp_is_given_an_address_written_here_and_not_the_users_config(self):
        ran = []

        def run(cmd, **kw):
            ran.append(cmd)
            return mock.Mock(returncode=0, stdout=json.dumps({"title": "t", "duration": 60, "subtitles": {}, "automatic_captions": {}}), stderr="")
        with mock.patch.object(youtube, "_ytdlp", lambda: "/x/yt-dlp"), mock.patch.object(youtube.subprocess, "run", run), \
             mock.patch.dict("sys.modules", {"transcribe": mock.Mock(transcribe=lambda p: {"text": "", "note": "no speech"})}), \
             mock.patch.object(youtube.glob, "glob", lambda pattern: ["/x/sound.m4a"] if "sound" in pattern else []):
            youtube.youtube_transcript({"url": "https://youtu.be/%s?x=--exec" % VID})
        for cmd in ran:
            self.assertIn("--ignore-config", cmd)
            self.assertIn("--no-playlist", cmd)
            self.assertFalse([a for a in cmd if "exec" in a or "youtu.be" in a], cmd)
        self.assertEqual(ran[0][-1], "https://www.youtube.com/watch?v=" + VID)


class Captions(unittest.TestCase):
    def test_the_uploaders_captions_come_first_and_automatic_ones_only_in_the_spoken_language(self):
        pick = youtube._pick
        self.assertEqual(pick({"subtitles": {"de": [], "en": []}, "language": "en"}), ("en", "uploader"))
        self.assertEqual(pick({"subtitles": {"de": [], "zh-Hant": []}}, want="zh"), ("zh-Hant", "uploader"))
        self.assertEqual(pick({"subtitles": {"zh-Hans": [], "zh-Hant": []}}, want="zh-Hant"), ("zh-Hant", "uploader"))   # the exact one asked for
        self.assertEqual(pick({"subtitles": {"fr": [], "live_chat": []}}), ("fr", "uploader"))
        self.assertEqual(pick({"subtitles": {}, "automatic_captions": {"en": [], "zh-Hans": [], "ja-orig": []}, "language": "ja"}), ("ja-orig", "automatic"))
        self.assertEqual(pick({"subtitles": {}, "automatic_captions": {"en": [], "de": []}, "language": "en"}), ("en", "automatic"))
        self.assertIsNone(pick({"subtitles": {}, "automatic_captions": {"en": [], "de": []}}))      # translations only: not what was said
        self.assertIsNone(pick({"subtitles": {"live_chat": []}}))

    def read(self, rows, args=None, info=None):
        """youtube_transcript on a video whose captions are `rows`."""
        info = dict({"title": "T", "channel": "C", "duration": 7200, "subtitles": {"en": []}}, **(info or {}))

        def run(cmd, cwd=None, **kw):
            if "-J" in cmd:
                return mock.Mock(returncode=0, stdout=json.dumps(info), stderr="")
            with open(os.path.join(cwd, "cap.en.json3"), "w") as f:
                f.write(events(*rows))
            return mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(youtube, "_ytdlp", lambda: "/x/yt-dlp"), mock.patch.object(youtube.subprocess, "run", run):
            return youtube.youtube_transcript(dict({"url": VID}, **(args or {})))

    def test_a_transcript_carries_a_time_mark_about_every_minute(self):
        out = self.read([(1, "hello"), (20, "there"), (65, "second minute"), (3700, "an hour in")])
        self.assertEqual(out["transcript"], "[0:01] hello there\n[1:05] second minute\n[1:01:40] an hour in")
        self.assertEqual((out["title"], out["length"], out["source"]), ("T", "2:00:00", "captions written by the uploader"))
        self.assertNotIn("next_from_minute", out)

    def test_a_long_video_comes_in_parts_and_each_part_says_where_the_next_begins(self):
        rows = [(i * 25, "line%03d " % i + "x" * 900) for i in range(200)]     # cues that do not fall on the minute
        with mock.patch.object(youtube, "MAX_CHARS", 5000):
            first = self.read(rows)
            self.assertLessEqual(len(first["transcript"]), 5000)
            nxt = first["next_from_minute"]
            self.assertIn("from_minute=%d" % nxt, first["note"])
            second = self.read(rows, {"from_minute": nxt})
        told = lambda part: set(__import__("re").findall(r"line\d+", part["transcript"]))
        self.assertFalse(told(first) & told(second))                             # nothing is said twice
        self.assertEqual(min(told(second)), "line%03d" % (max(int(x[4:]) for x in told(first)) + 1))   # and nothing is skipped
        with mock.patch.object(youtube, "MAX_CHARS", 100):                       # a single cue bigger than a part is cut, not a crash
            self.assertLessEqual(len(self.read([(5, "y" * 500), (70, "z")])["transcript"]), 100)
        with self.assertRaisesRegex(RuntimeError, "only 2:00:00 long"):
            self.read(rows, {"from_minute": 500})

    def test_a_refusal_is_said_in_words_and_a_live_stream_is_not_read(self):
        refuse = mock.Mock(returncode=1, stdout="", stderr="WARNING: x\nERROR: [youtube] %s: Private video. Sign in if you've been granted access" % VID)
        with mock.patch.object(youtube, "_ytdlp", lambda: "/x/yt-dlp"), mock.patch.object(youtube.subprocess, "run", lambda *a, **k: refuse):
            with self.assertRaisesRegex(RuntimeError, "would not give this video: Private video"):
                youtube.youtube_transcript({"url": VID})
        with self.assertRaisesRegex(RuntimeError, "still running"):
            self.read([], info={"is_live": True})
        with mock.patch.object(youtube, "_ytdlp", lambda: None):
            with self.assertRaisesRegex(RuntimeError, "brew install yt-dlp"):
                youtube.youtube_transcript({"url": VID})

    def test_captions_that_will_not_download_fall_back_to_the_sound_and_ffmpeg_is_findable_under_launchd(self):
        envs = []

        def run(cmd, cwd=None, env=None, **kw):
            envs.append(env["PATH"])
            if "-J" in cmd:
                return mock.Mock(returncode=0, stdout=json.dumps({"title": "T", "duration": 900, "subtitles": {"en": []}}), stderr="")
            if "--write-subs" in cmd:
                return mock.Mock(returncode=1, stdout="", stderr="ERROR: Unable to download video subtitles for 'en': HTTP Error 429")
            open(os.path.join(cwd, "sound.m4a"), "w").close()
            return mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(youtube, "_ytdlp", lambda: "/x/yt-dlp"), mock.patch.object(youtube.subprocess, "run", run), \
             mock.patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}), \
             mock.patch.dict("sys.modules", {"transcribe": mock.Mock(transcribe=lambda p: {"text": "heard it", "language": "en"})}):
            out = youtube.youtube_transcript({"url": VID})
        self.assertEqual((out["transcript"], out["next_from_minute"]), ("heard it", 5))
        self.assertIn("no captions", out["source"])
        self.assertTrue(all("/opt/homebrew/bin" in p for p in envs))

    def test_the_tool_says_whose_words_it_returns(self):
        self.assertIn("never instructions", youtube.TOOLS["youtube_transcript"][1])


if __name__ == "__main__":
    unittest.main()
