#!/usr/bin/env python3
"""Stock and crypto quotes: last price, day change, day and 52-week range, volume and realized
volatility for US-listed stocks (Yahoo Finance's own chart endpoint), and the same shape plus 24h
range for crypto (Binance's public market data). Both are free, keyless and read-only.

The group reads this at Chinese hours while US markets may be shut, so every reply carries its own
asof time and, for stocks, whether the market is open right now: information, never a live feed.

Run one by hand: python3 markets.py <tool> '<json args>'
"""
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0"   # Yahoo answers 429 to some full browser names whatever the pace: on 2026-11-22 a Chrome 125 one was
#                      refused for an hour while this one, sent in the same second from the same Mac, was answered
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/%s"
BINANCE_TICKER = "https://api.binance.com/api/v3/ticker/24hr"
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"

# Common Chinese names (and a few English ones) the group types -> the ticker to ask Yahoo/Binance for.
# Unmapped names: give the ticker itself, in either language.
STOCK_NAMES = {
    "美光": "MU", "英伟达": "NVDA", "苹果": "AAPL", "微软": "MSFT", "谷歌": "GOOGL", "字母表": "GOOGL",
    "亚马逊": "AMZN", "特斯拉": "TSLA", "脸书": "META", "元宇宙": "META", "台积电": "TSM", "博通": "AVGO",
    "高通": "QCOM", "甲骨文": "ORCL", "网飞": "NFLX", "奈飞": "NFLX", "英特尔": "INTC", "超微": "AMD",
    "阿里巴巴": "BABA", "阿里": "BABA", "拼多多": "PDD", "京东": "JD", "小鹏": "XPEV", "蔚来": "NIO",
    "理想": "LI", "好市多": "COST", "星巴克": "SBUX", "迪士尼": "DIS", "波音": "BA", "摩根士丹利": "MS",
    "花旗": "C", "美国银行": "BAC", "高盛": "GS", "沃尔玛": "WMT", "礼来": "LLY", "辉瑞": "PFE",
    "强生": "JNJ", "可口可乐": "KO", "百事": "PEP", "麦当劳": "MCD", "联合健康": "UNH", "思科": "CSCO",
    "摩根大通": "JPM",
}
CRYPTO_NAMES = {
    "比特币": "BTC", "大饼": "BTC", "以太坊": "ETH", "以太币": "ETH", "二饼": "ETH", "狗狗币": "DOGE",
    "瑞波币": "XRP", "瑞波": "XRP", "莱特币": "LTC", "门罗币": "XMR", "艾达币": "ADA", "卡尔达诺": "ADA",
    "波场": "TRX", "波卡": "DOT", "索拉纳": "SOL", "币安币": "BNB", "柴犬币": "SHIB", "泰达币": "USDT",
    "bitcoin": "BTC", "btc": "BTC", "ethereum": "ETH", "eth": "ETH", "dogecoin": "DOGE", "doge": "DOGE",
    "solana": "SOL",
}

CAVEAT = (" Public market data (Yahoo Finance for stocks, Binance for crypto): not trading advice, and "
          "not guaranteed to be this instant's price -- always read and report the asof time and, for "
          "stocks, the market state, rather than implying a live feed.")


def _fetch(url, timeout=8, retries=2):
    host = urllib.parse.urlparse(url).hostname
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:   # a short burst limit; it clears in a few seconds
                time.sleep(0.8 * (attempt + 1))
                continue
            if e.code == 429:
                raise RuntimeError("%s refused the request as too many (429); try again in a minute" % host)
            try:
                return json.loads(e.read().decode("utf-8", "replace"))
            except ValueError:
                raise RuntimeError("%s answered %s" % (host, e.code))
        except (OSError, ValueError) as e:
            raise RuntimeError("could not reach %s (%s)" % (host, getattr(e, "reason", None) or type(e).__name__))


def _resolve(raw, names):
    raw = str(raw or "").strip()
    if not raw:
        raise RuntimeError("symbol is empty")
    if raw in names:
        return names[raw]
    if raw.lower() in names:
        return names[raw.lower()]
    return re.sub(r"[^A-Za-z0-9.\-]", "", raw).upper() or None


