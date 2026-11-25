# Memory: search and notes

Two things live here: a searchable copy of your messages, and short notes about you that the agent reads at the start of every conversation.

- "What did Mia say about the invoice?" (any chat, any app)
- "Who is 'Sam W' on WeChat?"
- "Remember that the Orion project lives in ~/dev/orion."

The code is [`context/memory.py`](../context/memory.py). The store is one SQLite file, `~/.config/anotherme/memory.db`, readable by you only.

## Search your messages

- `memory_search`: finds messages containing every word you give, in the text, chat name or sender, newest first. Arguments: `query`, and optionally `sources` (`wechat,whatsapp,telegram`), `chat`, `days`, `limit` (default 50, max 300). Chinese and short words work.
- `people_find`: finds a person or group by any name: your remark for them, their nickname, their WeChat ID, or part of one. It returns the id to use with the other tools.

WeChat (through the `wx` daemon) and WhatsApp (its local database) are copied into the store, only what is new, each time a search runs. Telegram is searched live through your own Telegram login and is not copied. WeChat history starts when the daemon first signed in; the result tells you the start date. Searching needs those sources set up: see [WeChat](apps/wechat.md), [WhatsApp](apps/whatsapp.md) and [Telegram](apps/telegram.md). A source that cannot be read is reported in `problems`, and the others are still searched.

No model is used for search.

## Notes

Notes are short facts (up to 500 characters) about you, your people and your projects. Kept notes are put at the start of every new conversation, newest first, up to 3000 characters.

The agent saves a note with `memory_save` when you tell it something lasting. The rules, enforced in code (`SECRET`, `SENSITIVE`, `grounded`):

- Passwords, keys, codes and card numbers are refused.
- A harmless note is kept at once, and you are shown it with `/forget <number>` to take it back.
- A note waits for your `/keep` if it touches health, money, legal, family or similar private matters; if it reads like a standing order ("always", "never", "every day", "without asking", "send...", "approve..."); if the agent marked it sensitive; or if it cannot be traced to your words. Traced means every one of its names and distinctive words appears in what you stated in your message that turn. Questions don't count ("does Alice live in London?" states nothing), and neither does text you quote, forwarded text or earlier messages.
- A note only comes from what you said, never from what the agent read in a chat, page or file.

Commands (only from your own typed messages; no model sees them):

- `/notes`: list notes with numbers. Waiting ones are marked.
- `/keep`: keep every note that is waiting. `/keep4`, `/keep 4`, `/keep 6-14, 20`: keep those.
- Without the slash, "rmb them", "keep all" or "keep 6-14" work, but only while a note is waiting; otherwise they are ordinary words for the agent.
- `/forget 4` or `/forget 6-9` (or the tappable `/forget4`): delete. `/forget` needs numbers.

The agent can delete a note (`memory_forget`) only when your own message, in that turn, asks for it and points at that note, by its number or by one of its own words. "Forget the gym note" can remove a note about the gym; "is this score wrong?" removes nothing. `entry.py` checks for words such as forget, remove, delete, drop, wrong, outdated, no longer, and 忘, 删, 不对 (`ASKS_TO_FORGET`). Otherwise the agent tells you which note looks wrong and that `/forget` removes it.

## The daily look at what you typed

About once every 20 hours, between 09:00 and 23:00, the entry service reads what you typed to the agent in the last day and the prompts you typed yourself in your Claude Code sessions. It sends them, with the notes already saved, to Sonnet with no tools, and proposes up to five notes. Prompts written by programs (jobs, helper runs) are left out. Each proposal goes through the same rules as above, and you are told what was kept and what waits for `/keep`.

It is skipped on a day with less than about 300 characters to read. The call is capped at $0.50 (a few cents in practice). Try it by hand: `python3 context/memory.py learn --dry`.

Your typed messages to the agent are kept in `~/.config/anotherme/owner-said.jsonl` for this purpose, with each cut to 2000 characters.

## Privacy and cost

By default the agent's model is Claude through Claude Code, so whatever a tool returns, your notes, and what the daily look reads are sent to Anthropic as part of the conversation. Search results can hold messages from many chats.

With `local_model` set in `~/.config/anotherme/config.json` (see [models](models.md)), all of it stays on your Mac, and the daily look costs nothing.

Search, notes and commands cost nothing. Only the daily look uses a model.

## If it stops working

- `query is empty`: give at least one word.
- `Nothing matched`: the note in the result explains: try fewer words, or `people_find`. WeChat messages before the start date are not on this Mac.
- `problems` lists a source that could not be read, for example `telegram: not searched: ...` when the Telegram login is missing.
- A note that never appears: it is waiting. Check `/notes` and send `/keep`.
- `Nothing was saved: notes are not a place for passwords...`: the text looked like a secret.
- By hand: `python3 context/memory.py search "invoice"`, `ingest`, `notes`.
