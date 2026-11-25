# Markets and odds

Ask for prices and odds. Examples: "What is NVDA doing?", "BTC price and its range this week", "What odds do the sportsbooks give the Lakers tonight?", "How did Polymarket's chance for this game move?"

These tools are read-only. They give market data, not advice. Nothing places a bet or an order, and nothing reads an account.

## How it connects

No key, no login. All of these are public endpoints.

[markets.py](../../context/markets.py):

- `stock_quote`: a US stock's last price, day change, day and 52-week range, volume and realized volatility, stamped with its time and whether the US market is open. Data from Yahoo Finance. Give a ticker or a common Chinese company name.
- `crypto_quote`: a coin's price in USDT (a coin meant to stay at one US dollar), 24-hour change and range, from Binance. USDT itself has no quote.
- `days` sets the lookback for ranges and volatility (default 30, from 5 to 90).

[odds.py](../../context/odds.py):

- `game_odds`: sportsbook spread, total and moneylines for a day's games, from ESPN's public odds feed, with the win chance the moneylines imply. Leagues: nba, nfl, mlb, nhl, wnba, ncaab, ncaaf, epl, laliga, bundesliga, seriea, ligue1, mls, ucl, uel, worldcup. The date is the US game date.
- `market_odds`: Polymarket's public search. The price of a share that pays $1 is the market's chance for an outcome. Search in English.
- `market_history`: how one Polymarket outcome's price moved, as at most nine points. For a game, the window runs from before tip-off to the end. Otherwise it is 30 days, or `days` (max 90).

Times in odds replies are in your Mac's own time zone (UTC if it cannot be read).

## Set it up

Nothing to install. Try them:

```
python3 context/markets.py stock_quote '{"symbol": "NVDA"}'
python3 context/markets.py crypto_quote '{"symbol": "BTC"}'
python3 context/odds.py game_odds '{"league": "nba"}'
python3 context/odds.py market_odds '{"query": "NBA champion 2027"}'
```

## What it can and cannot do

- Quotes are not a live feed. Each reply carries the time it is from.
- ESPN has a line for only some games.
- Stocks: US-listed only.
- Everything is labelled market data, not trading or betting advice.

## Privacy and cost

- Free. Your Mac contacts Yahoo Finance and Binance (quotes), ESPN (game odds) and Polymarket (market odds and history). They see the ticker, team or search words, and your IP address.
- With the default model, replies go to Anthropic as part of the conversation. With `local_model` set (see [models.md](../models.md)) the model runs on the Mac, but the tools still contact these services.
- The WeChat group bot has these tools too.

## Risks

The endpoints are public but not promised. They can change or rate-limit you. Do not rely on a reply for a trade or bet.

## If it stops working

- "... refused the request as too many (429); try again in a minute": wait.
- "no ticker recognized for ...": use the US ticker.
- "Yahoo Finance has nothing for ...": check the ticker.
- "Binance has no ... pair": use the coin's ticker (BTC, ETH).
- "league ... not known": use one from the list above.
- "date must look like 2026-11-23": fix the date.
- "could not reach ...": check your network.