def _fmt(x):
    """A price as a phone reply wants it: cents for anything near a dollar or more, enough digits for
    an altcoin worth a few cents without sliding into scientific notation."""
    x = float(x)
    if abs(x) >= 1 or x == 0:
        return round(x, 2)
    if abs(x) < 0.0001:   # a float this small prints as 8.74e-06; the digits are given as text instead
        return ("%.10f" % x).rstrip("0")
    return float(("%.8f" % x).rstrip("0").rstrip(".") or "0")


def _stamp(epoch):
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(epoch)) + " UTC"


def _volatility(closes, trading_periods_per_year):
    """Annualized realized volatility (%) from a run of closes, stdev of daily log returns scaled up.
    None with fewer than three closes: not enough to say anything."""
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:]) if a and b]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return round(math.sqrt(var) * math.sqrt(trading_periods_per_year) * 100, 1)


def _days(args):
    return max(5, min(int(args.get("days", 30)), 90))


# ---------------------------------------------------------------- stocks

def stock_quote(args):
    ticker = _resolve(args.get("symbol"), STOCK_NAMES)
    if not ticker:
        raise RuntimeError("no ticker recognized for %r; use the US ticker (MU, NVDA, AAPL) or a mapped "
                            "Chinese name (美光, 英伟达, 苹果...)" % args.get("symbol"))
    days = _days(args)
    body = _fetch(YAHOO_CHART % urllib.parse.quote(ticker, safe="") + "?interval=1d&range=6mo")
    result = ((body.get("chart") or {}).get("result") or [None])[0]
    if not result:
        err = ((body.get("chart") or {}).get("error") or {}).get("description") or "no data"
        raise RuntimeError("Yahoo Finance has nothing for %s (%s); check the ticker" % (ticker, err))
    meta = result.get("meta") or {}
    if meta.get("regularMarketPrice") is None:
        raise RuntimeError("Yahoo Finance has no current price for %s; check the ticker" % ticker)
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    rows = [(c, h, l) for c, h, l in zip(quote.get("close") or [], quote.get("high") or [], quote.get("low") or [])
            if c is not None and h is not None and l is not None]
    window = rows[-(days + 1):]
    closes = [r[0] for r in window]

    now = time.time()
    ctp = meta.get("currentTradingPeriod") or {}

    def _in(session):
        return bool(session) and session.get("start") is not None and session["start"] <= now < session["end"]

    market = ("open" if _in(ctp.get("regular")) else "pre-market" if _in(ctp.get("pre"))
              else "after-hours" if _in(ctp.get("post")) else "closed")
    asof = meta.get("regularMarketTime")
    hours_old = round((now - asof) / 3600, 1) if asof else None

    out = {
        "symbol": ticker,
        "name": meta.get("longName") or meta.get("shortName") or ticker,
        "currency": meta.get("currency"),
        "price": _fmt(meta["regularMarketPrice"]),
        "change_pct_day": round(meta["regularMarketChangePercent"], 2) if meta.get("regularMarketChangePercent") is not None else None,
        "day_range": "%.2f-%.2f" % (meta["regularMarketDayLow"], meta["regularMarketDayHigh"]) if meta.get("regularMarketDayLow") else None,
        "52w_range": "%.2f-%.2f" % (meta["fiftyTwoWeekLow"], meta["fiftyTwoWeekHigh"]) if meta.get("fiftyTwoWeekLow") else None,
        "volume": meta.get("regularMarketVolume"),
        "market": market,
        "asof": _stamp(asof) if asof else None,
        "hours_old": hours_old,
    }
    if len(window) >= 2:   # one more close than days, to have a first return; the range is of the days themselves
        out["window_days"] = len(window) - 1
        out["range_window"] = "%.2f-%.2f" % (min(r[2] for r in window[1:]), max(r[1] for r in window[1:]))
        vol = _volatility(closes, 252)
        if vol is not None:
            out["volatility_annualized_pct"] = vol
    if market != "open":
        out["note"] = ("US market is %s; this price is from the last session%s, not live." %
                        (market, (" (%.1f hours ago)" % hours_old) if hours_old else ""))
    return out


