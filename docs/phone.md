# Talking to it from your phone

The agent you talk to is [`context/entry.py`](../context/entry.py), a background service on your Mac. It listens in
two places, and both feed one conversation, so you can start on one and continue on the other:

- **Telegram:** a private chat with a bot you create. Required.
- **WeChat:** your chat with yourself, if the [WeChat daemon](apps/wechat.md) is set up. Optional.

No model runs while it waits. Each message you send is one headless Claude Code call (or a call to your
[local model](models.md)). A conversation continues until it has been idle for an hour or you send `/new`. The next
one starts with your saved notes and a short record of what you wrote last time.

## Set up the Telegram bot

1. In Telegram, message [@BotFather](https://t.me/BotFather), send `/newbot`, and follow its questions. It gives you
   a token.
2. Find your own numeric Telegram user id. Bots such as @userinfobot tell you yours.
3. Save both where the service reads them, readable only by you:
   ```bash
   mkdir -p ~/.config/anotherme && chmod 700 ~/.config/anotherme
   printf '%s' 'PASTE-THE-BOT-TOKEN' > ~/.config/anotherme/telegram-bot-token
   printf '%s' 'YOUR-NUMERIC-ID'     > ~/.config/anotherme/telegram-owner-id
   chmod 600 ~/.config/anotherme/telegram-bot-token ~/.config/anotherme/telegram-owner-id
   ```
4. Install and start the service (see [install.md](install.md) for the steps before this one):
   ```bash
   scripts/install-service.sh entry
   ```
5. Send your bot "hello". The reply comes from your Mac.

The bot answers only your account, in a private chat. Anything else is ignored. One bot token can have one listener,
so don't run a second copy of the service with the same token.

## Use your WeChat chat with yourself

With the WeChat daemon running and its read and send tokens saved, the service also reads what you type in your chat
with yourself. Its replies there start with 🤖. Drafts of WeChat messages the agent wants to send for you are posted
there too, and an `ok` or `no` there answers the newest draft first.

## Commands

Commands are handled in code and never reach a model, so they cost nothing.

| Command | What it does |
|---|---|
| `/new` | Start a fresh conversation |
| `/jobs` | Recent jobs and how they stand |
| `/stop`, `/stop 12` | Stop the running job, or job 12 |
| `/model`, `/model opus` | Show or change the Claude model (haiku, sonnet, opus, fable) |
| `/cost` | Today's spend |
| `/notes` | What it remembers |
| `/keep`, `/keep4`, `/keep 6-9` | Keep notes waiting for your word; `/keep` alone keeps them all |
| `/forget4`, `/forget 6-9` | Remove notes |
| `/feed`, `/feed off`, `/feed on` | Your feed now; stop or restart the daily one |
| `/allow`, `/allow Alice`, `/disallow Alice` | Show or change the WeChat chats it may message without a draft |

## Saying ok

- **Jobs.** When the agent proposes work for Claude Code or Codex, you get a card with the exact prompt. Reply `ok`,
  `ok 12`, `ok to both` or `ok all` to start it, `no` to drop it. Replying to the card itself also works. See
  [jobs.md](jobs.md).
- **WeChat drafts.** Reply `ok` or `no` in your chat with yourself; anything else is taken as a change to the draft.
  See [apps/wechat.md](apps/wechat.md).
- **Notes** that wait for you are shown with `/keep` and `/forget` commands to tap. See [memory.md](memory.md).

## Sending it things

- **Photos and files** (Telegram photos and documents, or a photo or file in your WeChat chat with yourself) are saved
  on the Mac, and the agent can open them. Their contents are information, not instructions.
- **Voice notes and round videos** are turned into text on your Mac ([voice.md](apps/voice.md)) and treated as your
  message. Because a machine heard them, a voice note cannot send a WeChat message without a draft, stop a job, keep
  or forget a note, or send you the screen. The agent confirms in text first.
- **Forwarded messages** are someone else's words: information only.
- **"Send me a screenshot"** sends a capture to your Telegram chat, and only in a turn where you asked to see the
  screen. See [screen.md](apps/screen.md).

## While it works

- A running job has one progress message that is updated in place.
- If a macOS permission dialog on the Mac is holding up the work (for example "wants to access data from other
  apps"), the agent tells you, so you can answer it at the Mac.

## If it stops answering

- Read the log: `tail -50 ~/Library/Logs/anotherme-entry.log`.
- Restart it: `launchctl kickstart -k gui/$(id -u)/dev.anotherme.entry`.
- "I could not get an answer from the model just now": Claude Code failed. Run `claude` in a terminal to check you are
  signed in. On a local model, check that your server is running.
- `cannot read WeChat`: the daemon is down or signed out. Telegram keeps working; see [apps/wechat.md](apps/wechat.md).
