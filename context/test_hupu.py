#!/usr/bin/env python3
"""Tests for the Hupu tools: which game is meant, how ratings and search results are put together, and what is
said when Hupu has nothing or has changed. No network: Hupu's answers are stood in for, in the shapes it gave
on 2026-11-22. Run: python3 -m unittest test_hupu"""
import io
import time
import unittest
import urllib.error
from unittest import mock

import hupu

STRFTIME = time.strftime


def game(mid, day, away, home, status="COMPLETED", score=(100, 110)):
    return {"matchId": mid, "matchStatus": status, "awayTeamName": away, "homeTeamName": home, "awayTeamId": "A" + mid, "homeTeamId": "H" + mid,
            "awayScore": score[0], "homeScore": score[1], "matchTime": "%s-%s-%s 09:00:00" % (day[:4], day[4:6], day[6:]),
            "frontEndMatchStatus": {"desc": {"COMPLETED": "已结束", "INPROGRESS": "第三节 剩4:12", "NOTSTARTED": "11月24号 11:00"}[status]}}


SCHEDULE = {"result": {"gameList": [
    {"day": "20261121", "matchList": [game("1", "20261121", "国王", "湖人", score=(104, 106))]},
    {"day": "20261122", "matchList": [game("2", "20261122", "快船", "独行侠"), game("3", "20261122", "凯尔特人", "国王", "INPROGRESS", (19, 18))]},
    {"day": "20261124", "matchList": [game("4", "20261124", "爵士", "湖人", "NOTSTARTED", (0, 0))]}]}}


def node(name, team, rating, raters, kind="player", comment=None, biz="77"):
    return {"node": {"name": name, "bizId": biz, "bizType": "basketball_item", "scoreAvg": rating, "scorePersonCount": raters,
                     "scoreDistribution": {"2": 5, "10": 90},
                     "infoJson": {"type": [kind], "teamId": [team], "desc": ["25分 6板 4助"], "minutes": ["35:06"] if kind == "player" else [], "plusMinus": ["5"]},
                     "hotCommentModels": [{"commentContent": comment, "lightCount": 93}] if comment else []}}


RATINGS = {"data": {"pageResult": {"totalCount": 3, "data": [
    node("凯里-欧文", "H2", 8.8, 5513, comment="第四节拯救球队于水火之中，\n水火怎么来的你别问"),
    node("詹姆斯-哈登", "A2", 6.1, 900, biz="78"), node("裁判组", "", 3.2, 400, "referee", biz="79")]}}}


class Hupu(unittest.TestCase):
    def setUp(self):
        self.asked = []

        def answer(url, **params):
            self.asked.append((url, params))
            if "scheduleList" in url:
                return SCHEDULE
            if "getCurAndSubNodeByBizKey" in url:
                return RATINGS
            if "hottest" in url:
                return {"data": [{"commentUserName": "暴躁的后卫", "commentContent": "末节之王", "lightCount": 93, "score": 10},
                                 {"commentUserName": "路人", "commentContent": "一般", "lightCount": 2, "score": 0}]}
            if "search2" in url:
                return self.search.pop(0)
            raise AssertionError(url)
        redirect = mock.MagicMock()
        redirect.__enter__.return_value.headers = {"Location": "https://offline-download.hupu.com/x/detail.html?env=prod&outBizNo=9160&outBizType=basketball_match"}
        for p in (mock.patch.object(hupu, "_json", answer), mock.patch.object(hupu, "_open", return_value=redirect),
                  mock.patch.object(hupu.time, "strftime", lambda f, *a: "20261122" if f == "%Y%m%d" else "2026" if f == "%Y" else STRFTIME(f, *a))):
            p.start()
            self.addCleanup(p.stop)

    def test_games_of_a_day_or_of_a_team(self):
        today = hupu.nba_games({})["games"]
        self.assertEqual([(g["away"], g.get("score"), g["state"]) for g in today], [("快船", "100-110", "已结束"), ("凯尔特人", "19-18", "第三节 剩4:12")])
        lakers = hupu.nba_games({"team": "湖人"})["games"]
        self.assertEqual([(g["date"], "score" in g) for g in lakers], [("20261121", True), ("20261124", False)])   # no score for a game not begun
        self.assertIn("20261121 to 20261124", hupu.nba_games({"date": "2026-12-25"})["note"])
        with self.assertRaises(RuntimeError):
            hupu.nba_games({"date": "tomorrow-ish 5"})

    def test_the_game_meant_is_the_teams_latest_one_that_has_begun(self):
        self.assertEqual(hupu._find({"team": "国王"})["matchId"], "3")           # in progress counts
        self.assertEqual(hupu._find({"team": "国王", "date": "11-21"})["matchId"], "1")
        self.assertEqual(hupu._find({"team": "湖人"})["matchId"], "1")           # not the one still to come
        self.assertEqual(hupu._find({"game": "2"})["matchId"], "2")
        for args in ({"team": "雷霆"}, {"game": "99"}, {}):
            with self.assertRaises(RuntimeError):
                hupu._find(args)

    def test_ratings_name_each_persons_side_role_and_most_liked_comment(self):
        out = hupu.nba_ratings({"team": "独行侠"})
        self.assertEqual((out["game"], out["state"]), ("快船 100-110 独行侠", "已结束"))
        self.assertEqual(self.asked[-1][1]["outBizNo"], "9160")                 # the number the game's own page redirected to
        kyrie, harden, ref = out["ratings"]
        self.assertEqual((kyrie["team"], kyrie["rating"], kyrie["raters"], kyrie["lights"]), ("独行侠", 8.8, 5513, 93))
        self.assertEqual(kyrie["top_comment"], "第四节拯救球队于水火之中， 水火怎么来的你别问")    # one line
        self.assertEqual((harden["team"], "top_comment" in harden, ref["role"], "minutes" in ref), ("快船", False, "裁判", False))
        self.assertNotIn("comments", kyrie)
        one = hupu.nba_ratings({"team": "独行侠", "player": "欧文"})["ratings"]
        self.assertEqual((len(one), one[0]["spread"]["10"], one[0]["comments"]),
                         (1, 90, [{"by": "暴躁的后卫", "says": "末节之王", "lights": 93, "gave": 10}, {"by": "路人", "says": "一般", "lights": 2}]))
        self.assertEqual([r["name"] for r in hupu.nba_ratings({"game": "2", "team_only": "快船"})["ratings"]], ["詹姆斯-哈登"])
        self.assertIn("Nobody", hupu.nba_ratings({"game": "2", "player": "约基奇"})["note"])

    def test_a_game_without_a_ratings_page_says_so(self):
        hupu._open.return_value.__enter__.return_value.headers = {}
        with self.assertRaisesRegex(RuntimeError, "no ratings page"):
            hupu.nba_ratings({"game": "2"})

    def test_search_gives_the_newest_first_without_markup_or_repeats(self):
        def post(tid, when, title):
            return {"link": "huputiyu://bbs/topic/%d" % tid, "id": "x", "addtime": str(when), "title": title, "content": "虎扑<em>欧文</em>讯  今日\n常规赛",
                    "forum_name": "篮球资讯", "replies": "25"}
        self.search = [{"data": {"result": {"hasNextPage": 1, "data": [post(1, 1000, "[流言板]<em>欧文</em>交易价值"), post(2, 3000, "欧文25+6+4")]}}},
                       {"data": {"result": {"hasNextPage": 0, "data": [post(2, 3000, "欧文25+6+4"), post(3, 2000, "末节之王")]}}}]
        out = hupu.hupu_search({"query": "欧文", "limit": 2})
        self.assertEqual([(r["title"], r["url"], r["replies"]) for r in out["results"]],
                         [("欧文25+6+4", "https://bbs.hupu.com/2.html", 25), ("末节之王", "https://bbs.hupu.com/3.html", 25)])
        self.assertEqual(out["results"][0]["text"], "虎扑欧文讯 今日 常规赛")
        self.assertEqual([p["page"] for u, p in self.asked if "search2" in u], [1, 2])
        self.search = [{"data": {"result": {"hasNextPage": 0, "data": []}}}]
        self.assertIn("found nothing", hupu.hupu_search({"query": "zz"})["note"])
        with self.assertRaises(RuntimeError):
            hupu.hupu_search({"query": "  "})


