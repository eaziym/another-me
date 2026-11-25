"""odds.py with the network stood in for (shapes seen 2026-11-23). Run: python3 -m unittest test_odds"""
import unittest
from unittest import mock

import odds

BOARD = {"events": [{"id": "1", "name": "Dallas Mavericks at Utah Jazz", "shortName": "DAL @ UTA", "date": "2026-11-23T00:00Z",
                     "status": {"type": {"state": "in", "description": "In Progress", "detail": "Q4 1:00"}},
                     "competitions": [{"id": "1", "competitors": [
                         {"homeAway": "home", "score": "110", "team": {"displayName": "Utah Jazz", "abbreviation": "UTA"}},
                         {"homeAway": "away", "score": "111", "team": {"displayName": "Dallas Mavericks", "abbreviation": "DAL"}}]}]}]}
ODDS = {"items": [{"provider": {"name": "DraftKings"}, "details": "DAL -1.5", "overUnder": 226.5, "overOdds": -110.0,
                   "homeTeamOdds": {"moneyLine": 120}, "awayTeamOdds": {"moneyLine": -140}}]}
POLY = {"events": [{"title": "Mavericks vs. Jazz", "endDate": "x", "volume": 5, "markets": [
    {"question": "Mavericks vs. Jazz", "outcomes": '["Mavericks","Jazz"]', "outcomePrices": '["0.6","0.4"]', "volume": 9},
    {"question": "Will X?", "outcomes": '["Yes","No"]', "outcomePrices": '["0.25","0.75"]', "volume": 1},
    {"question": "gone", "closed": True, "outcomes": '["Yes","No"]', "outcomePrices": '["1","0"]'}]}]}


class OddsTests(unittest.TestCase):
    def test_game_odds(self):
        with mock.patch.object(odds, "_fetch", side_effect=[BOARD, ODDS]):
            out = odds.game_odds({"team": "mavericks", "date": "2026-11-22"})
        o = out["games"][0]["odds"]
        self.assertEqual((o["line"], o["moneyline_away"], o["implied_win_pct_away"]), ("DAL -1.5", -140, 58.3))
        self.assertRegex(out["fetched"], r"^\d{4}-\d\d-\d\d \d\d:\d\d UTC \(\d\d-\d\d \d\d:\d\d %s time\)$" % odds.ZONE)   # the bot read UTC alone an hour wrong
        self.assertIn("in progress", o["note"])

    def test_no_line_is_not_an_error(self):
        with mock.patch.object(odds, "_fetch", side_effect=[BOARD, {}]):
            self.assertIsNone(odds.game_odds({"date": "2026-11-22"})["games"][0]["odds"])

    def test_bad_input_refused(self):
        with self.assertRaises(RuntimeError):
            odds.game_odds({"league": "curling"})
        with self.assertRaises(RuntimeError):
            odds.game_odds({"date": "tomorrow"})
        with self.assertRaises(RuntimeError):
            odds.market_odds({"query": " "})

    def test_market_odds_skips_closed_and_shortens_yes_no(self):
        with mock.patch.object(odds, "_fetch", return_value=POLY):
            ev = odds.market_odds({"query": "x"})["events"][0]
        self.assertEqual([m["market"] for m in ev["markets_shown"]], ["Mavericks vs. Jazz", "Will X?"])
        self.assertEqual(ev["markets_shown"][0]["chance"]["Mavericks"], "60.0%")
        self.assertEqual(ev["markets_shown"][1]["chance"], {"Yes": "25.0%"})

    def test_history_points_show_the_dip_and_before_start(self):
        start = 1000000
        series = [(start - 600, .55), (start + 60, .6), (start + 120, .8), (start + 180, 1.0), (start + 240, .68), (start + 300, 1.0)]
        series += [(start + 300 + 60 * k, 1.0) for k in range(1, 30)]
        poly = {"events": [{"title": "A vs. B", "markets": [{"question": "A vs. B", "outcomes": '["A","B"]', "volume": 9,
                "clobTokenIds": '["t1","t2"]', "gameStartTime": "1970-01-12 13:46:40+00"}]}]}
        hist = {"history": [{"t": t, "p": p} for t, p in series]}
        with mock.patch.object(odds, "_fetch", side_effect=[poly, hist]), mock.patch.object(odds.time, "time", return_value=start + 4000):
            row = odds.market_history({"query": "a b"})["series"][0]
        marks = {m: p["chance"] for p in row["points"] for m in p.get("is", "").split(" + ")}
        self.assertEqual(marks["before start"], "55.0%")
        self.assertEqual(marks["deepest fall from an earlier high"], "68.0%")
        self.assertEqual(marks["latest"], "100.0%")
        self.assertLessEqual(len(row["points"]), odds.MAX_POINTS)
        self.assertTrue(row["window_sgt"] and row["game_start_sgt"])

    def test_history_long_window_is_fetched_in_chunks_and_empty_is_a_note(self):
        poly = {"events": [{"title": "T", "markets": [{"question": "Yes?", "outcomes": '["Yes","No"]', "volume": 1, "clobTokenIds": '["t1","t2"]'}]}]}
        fetch = mock.Mock(side_effect=[poly] + [{"history": []}] * 10)
        with mock.patch.object(odds, "_fetch", fetch):
            out = odds.market_history({"query": "t", "days": 30})
        spans = [(c.args[0].split("startTs=")[1].split("&")[0], c.args[0].split("endTs=")[1].split("&")[0]) for c in fetch.call_args_list[1:]]
        spans = [(int(a), int(b)) for a, b in spans]
        self.assertTrue(all(b - a <= odds.CHUNK for a, b in spans))   # the endpoint refuses a span over about two weeks
        self.assertTrue(all(spans[i][1] == spans[i + 1][0] for i in range(len(spans) - 1)))   # no gap between slices
        self.assertGreaterEqual(spans[-1][1] - spans[0][0], 29 * 86400)
        with mock.patch.object(odds, "_fetch", return_value=poly):
            with self.assertRaises(RuntimeError):
                odds.market_history({"query": "t", "outcome": "Utah"})   # not silently the first outcome
        self.assertIn("no price history", out["series"][0]["note"])
        with self.assertRaises(RuntimeError):
            odds.market_history({"query": ""})

    def test_only_reads(self):
        self.assertTrue(odds.POLY_HISTORY.startswith("https://clob.polymarket.com/prices-history"))
        for name in ("game_odds", "market_odds", "market_history"):
            self.assertIn("not betting advice", odds.TOOLS[name][1])
        self.assertTrue(all(u.startswith("https://") for u in (odds.ESPN_BOARD, odds.ESPN_ODDS, odds.POLY_SEARCH)))


if __name__ == "__main__":
    unittest.main()
