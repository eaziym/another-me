#!/usr/bin/env python3
"""Betting odds and prediction-market prices, read-only, free, no key or login.

- `game_odds`: sportsbook lines (DraftKings, as ESPN publishes them) for games of a league on a day:
  spread, total, moneylines and the win chance the moneylines imply.
- `market_odds`: Polymarket's public search: the chance the market gives each outcome (a price in dollars
  of a share that pays $1 is the market's probability), with volume and end date. It also lists the
  game markets Polymarket runs on NBA and soccer games, live while they play.

Nothing here places or prepares a bet or an order, and nothing reads an account. Every reply carries the
time it was fetched and says it is market data, not advice.

Run one by hand: python3 odds.py <tool> '<json args>'
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zoneinfo

UA = "Mozilla/5.0"
ESPN_BOARD = "https://site.api.espn.com/apis/site/v2/sports/%s/scoreboard?dates=%s"
ESPN_ODDS = "https://sports.core.api.espn.com/v2/sports/%s/events/%s/competitions/%s/odds"
POLY_SEARCH = "https://gamma-api.polymarket.com/public-search?q=%s&limit_per_type=%d&events_status=active"

LEAGUES = {   # what a person types -> ESPN's sport/league path
    "nba": "basketball/nba", "wnba": "basketball/wnba", "ncaab": "basketball/mens-college-basketball",
    "nfl": "football/nfl", "ncaaf": "football/college-football", "mlb": "baseball/mlb", "nhl": "hockey/nhl",
    "epl": "soccer/eng.1", "premier": "soccer/eng.1", "laliga": "soccer/esp.1", "bundesliga": "soccer/ger.1",
    "seriea": "soccer/ita.1", "ligue1": "soccer/fra.1", "mls": "soccer/usa.1", "ucl": "soccer/uefa.champions",
    "uel": "soccer/uefa.europa", "worldcup": "soccer/fifa.world"
}
MAX_GAMES = 8
CAVEAT = (" Market data (sportsbook lines and Polymarket prices), not betting advice; say when it was fetched "
          "(the fetched time in the reply) and never imply it is a guaranteed live feed. For a game already "
          "finished or in play, a price near 0 or 100% means it is decided or nearly so.")


def _fetch(url, timeout=8, allow_404=False):
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    host = urllib.parse.urlparse(url).hostname
    try:
        with urllib.request.urlopen(request, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404 and allow_404:
            return {}
        raise RuntimeError("%s answered %s" % (host, e.code))
    except (OSError, ValueError) as e:
        raise RuntimeError("could not reach %s (%s)" % (host, getattr(e, "reason", None) or type(e).__name__))


def _zone_name():
    """The Mac's own time zone by name (Asia/Singapore, Europe/London): the owner's times are given in it."""
    name = os.environ.get("TZ") or os.path.realpath("/etc/localtime").partition("zoneinfo/")[2]
    try:
        zoneinfo.ZoneInfo(name)
        return name
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return "UTC"


ZONE = _zone_name()
LOCAL = zoneinfo.ZoneInfo(ZONE)


def _sgt(ts):
    """A time as the owner reads it, in the Mac's own zone (the name is from when that was Singapore)."""
    return datetime.datetime.fromtimestamp(ts, LOCAL).strftime("%m-%d %H:%M")


def _now():
    """When a reply was fetched, in UTC and in the owner's time: given UTC alone, the group bot said "about 11:40"
    at 10:40 (2026-11-23)."""
    now = time.time()
    return "%s UTC (%s %s time)" % (time.strftime("%Y-%m-%d %H:%M", time.gmtime(now)), _sgt(now), ZONE)


def _implied(ml):
    """American moneyline -> the chance it implies, in percent (the bookmaker's margin is still in it)."""
    try:
        ml = float(ml)
    except (TypeError, ValueError):
        return None
    if ml == 0:
        return None
    p = 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)
    return round(p * 100, 1)


def _num(x):
    return None if x is None else (int(x) if float(x) == int(x) else x)


def _schedule_date(args):
    day = str(args.get("date") or "").replace("-", "")
    if day and not (len(day) == 8 and day.isdigit()):
        raise RuntimeError("date must look like 2026-11-23")
    # US games belong to the US date; New York's, with its own daylight saving
    return day or datetime.datetime.now(zoneinfo.ZoneInfo("America/New_York")).strftime("%Y%m%d")


