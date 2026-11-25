#!/usr/bin/env python3
"""Tests for the stock and crypto quote tools: name resolution, market-state and volatility maths, and
what is said when Yahoo or Binance have nothing or are rate-limiting this Mac. No network: their answers
are stood in for, in the shapes they gave on 2026-11-22. Run: python3 -m unittest test_markets"""
import io
import unittest
import urllib.error
from unittest import mock

import markets

NOW = 1795325000.0   # a moment after MU's regular session (ending 1795208400) has long closed


def yahoo_meta(**over):
    meta = {
        "currency": "USD", "symbol": "MU", "regularMarketPrice": 594.51, "regularMarketChangePercent": -13.894,
        "fiftyTwoWeekHigh": 1255.0, "fiftyTwoWeekLow": 212.36, "regularMarketDayHigh": 668.99,
        "regularMarketDayLow": 585.253, "regularMarketVolume": 59423144, "longName": "Micron Technology, Inc.",
        "regularMarketTime": 1795208401,
        "currentTradingPeriod": {"pre": {"start": 1795165200, "end": 1795185000},
                                 "regular": {"start": 1795185000, "end": 1795208400},
                                 "post": {"start": 1795208400, "end": 1795222800}},
    }
    meta.update(over)
    return meta


def yahoo_chart(closes, meta=None):
    n = len(closes)
    return {"chart": {"result": [{"meta": meta or yahoo_meta(),
                                   "indicators": {"quote": [{"close": closes, "high": [c + 5 for c in closes],
                                                             "low": [c - 5 for c in closes]}]}}]}}


def binance_ticker(**over):
    row = {"symbol": "BTCUSDT", "lastPrice": "58957.69", "priceChangePercent": "4.84",
           "lowPrice": "55130.0", "highPrice": "60996.0", "volume": "35686.06", "quoteVolume": "2094323872.39",
           "closeTime": int(NOW * 1000)}
    row.update(over)
    return row


def binance_klines(closes, high=None, low=None):
    return [[0, "0", str((high or [c + 1000 for c in closes])[i]), str((low or [c - 1000 for c in closes])[i]),
              str(c), "0", 0, "0", 0, "0", "0", "0"] for i, c in enumerate(closes)]