# ---------------------------------------------------------------- crypto

def crypto_quote(args):
    coin = _resolve(args.get("symbol"), CRYPTO_NAMES)
    if not coin:
        raise RuntimeError("no coin recognized for %r; use its ticker (BTC, ETH, SOL, DOGE...) or a mapped "
                            "Chinese name (比特币, 以太坊, 狗狗币...)" % args.get("symbol"))
    if coin == "USDT":   # every price here is in USDT, so it has no price of its own; saying 1.00 would hide a day it slips
        raise RuntimeError("prices here are quoted in USDT, a coin meant to stay at one US dollar, so USDT itself has no quote")
    days = _days(args)
    pair = coin + "USDT"
    ticker = _fetch(BINANCE_TICKER + "?symbol=" + urllib.parse.quote(pair, safe=""))
    if "symbol" not in ticker:
        raise RuntimeError("Binance has no %s pair (%s); try its ticker (BTC, ETH, SOL, DOGE...)" %
                            (pair, ticker.get("msg") or "not found"))
    now = time.time()
    close_time = ticker.get("closeTime", 0) / 1000
    out = {
        "symbol": coin,
        "pair": pair,
        "price": _fmt(ticker["lastPrice"]),
        "change_pct_24h": round(float(ticker["priceChangePercent"]), 2),
        "range_24h": "%s-%s" % (_fmt(ticker["lowPrice"]), _fmt(ticker["highPrice"])),
        "volume_24h": _fmt(ticker["volume"]),
        "volume_24h_usdt": _fmt(ticker["quoteVolume"]),
        "market": "always open (crypto trades 24/7)",
        "asof": _stamp(close_time) if close_time else None,
        "hours_old": round((now - close_time) / 3600, 2) if close_time else None,
    }
    klines = _fetch(BINANCE_KLINES + "?symbol=%s&interval=1d&limit=%d" % (urllib.parse.quote(pair, safe=""), days + 1))
    if isinstance(klines, list) and len(klines) >= 2:
        closes = [float(k[4]) for k in klines]
        out["window_days"] = len(klines) - 1
        out["range_window"] = "%s-%s" % (_fmt(min(float(k[3]) for k in klines[1:])), _fmt(max(float(k[2]) for k in klines[1:])))
        vol = _volatility(closes, 365)
        if vol is not None:
            out["volatility_annualized_pct"] = vol
    return out


def _schema(props=None, required=None):
    return {"type": "object", "properties": props or {}, "required": required or []}


TOOLS = {
    "stock_quote": (stock_quote,
        "A US stock's last price, day change and %, day and 52-week range, volume, and realized "
        "volatility over the lookback window -- stamped with when the price is from and whether the "
        "US market is open, pre-market, after-hours or closed right now." + CAVEAT,
        _schema({"symbol": {"type": "string", "description": "Ticker (MU, NVDA, AAPL) or a common Chinese "
                             "company name (美光, 英伟达, 苹果, 特斯拉...). Unmapped name: give the ticker."},
                 "days": {"type": "integer", "description": "Lookback window in trading days for the range "
                           "and volatility figures. Default 30, from 5 to 90."}}, ["symbol"])),
    "crypto_quote": (crypto_quote,
        "A crypto coin's last price in USDT (the dollar coin Binance quotes in: say USDT, or about that many "
        "dollars), 24h change and %, 24h and N-day range, and realized volatility over the lookback window "
        "-- stamped with when it was fetched (crypto trades 24/7, so this stays close to live)." + CAVEAT,
        _schema({"symbol": {"type": "string", "description": "Ticker (BTC, ETH, SOL, DOGE...) or a common "
                             "Chinese name (比特币, 以太坊, 狗狗币...). Unmapped name: give the ticker."},
                 "days": {"type": "integer", "description": "Lookback window in days for the range and "
                           "volatility figures. Default 30, from 5 to 90."}}, ["symbol"])),
}


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in TOOLS:
        sys.exit("usage: markets.py <%s> '<json args>'" % " | ".join(TOOLS))
    print(json.dumps(TOOLS[sys.argv[1]][0](json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}), ensure_ascii=False, indent=1))