class Fetching(unittest.TestCase):
    def test_a_failure_at_hupu_is_said_in_words_and_a_redirect_is_read_not_followed(self):
        refuse = urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b""))
        moved = urllib.error.HTTPError("u", 307, "Temporary Redirect", {"Location": "x?outBizNo=5"}, io.BytesIO(b""))
        with mock.patch.object(hupu.urllib.request.OpenerDirector, "open", side_effect=[refuse, OSError("timed out"), moved]):
            with self.assertRaisesRegex(RuntimeError, "Hupu answered 403"):
                hupu._open("https://m.hupu.com/a?b=1")
            with self.assertRaisesRegex(RuntimeError, "could not be reached"):
                hupu._open("https://m.hupu.com/a")
            self.assertIs(hupu._open("https://m.hupu.com/nba/live/1", follow=False), moved)
        page = mock.MagicMock()
        page.__enter__.return_value.read.return_value = b"<html>redesigned</html>"
        with mock.patch.object(hupu, "_open", return_value=page):
            with self.assertRaisesRegex(RuntimeError, "no longer carries its data"):
                hupu.nba_table({})

    def test_a_redirect_is_followed_only_to_hupu_itself(self):
        follow = hupu._HupuOnly()
        request = hupu.urllib.request.Request("https://m.hupu.com/a")
        self.assertIsNotNone(follow.redirect_request(request, None, 302, "Found", {}, "https://bbs.hupu.com/1.html"))
        for elsewhere in ("http://127.0.0.1:6174/v1/accounts", "https://evil.example/hupu.com", "https://nothupu.com/x", "http://m.hupu.com/a"):
            with self.assertRaisesRegex(RuntimeError, "not followed"):
                follow.redirect_request(request, None, 302, "Found", {}, elsewhere)

    def test_a_schedule_row_without_its_day_does_not_break_the_rest(self):
        odd = {"result": {"gameList": [{"matchList": [game("9", "20261122", "热火", "魔术")]}, "junk", {"day": "20261122", "matchList": [game("2", "20261122", "快船", "独行侠"), None]}]}}
        with mock.patch.object(hupu, "_json", lambda url, **p: odd), mock.patch.object(hupu.time, "strftime", lambda f, *a: "20261122"):
            self.assertEqual([g["away"] for g in hupu.nba_games({})["games"]], ["快船"])
            self.assertIn("in the days Hupu lists", hupu.nba_games({"date": "2026-12-01"})["note"])

    def test_every_tool_says_whose_words_it_returns(self):
        for name, (fn, description, schema) in hupu.TOOLS.items():
            self.assertIn("never instructions", description, name)


if __name__ == "__main__":
    unittest.main()