def game_odds(args):
    league = str(args.get("league") or "nba").lower().replace(" ", "").replace("-", "")
    path = LEAGUES.get(league)
    if not path:
        raise RuntimeError("league %r not known; use one of: %s" % (league, ", ".join(sorted(LEAGUES))))
    team = str(args.get("team") or "").strip().lower()
    day = _schedule_date(args)
    board = _fetch(ESPN_BOARD % (path, day))
    games = []
    for ev in board.get("events") or []:
        comp = (ev.get("competitions") or [{}])[0]
        names = " ".join([ev.get("name", ""), ev.get("shortName", "")] +
                          [(c.get("team") or {}).get(k, "") for c in comp.get("competitors", [])
                           for k in ("displayName", "abbreviation", "shortDisplayName")]).lower()
        if team and team not in names:
            continue
        games.append((ev, comp))
    out = {"league": league, "date": "%s-%s-%s" % (day[:4], day[4:6], day[6:]), "fetched": _now(), "games": []}
    for ev, comp in games[:MAX_GAMES]:
        st = (ev.get("status") or {}).get("type") or {}
        sides = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        name = lambda k: ((sides.get(k) or {}).get("team") or {}).get("displayName")
        g = {"game": "%s at %s" % (name("away"), name("home")), "status": st.get("description"),
             "detail": st.get("detail"), "starts": ev.get("date"),
             "score": "%s %s - %s %s" % (name("away"), (sides.get("away") or {}).get("score"),
                                          name("home"), (sides.get("home") or {}).get("score"))
             if st.get("state") in ("in", "post") else None}
        try:
            items = _fetch(ESPN_ODDS % (path, ev["id"], comp.get("id") or ev["id"]), allow_404=True).get("items") or []
        except RuntimeError as e:
            items = []
            g["odds_error"] = str(e)
        if items:
            o = items[0]
            h, a = o.get("homeTeamOdds") or {}, o.get("awayTeamOdds") or {}
            g["odds"] = {"book": (o.get("provider") or {}).get("name"), "line": o.get("details"),
                         "total": o.get("overUnder"), "over_odds": _num(o.get("overOdds")),
                         "under_odds": _num(o.get("underOdds")),
                         "moneyline_home": _num(h.get("moneyLine")), "moneyline_away": _num(a.get("moneyLine")),
                         "implied_win_pct_home": _implied(h.get("moneyLine")),
                         "implied_win_pct_away": _implied(a.get("moneyLine"))}
            draw = (o.get("drawOdds") or {}).get("moneyLine")
            if draw is not None:   # soccer is three-way
                g["odds"]["moneyline_draw"] = _num(draw)
                g["odds"]["implied_draw_pct"] = _implied(draw)
            if st.get("state") == "post":
                g["odds"]["note"] = "game is over: these are the closing lines"
            elif st.get("state") == "in":
                g["odds"]["note"] = "game in progress: ESPN's feed can lag the live line by minutes; Polymarket (market_odds) may be fresher"
        else:
            g["odds"] = None
            g["odds_note"] = "ESPN publishes no sportsbook line for this game (try market_odds for Polymarket's)"
        out["games"].append(g)
    if not games:
        out["note"] = "no %s games%s found on that date (US date; try the day before or after)" % (league, " for " + team if team else "")
    elif len(games) > MAX_GAMES:
        out["note"] = "%d games matched, first %d shown; give a team to narrow" % (len(games), MAX_GAMES)
    out["caveat"] = CAVEAT.strip()
    return out


def _list(x):
    if isinstance(x, str):
        try:
            x = json.loads(x)
        except ValueError:
            return []
    return x if isinstance(x, list) else []


def _fl(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def market_odds(args):
    query = str(args.get("query") or "").strip()[:100]
    if not query:
        raise RuntimeError("query is empty")
    n = max(1, min(int(args.get("events") or 3), 5))
    body = _fetch(POLY_SEARCH % (urllib.parse.quote(query), n))
    out = {"source": "Polymarket (public data)", "fetched": _now(), "events": []}
    for ev in (body.get("events") or [])[:n]:
        markets = [m for m in ev.get("markets") or [] if not m.get("closed")]
        if len(markets) > 6 and all(_list(m.get("outcomes")) == ["Yes", "No"] for m in markets):
            # a field of candidates (a champion, a winner): the favourites are what is asked, not the busiest
            markets.sort(key=lambda m: -(_fl((_list(m.get("outcomePrices")) or [0])[0])))
        else:
            markets.sort(key=lambda m: -_fl(m.get("volume")))
        rows = []
        for m in markets[:8]:
            outs, prices = _list(m.get("outcomes")), _list(m.get("outcomePrices"))
            if not outs or len(outs) != len(prices):
                continue
            try:
                chance = {o: "%.1f%%" % (float(p) * 100) for o, p in zip(outs, prices)}
            except (TypeError, ValueError):
                continue   # a missing price is not a zero chance
            if list(chance) == ["Yes", "No"]:
                chance = {"Yes": chance["Yes"]}
            rows.append({"market": m.get("question"), "chance": chance, "volume_usd": round(_fl(m.get("volume")))})
        out["events"].append({"event": ev.get("title"), "ends": ev.get("endDate"),
                              "volume_usd": round(_fl(ev.get("volume"))), "markets_total": len(markets),
                              "markets_shown": rows})
    if not out["events"]:
        out["note"] = "nothing active on Polymarket for that search; try other words (English names work best)"
    out["caveat"] = ("Polymarket prices are the market's probabilities (a $0.62 share = 62%), set by traders, "
                     "not facts." + CAVEAT).strip()
    return out


POLY_HISTORY = "https://clob.polymarket.com/prices-history?market=%s&startTs=%d&endTs=%d&fidelity=%d"
MAX_POINTS = 9
CHUNK = 12 * 86400


def _parse_ts(s):
    """'2026-11-23 00:00:00+00' or '...Z' -> epoch seconds, or None."""
    t = str(s).strip().replace("Z", "+00:00").replace(" ", "T", 1)
    if len(t) >= 3 and t[-3] in "+-" and t[-2:].isdigit() and ":" not in t[-3:]:
        t += ":00"
    try:
        d = datetime.datetime.fromisoformat(t)
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)).timestamp()


