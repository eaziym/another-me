# Security

another-me reads your private messages and can act in your name in a few narrow ways. This page lists who can tell it
what to do, the guards in code, and what those guards do not cover.

## Who can instruct it

| Who | Can instruct | Can do |
|---|---|---|
| You, typing in your private Telegram chat with the bot, or your WeChat chat with yourself | The agent, and the commands | Everything below |
| Your own voice notes there | The agent | Ask and be answered. A transcript cannot keep a note, forget one, stop a job, show the screen or skip a WeChat draft |
| The agent on your phone | | Read every set-up source; write a job that waits for your ok; send WeChat under the rules below; save a note under the note rules |
| A job | | Run commands in one project folder, after your ok to its exact prompt |
| The group bot's model | | Write one reply for its own group; read that group and public data |
| Anyone else's text: messages, pages, captions, files, forwarded messages | Nobody | Be read and quoted |

The Telegram bot answers only your account, in a private chat. Messages from anyone else are ignored. On WeChat
only what you type in your chat with yourself counts.

## Guards in code

- **Read-only by default.** Every source is read-only except WeChat sending. RedNote's `rednote_ask` types one
  question into RedNote's own assistant; nothing likes, follows, comments, posts or messages.
- **The agent has no shell.** It runs with Claude Code's `--restricted` flag and a fixed tool list: this project's
  tools, `Read` limited to the files you attach, and web search on Claude. Any new ability is added as a tool with
  its own guard.
- **WeChat sending** ([wechat.py](../context/wechat.py)).
  - Each tool uses the narrowest daemon token: read, send or media, never the owner token.
  - A message goes out without a draft only to a chat on your allowlist, and only when your own message in that turn
    asks for a send (`ASKS_TO_SEND`), does not turn it down (`SAYS_NOT_TO_SEND`), and names that chat (`_named`).
  - Everything else is a numbered draft in your chat with yourself, sent only when you reply ok.
  - No tool can change the allowlist. Only your typed `/allow` and `/disallow` can.
  - No tool can write in your chat with yourself, so no tool can post its own ok.
- **Jobs** ([jobs.py](../context/jobs.py)). A job never starts on the agent's say-so. You see the exact prompt and
  reply ok. The agent may stop a job only in a turn where your message speaks of stopping.
- **Notes** ([memory.py](../context/memory.py)). A note is fed into every later conversation, so:
  - Passwords, keys, codes and card numbers are refused.
  - A note waits for your `/keep` if it is sensitive or reads like a standing order. It also waits unless every one of
    its distinctive words is in what you stated in that turn; questions, quotes and forwarded text don't count.
  - The agent may forget a note only when your message asks for it and points at that note.
- **Screen captures** are sent only to your own Telegram chat, and only in a turn where your message asked to see
  the screen.
- **The group bot** reads only its own group, through tools fixed to that group in code. It has none of your notes,
  no other chat and no RedNote. It sends nothing itself: the script posts its reply.
- **Secrets** live in `~/.config/anotherme/` (tokens, allowlist, drafts, memory, logs), never in the repository. Keep
  that folder `chmod 700`.

## What these guards do not cover

- **The checks read words.** "Did you send it?" can count as asking for a send. A chat can be named by accident
  ("Al" in a sentence about Al). An allowlisted chat then gets a message without a draft. Keep the allowlist short.
- **Text you paste without quote marks counts as your own words** for the note and send checks.
- **A job runs real commands** in auto permission mode. Read the prompt before you say ok. On a local model its
  commands can still reach the network.
- **The model can be wrong or misled.** Text it reads can push it toward a bad summary or a bad draft. The guards
  limit what it can do on its own; they do not make what it says true.
- **Your Mac is the boundary.** Anyone who can use your Mac account can read `~/.config/anotherme/` and the apps
  themselves.
- **Unofficial clients and automation.** WeChat and RedNote accounts can be restricted. See each app's page.

## Reporting a problem

If you find a way around one of these guards, please report it privately through GitHub's "Report a vulnerability"
on this repository rather than in a public issue.