class StockQuote(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(markets.time, "time", return_value=NOW)
        p.start()
        self.addCleanup(p.stop)

    def test_chinese_name_resolves_and_shape_is_phone_sized(self):
        closes = [700.0 + i for i in range(60)] + [594.51]
        with mock.patch.object(markets, "_fetch", return_value=yahoo_chart(closes)):
            out = markets.stock_quote({"symbol": "美光"})
        self.assertEqual(out["symbol"], "MU")
        self.assertEqual(out["name"], "Micron Technology, Inc.")
        self.assertEqual(out["price"], 594.51)
        self.assertEqual(out["change_pct_day"], -13.89)
        self.assertEqual(out["day_range"], "585.25-668.99")
        self.assertEqual(out["52w_range"], "212.36-1255.00")
        self.assertEqual(out["market"], "closed")
        self.assertIn("not live", out["note"])
        self.assertGreater(out["hours_old"], 0)
        self.assertIn("volatility_annualized_pct", out)

    def test_bare_ticker_is_uppercased_without_being_in_the_name_table(self):
        with mock.patch.object(markets, "_fetch", return_value=yahoo_chart([1, 2, 3], meta=yahoo_meta(symbol="nvda"))) as fetched:
            markets.stock_quote({"symbol": "nvda"})
        self.assertIn("NVDA", fetched.call_args[0][0])

    def test_market_open_during_the_regular_session(self):
        with mock.patch.object(markets.time, "time", return_value=1795190000.0), \
             mock.patch.object(markets, "_fetch", return_value=yahoo_chart([1, 2, 3])):
            out = markets.stock_quote({"symbol": "MU"})
        self.assertEqual(out["market"], "open")
        self.assertNotIn("note", out)

    def test_volatility_is_the_annualized_stdev_of_log_returns(self):
        # three closes with one +-5% move each way give a predictable, non-zero annualized figure
        closes = [100.0, 105.0, 100.0]
        with mock.patch.object(markets, "_fetch", return_value=yahoo_chart(closes)):
            out = markets.stock_quote({"symbol": "MU", "days": 2})
        self.assertEqual(out["window_days"], 2)
        self.assertEqual(out["volatility_annualized_pct"], 109.5)   # stdev of ln(1.05), -ln(1.05) = 0.069, times sqrt(252)

    def test_the_range_is_of_the_days_asked_for_not_the_extra_close_the_volatility_needs(self):
        with mock.patch.object(markets, "_fetch", return_value=yahoo_chart([200.0, 100.0, 105.0])):   # highs +5, lows -5
            out = markets.stock_quote({"symbol": "MU", "days": 2})
        self.assertEqual((out["window_days"], out["range_window"]), (2, "95.00-110.00"))            # not up to 205
        with mock.patch.object(markets, "_fetch", side_effect=[binance_ticker(), binance_klines([90000.0, 50000.0, 52000.0])]):
            self.assertEqual(markets.crypto_quote({"symbol": "BTC", "days": 2})["range_window"], "49000.0-53000.0")

    def test_unknown_ticker_says_so(self):
        body = {"chart": {"result": None, "error": {"description": "No data found, symbol may be delisted"}}}
        with mock.patch.object(markets, "_fetch", return_value=body):
            with self.assertRaisesRegex(RuntimeError, "check the ticker"):
                markets.stock_quote({"symbol": "ZZZZNOPE"})

    def test_empty_symbol_is_rejected_before_any_network_call(self):
        with mock.patch.object(markets, "_fetch") as fetched:
            with self.assertRaises(RuntimeError):
                markets.stock_quote({"symbol": "   "})
        fetched.assert_not_called()


class CryptoQuote(unittest.TestCase):
    def test_chinese_name_resolves_to_the_usdt_pair(self):
        closes = [55000.0 + i * 100 for i in range(30)]
        with mock.patch.object(markets, "_fetch", side_effect=[binance_ticker(), binance_klines(closes)]) as fetched:
            out = markets.crypto_quote({"symbol": "比特币"})
        self.assertEqual((out["symbol"], out["pair"]), ("BTC", "BTCUSDT"))
        self.assertEqual(out["price"], 58957.69)
        self.assertEqual(out["change_pct_24h"], 4.84)
        self.assertEqual(out["range_24h"], "55130.0-60996.0")
        self.assertEqual(out["market"], "always open (crypto trades 24/7)")
        self.assertIn("volatility_annualized_pct", out)
        self.assertIn("BTCUSDT", fetched.call_args_list[0][0][0])

    def test_small_price_altcoin_does_not_use_scientific_notation(self):
        with mock.patch.object(markets, "_fetch",
                                side_effect=[binance_ticker(symbol="DOGEUSDT", lastPrice="0.05396", lowPrice="0.05", highPrice="0.06"), []]):
            out = markets.crypto_quote({"symbol": "狗狗币"})
        self.assertEqual(out["price"], 0.05396)
        self.assertNotIn("e", out["range_24h"])
        with mock.patch.object(markets, "_fetch",
                                side_effect=[binance_ticker(symbol="SHIBUSDT", lastPrice="0.00000874", lowPrice="0.0000085", highPrice="0.0000091"), []]):
            out = markets.crypto_quote({"symbol": "柴犬币"})
        self.assertEqual((out["price"], out["range_24h"]), ("0.00000874", "0.0000085-0.0000091"))

    def test_usdt_is_what_prices_are_in_and_is_not_given_a_made_up_price(self):
        with mock.patch.object(markets, "_fetch") as fetched:
            with self.assertRaisesRegex(RuntimeError, "no quote"):
                markets.crypto_quote({"symbol": "泰达币"})
        fetched.assert_not_called()

    def test_another_dollar_coin_is_quoted_like_any_coin(self):
        with mock.patch.object(markets, "_fetch", side_effect=[binance_ticker(symbol="USDCUSDT", lastPrice="0.9712"), []]) as fetched:
            self.assertEqual(markets.crypto_quote({"symbol": "usdc"})["price"], 0.9712)   # a day it slips shows
        self.assertIn("USDCUSDT", fetched.call_args_list[0][0][0])

    def test_unknown_coin_says_so(self):
        with mock.patch.object(markets, "_fetch", return_value={"code": -1121, "msg": "Invalid symbol."}):
            with self.assertRaisesRegex(RuntimeError, "no ZZZZUSDT pair"):
                markets.crypto_quote({"symbol": "ZZZZ"})


class Fetching(unittest.TestCase):
    def test_a_429_is_retried_then_succeeds(self):
        refuse = urllib.error.HTTPError("u", 429, "Too Many Requests", {}, io.BytesIO(b""))
        ok = mock.MagicMock()
        ok.__enter__.return_value.read.return_value = b'{"ok": true}'
        with mock.patch.object(markets.urllib.request, "urlopen", side_effect=[refuse, ok]), \
             mock.patch.object(markets.time, "sleep"):
            self.assertEqual(markets._fetch("https://query1.finance.yahoo.com/x"), {"ok": True})

    def test_a_429_that_does_not_clear_says_rate_limited(self):
        refuse = urllib.error.HTTPError("u", 429, "Too Many Requests", {}, io.BytesIO(b""))
        with mock.patch.object(markets.urllib.request, "urlopen", side_effect=[refuse, refuse, refuse]), \
             mock.patch.object(markets.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "too many"):
                markets._fetch("https://query1.finance.yahoo.com/x")

    def test_a_404_with_a_json_body_is_returned_for_the_caller_to_read(self):
        notfound = urllib.error.HTTPError("u", 404, "Not Found", {}, io.BytesIO(b'{"chart": {"result": null}}'))
        with mock.patch.object(markets.urllib.request, "urlopen", side_effect=notfound):
            self.assertEqual(markets._fetch("https://query1.finance.yahoo.com/x"), {"chart": {"result": None}})

    def test_unreachable_host_says_so_in_words(self):
        with mock.patch.object(markets.urllib.request, "urlopen", side_effect=OSError("timed out")):
            with self.assertRaisesRegex(RuntimeError, "could not reach"):
                markets._fetch("https://api.binance.com/x")

    def test_every_tool_names_its_source_and_is_not_trading_advice(self):
        for name, (fn, description, schema) in markets.TOOLS.items():
            self.assertIn("not trading advice", description, name)


if __name__ == "__main__":
    unittest.main()
