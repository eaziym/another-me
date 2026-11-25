# Daily feed

Once a day the agent sends you a short message on Telegram with the few things from the last day that matter to you, from X and the news. On a day with nothing worth your time, it sends nothing.

- "/feed" (get one now)
- "More on the second item in my feed."
- "/feed off" (stop the daily one)

## How it connects

[`context/feed.py`](../../context/feed.py) is run by the entry service ([`entry.py`](../../context/entry.py)). One run does this:

1. One `x_posts` call for each group of accounts in your settings (at most 3 groups, 10 posts each, the last day). See [X posts](x.md); it needs the key described there.
2. One Claude call with web search and no other tool. It reads the posts as data, searches the day's news for your first interests, and writes at most `max_items` items (never more than 5) or the single word `NOTHING`.

The message goes to Telegram only, never to WeChat. Each item has a headline, one or two sentences, and a source link. The message ends with its cost.

## Set it up

1. Set up X posts first ([X posts](x.md)).
2. Create `~/.config/anotherme/feed.json`:

```json
{"on": true, "hour": 8, "max_items": 5,
 "interests": "who you are and what you care about, most important first",
 "x": [{"name": "AI", "look_for": "new models, prices, tools", "handles": ["handle1", "handle2"]}]}
```

- `on`: must be true, or the daily feed never runs.
- `hour`: the daily feed runs after this hour, before 23:00, once a day (default 8).
- `max_items`: at most this many items (default 5, never above 5).
- `interests`: who you are and what you care about. The model decides what clears the bar from this.
- `x`: up to three groups. `name`, `look_for` (what to look for in their posts) and `handles` (X accounts).

3. Restart the entry service so it sees the file. Then send `/feed` on Telegram.

Without a settings file the feed has nothing to go on, and `/feed on` says so.

## What it can and cannot do

- `/feed`: build one now (takes a couple of minutes). If nothing clears the bar, it says so.
- `/feed off`, `/feed on`: stop or restart the daily one. This does not change `feed.json`.
- `feed_last`: lets the agent read the newest feed that was sent, with the X posts it came from, so you can ask a follow-up.
- Notes you kept that mention "feed", "digest", 简报, 推送 or 日报 steer it ("in my feed, less crypto"). Your other notes are not given to this call, because it reads strangers' posts. Notes waiting for `/keep` are not used. See [memory](../memory.md).
- The last five days of feeds are shown to the model so it does not repeat itself.
- Sent feeds are kept in `~/.config/anotherme/feed/<day>.json`, with a `log.jsonl` of costs.

The posts and pages it reads are other people's words: information to weigh, never instructions.

## Privacy and cost

By default the Claude call runs on Claude through Claude Code, so your `interests`, your steering notes and the posts are sent to Anthropic. The X side goes to Grok through OpenRouter (see [X posts](x.md)). With `local_model` set in `~/.config/anotherme/config.json` (see [models](../models.md)) the feed does not run. It checks what it reports with web search, which a local model doesn't have. It stops before paying for any X lookups, and `/feed` tells you why.

Caps from the code: the Claude call is limited to $0.40; the feed's X lookups have their own daily cap of $0.40 (each lookup counts as about $0.07). The message tells you what that day's feed cost. `/feed off` stops the daily run.

## If it stops working

- Nothing arrives: `on` is false, the hour has not come, it is past 23:00, or the day had nothing worth sending. Send `/feed` to test.
- `The feed could not be put together: ...`: the text after it is the cause.
- `Not read: X posts (<group>): ...`: that group failed, for example `no OpenRouter key is set up for X posts` or the daily cap was reached.
- By hand, sending nothing: `python3 context/feed.py`. It prints the message and the cost. Add `--save` to record it.
