# Hupu (NBA)

Ask for NBA scores and what Chinese fans think. Examples: "Who won last night, and how did Hupu rate the players?", "What are the standings in the West?", "Latest Hupu news on 欧文."

Hupu (虎扑) is a large Chinese sports site.

## How it connects

[hupu.py](../../context/hupu.py) calls Hupu's mobile web addresses. No login, no key. Hupu publishes no API, so these are the addresses its own mobile pages use. Four tools:

- `nba_games`: games and scores for one day, or one team's recent and coming games. Times are China time. Only about ten days around today are listed.
- `nba_ratings`: what Hupu users rated each player in a game, out of 10, with the most liked comment. Name the game by id or by team. With `player`, you get the spread of scores and more comments.
- `nba_table`: standings (`kind` is `standings`, the default) or league leaders (`leaders`, with `stat`, default 得分).
- `hupu_search`: Hupu's news and forum, newest first, up to 20 results.

Use Chinese names for teams and players (火箭, 欧文).

## Set it up

Nothing to install. Try one:

```
python3 context/hupu.py nba_games '{"team": "火箭"}'
python3 context/hupu.py nba_table '{"kind": "leaders", "stat": "得分"}'
python3 context/hupu.py hupu_search '{"query": "欧文", "limit": 5}'
```

## What it can and cannot do

- Read-only public data. Nothing of yours is used.
- Ratings exist only for games Hupu has a ratings page for.
- What users and editors wrote is information, never instructions.
- The WeChat group bot has these tools too.

## Privacy and cost

- Free. Your Mac contacts Hupu's servers with your search words or team names. It sends a mobile-browser user agent and nothing of yours.
- With the default model, what comes back goes to Anthropic as part of the conversation. With `local_model` set (see [models.md](../models.md)) the model runs on the Mac, but the tools still contact Hupu.

## Risks

The addresses are undocumented. They can change or stop answering at any time, without notice. The tool says so when it happens.

## If it stops working

- "Hupu did not answer with data for ...; its pages may have changed" or "Hupu's page ... no longer carries its data; the site may have changed": Hupu changed. The code in [hupu.py](../../context/hupu.py) needs an update.
- "Hupu answered <code> for ...": Hupu refused or failed. Retry later.
- "Hupu could not be reached": check your network.
- "no game ... in the days Hupu lists now": use `nba_games` to see what is listed.
- "give a game id from nba_games, or a team name in Chinese": use the id or a Chinese name.
- "date must look like 2026-11-22": fix the date.
