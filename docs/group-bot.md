# WeChat group bot

A small background program that answers in one WeChat group when someone calls it. It uses your WeChat account, so its messages come from you, each starting with a robot sign.

It is separate from the agent you talk to on your phone. It has fewer tools and reads only its own group.

The code: [`wechat_bot.py`](../context/wechat_bot.py) (the responder), [`wechat_group_history.py`](../context/wechat_group_history.py) (the only tools its model gets) and [`group_memory.py`](../context/group_memory.py) (its notes). It needs the WeChat setup in [WeChat](apps/wechat.md).

## How it is called

It checks the group every few seconds against the local `wx` daemon. That costs nothing and uses no model. A model runs only when a message:

- says "Claude" or "克劳德" in text, or
- quotes one of the bot's own messages, or
- is a voice note that says the name. The voice note is turned into text on your Mac first (no model). Because speech recognition often hears "Claude" as "Cloud", a note also counts if it opens with a sound-alike such as "Hi Cloud".

After a call it waits a few seconds (up to 30) in case the caller is still typing. Then it answers with one short message, in the group's language and tone.

Mute and unmute are text only:

- "Claude 闭嘴", "Claude 安静", "Claude shut up", "Claude mute" mute it. It posts a short line, stops answering, and sends you a note in your file-transfer chat.
- "Claude 回来", "Claude unmute" or "Claude come back" bring it back.

Anyone in the group can do this. Text inside a forwarded record or a shared link's title does not count.

## What its model can and cannot do

Its model (Claude Haiku by default) gets web search, `Read`, and the tools in `GROUP_TOOLS`, and nothing else:

- `group_history`, `group_members`: older messages and the member list of this one group. The group is fixed in code when the bot starts. There is no argument the model can change to read another chat.
- `group_media`: fetches a photo, voice note, video, sticker or file, or one item inside a forwarded record. It works only with a short code that is first found among this group's own stored messages. Voice notes and videos come back as a machine transcript.
- `group_remember`, `group_forget`: this group's own notes (below).
- Public lookups: `nba_games`, `nba_ratings`, `nba_table`, `hupu_search` ([Hupu](apps/hupu.md)), `stock_quote`, `crypto_quote` ([markets](apps/markets.md)), `game_odds`, `market_odds`, `market_history`, `web_page` ([web pages](apps/web-pages.md)), `youtube_transcript` ([YouTube](apps/youtube.md)) and `x_posts` ([X](apps/x.md)).

It cannot: read any other chat, send anything itself (the script posts its text), see your notes, use RedNote, run commands, or read files other than what `group_media` just fetched. Messages and pages it reads are treated as information, not instructions.

Other limits:

- It posts only while the group is on your send allowlist (see [WeChat](apps/wechat.md)). Take it off with `/disallow` to switch the bot off.
- X posts count against a small daily budget for the whole group (`xposts.DAILY_USD["group"]`, $0.25), at most 6 posts per call. Nothing a member says raises it.
- Each model call has a spend cap of $0.30 (not applied with a local model) and about 4.5 minutes.
- Each call is fresh. It sees about 4000 characters of recent chat, and says how much older chat exists.
- Media is fetched into a new temporary folder made for that one call and deleted after it. A later call cannot open what an earlier one fetched.

## Its own notes

When someone asks it to remember something, or settles what someone is called, it saves a short note (up to 200 characters; all notes up to 3000). Every later call is shown them. They are in `~/.config/anotherme/wechat-bot-notes-<group id>.json`, apart from your own notes, and only this group's bot sees them. Who asked is written by code from the messages that called it, never by the model. A note you asked for can be changed or dropped only in a call you are part of. Passwords and codes are refused. Print them with `python3 context/group_memory.py <group id>`.

## Start it

1. Find the group's id. List chats and look for the one ending in `@chatroom`:

   ```
   python3 context/server.py wechat_chats '{"limit": 100}'
   ```

2. Put the group on your send allowlist: send `/allow <group name>` to the agent (see [WeChat](apps/wechat.md)).
3. Install and start the service:

   ```
   scripts/install-service.sh group-bot <group chat id>
   ```

4. Restart it after you change code or settings it uses. It exits with a message if the id is not a group.

Try it without posting:

```
ANOTHERME_BOT_TRIAL=1 /usr/bin/python3 context/wechat_bot.py <group id> --answer-last
```

This answers the group's newest message for real and prints the reply instead of posting. Its X lookups count against your own budget, not the group's. Notes it would save go to a copy.

## Tell the group

Members' messages are read by a model when they call it: Claude by default, run through Claude Code and sent to Anthropic, together with recent chat from that group and anything it fetches (photos, voice transcripts, pages). If you set `local_model` in `~/.config/anotherme/config.json` (see [models](models.md)), the model runs on your Mac, with no web search. Say so in the group before you turn it on, and how to mute it.

## Cost

Idle cost is zero. Each answer is one small model call, capped at $0.30. X lookups are the main extra cost, capped per day as above. `~/.config/anotherme/wechat-bot-log.jsonl` has one line per call (time, cost, outcome, no chat text).

## If it stops working

- `cannot read WeChat: ...` (in the service log): the `wx` daemon is stopped or signed out. See [WeChat](apps/wechat.md). It keeps retrying.
- `<name> is not a group; this bot answers in one group only`: use the group's `@chatroom` id.
- `several chats match: ...`: use the id, not the name.
- It answers in a trial but not in the group: the group is not on the allowlist (`group is not on the send allowlist` in the log), or it is muted.