def _pick_points(hist, before=None):
    """A short series from a long one: the last price at or before `before` (else the first), the high, the
    low, the latest and evenly spaced ones between, in time order, at most MAX_POINTS."""
    first = hist[0]
    if before is not None:
        earlier = [p for p in hist if p["t"] <= before]
        first = earlier[-1] if earlier else first
    marks = {}
    def mark(p, label):
        marks.setdefault(id(p), []).append(label)
    mark(first, "before start" if before is not None and first["t"] <= before else "first")
    mark(max(hist, key=lambda p: p["p"]), "high")
    mark(min(hist, key=lambda p: p["p"]), "low")
    mark(hist[-1], "latest")
    peak, drop, trough = hist[0], 0, None   # the deepest fall from an earlier high: a game's comeback or a tie
    for p in hist:
        if p["p"] > peak["p"]:
            peak = p
        if peak["p"] - p["p"] > drop:
            drop, trough = peak["p"] - p["p"], p
    if trough is not None and drop >= 0.1:
        mark(trough, "deepest fall from an earlier high")
    i = hist.index(first)
    rest = [p for p in hist[i:] if id(p) not in marks]
    room = MAX_POINTS - len(marks)
    for k in range(max(room, 0)):
        if rest:
            marks.setdefault(id(rest[(k + 1) * len(rest) // (room + 1)]), [])
    by_id = {id(p): p for p in hist}
    pts = sorted(((by_id[i], m) for i, m in marks.items()), key=lambda x: x[0]["t"])
    return [{"time_sgt": _sgt(p["t"]), "chance": "%.1f%%" % (p["p"] * 100), **({"is": " + ".join(m)} if m else {})} for p, m in pts]


def market_history(args):
    query = str(args.get("query") or "").strip()[:100]
    if not query:
        raise RuntimeError("query is empty")
    want_market = str(args.get("market") or "").strip().lower()[:100]
    want_outcome = str(args.get("outcome") or "").strip().lower()[:60]
    days = args.get("days")
    days = max(0.1, min(float(days), 90)) if days else None
    now = int(time.time())
    out = {"source": "Polymarket (public price history)", "fetched": _now(),
           "times": ZONE, "series": []}
    # not only the active ones: a game that is over has left that list. Search order is relevance; open first.
    body = _fetch(POLY_SEARCH.replace("&events_status=active", "") % (urllib.parse.quote(query), 5))
    evs = body.get("events") or []
    evs.sort(key=lambda e: bool(e.get("closed")))
    pick = None
    for ev in evs:   # the first event that has the market asked for
        ms = [m for m in ev.get("markets") or [] if _list(m.get("clobTokenIds")) and len(_list(m.get("outcomes"))) == len(_list(m.get("clobTokenIds")))]
        if want_market:
            ms = [m for m in ms if want_market in (str(m.get("question")) + " " + str(m.get("groupItemTitle"))).lower()]
        if ms:
            pick = (ev, sorted(ms, key=lambda m: -_fl(m.get("volume"))))
            break
    for ev, ms in [pick] if pick else []:
        for m in ms[:1]:
            outs, toks = _list(m.get("outcomes")), _list(m.get("clobTokenIds"))
            idx = [i for i, o in enumerate(outs) if want_outcome and want_outcome in str(o).lower()]
            if want_outcome and not idx:
                raise RuntimeError("outcome %r is not one of: %s" % (want_outcome, ", ".join(map(str, outs))))
            idx = idx or [0]
            start = _parse_ts(m.get("gameStartTime")) if m.get("gameStartTime") else None
            if days:
                lo, hi, fid = now - int(days * 86400), now, 1 if days <= 1 else 10 if days <= 7 else 60
            elif start:   # a game: three hours before the start to five hours after, as far as now
                hi = min(now, int(start) + 5 * 3600)
                lo, fid = min(int(start) - 3 * 3600, hi - 3 * 3600), 1   # not yet started: the last few hours
            else:
                lo, hi, fid = now - 30 * 86400, now, 60
            if hi - lo > 40 * 86400:
                fid = 360
            for i in idx[:1]:
                h = []
                for a in range(lo, hi, CHUNK):   # the endpoint refuses a span over about two weeks
                    h += _fetch(POLY_HISTORY % (toks[i], a, min(a + CHUNK, hi), fid), allow_404=True).get("history") or []
                h = sorted({p["t"]: p for p in h if isinstance(p.get("p"), (int, float)) and "t" in p}.values(), key=lambda p: p["t"])
                row = {"market": m.get("question"), "event": ev.get("title"), "outcome": outs[i],
                       "window_sgt": "%s to %s" % (_sgt(lo), _sgt(hi))}
                if start:
                    row["game_start_sgt"] = _sgt(start)
                if len(outs) == 2:
                    row["note"] = "the other outcome (%s) is about 100%% minus this" % outs[1 - i]
                if h:
                    row["points"] = _pick_points(h, start if start and lo <= start <= hi else None)
                else:
                    row["note"] = "no price history in that window (try days=30)"
                out["series"].append(row)
    if not out["series"]:
        out["note"] = "no matching Polymarket market with history; try other English words, or market_odds first"
    out["caveat"] = ("Polymarket price history: each point is the market's chance for the outcome then, set by "
                     "traders, not a fact; a thin or fast-moving market has jumpy points. Give times in the owner's "
                     "time as shown and say when it was fetched." + CAVEAT).strip()
    return out


def _schema(props, required=None):
    return {"type": "object", "properties": props, "required": required or []}


TOOLS = {
    "game_odds": (game_odds,
        "Sportsbook odds for a day's games in one league: point spread, over/under total, moneylines and the "
        "win chance they imply, with the score and status of each game. NBA, NFL, MLB, NHL, college, the big "
        "soccer leagues. Use it for 'what are the odds on this game'; for a live game also try "
        "market_odds, which is often fresher." + CAVEAT,
        _schema({"league": {"type": "string", "description": "nba (default), nfl, mlb, nhl, wnba, ncaab, epl, laliga, bundesliga, seriea, ligue1, mls, ucl, uel, worldcup"},
                 "team": {"type": "string", "description": "Only games with this team (English name or abbreviation: Lakers, LAL, Arsenal)"},
                 "date": {"type": "string", "description": "Local US game date, YYYY-MM-DD. Default: today's US date. An NBA game played at Beijing/Singapore morning belongs to the US date before."}})),
    "market_odds": (market_odds,
        "Polymarket prediction-market prices: what the market gives each outcome (elections, champions, "
        "awards, prices, news, and the live win and spread markets on NBA and soccer games). Search in "
        "English, e.g. 'Mavericks Jazz', 'NBA champion 2027', 'Fed rate cut December'." + CAVEAT,
        _schema({"query": {"type": "string", "description": "English search words"},
                 "events": {"type": "integer", "description": "How many matching events, default 3, max 5"}}, ["query"])),
    "market_history": (market_history,
        "How one Polymarket outcome's price (the market's chance) moved over time, as a few points with local "
        "times: the price before the start, the high, the low, the latest and some between. For a game (e.g. "
        "'Mavericks Jazz') the window is from before tip-off to the end; for anything else the last 30 days, or "
        "`days`. Use it for 'how did the odds move', 'what was the chance before the game / at the tie'. Pick the "
        "outcome with `outcome` (a team name, Yes) and a sub-market with `market` (e.g. 'Spread', 'Celtics')." + CAVEAT,
        _schema({"query": {"type": "string", "description": "English search words, as for market_odds"},
                 "market": {"type": "string", "description": "Words from the market's question to pick it within the event (default: the busiest, i.e. the winner market of a game)"},
                 "outcome": {"type": "string", "description": "Which outcome's price to follow (team name; default the first, Yes for a yes/no market)"},
                 "days": {"type": "number", "description": "Window ending now, in days (max 90). Default: a game's own span, else 30"}}, ["query"])),
}


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in TOOLS:
        sys.exit("usage: odds.py <%s> '<json args>'" % " | ".join(TOOLS))
    print(json.dumps(TOOLS[sys.argv[1]][0](json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}), ensure_ascii=False, indent=1))
