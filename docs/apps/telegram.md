# Telegram

There are two separate things here. This page is about the first one.

1. Reading your Telegram chats as you. Examples: "Summarise what happened in my team group today", "Find the last message from Alice about the flight", "What is in my Saved Messages?"
2. The Telegram bot you use to talk to the agent. That is covered in [phone.md](../phone.md).

You do not need one to use the other.

## How it connects

The agent signs in to Telegram as you, with a user session made by [Telethon](https://docs.telethon.dev). It uses your own API id and hash from my.telegram.org. It lists chats and reads messages. It never sends and does not mark messages as read. The tools are `telegram_chats` and `telegram_read`, in [server.py](../../context/server.py).

## Set it up

1. Install Telethon for the system Python that runs the agent:
   ```
   /usr/bin/python3 -m pip install --user telethon
   ```
2. Sign in. Run this in a terminal:
   ```
   python3 context/server.py telegram-login
   ```
   It asks for an `api_id` and `api_hash`. Make an app at https://my.telegram.org (API development tools) and paste its two values. Then Telegram asks for your phone number, the login code and your password if you have one.
3. This creates a folder `~/.config/anotherme/telegram/` with a `.env` file (your API id and hash) and the session. Both are readable only by you.
4. If you already have a Telethon login made elsewhere, you can point to it instead. In `~/.config/anotherme/config.json` set:
   ```
   {"telegram_dir": "~/path/to/that/folder"}
   ```
   The folder needs a `.env` with `TG_API_ID` and `TG_API_HASH`, and a session named `.tg_chatsumm`.
5. Test:
   ```
   python3 context/server.py telegram_chats '{"limit": 5}'
   ```

## What it can and cannot do

- `telegram_chats`: recent chats with name, id, kind (dm, group, channel), unread count and last activity.
- `telegram_read`: messages from one chat, oldest first, with sender and time. Arguments: `chat` (name, part of a name, or id), `limit` (default 50), `hours`. Use `chat` = `saved` for Saved Messages. If several chats match, they are listed and nothing is guessed. Only your 200 most recent chats are searched by name.
- Media shows as a placeholder such as `[photo]`. The agent does not fetch it.
- It never sends, edits or deletes. It does not mark messages as read.

## Privacy and cost

- The Mac talks to Telegram as you, as any Telegram client does. Nothing goes to another service from this app.
- By default the agent's model is Claude through Claude Code. Whatever a tool returns, which here is chat names and message text, is sent to Anthropic as part of the conversation. With `local_model` set in `~/.config/anotherme/config.json` (see [models.md](../models.md)), it stays on the Mac.
- No cost from this app.

## Risks

- The session file gives full access to your Telegram account. Keep `~/.config/anotherme/telegram/` private. Anyone who has it can act as you. You can end the session in Telegram under Settings → Devices.
- The code only reads. The session itself is not limited, though.

## If it stops working

Try one tool by hand: `python3 context/server.py telegram_chats '{"limit": 5}'`.

- `Telegram is not set up on this Mac; run python3 context/server.py telegram-login`: no `.env` yet. Run the login.
- `Telegram is not signed in on this Mac; run python3 context/server.py telegram-login`: the session is missing or ended. Run the login again.
- `TG_API_ID / TG_API_HASH not found in .../.env`: fix the `.env` file.
- `no Telegram chat matches ...`: use the chat's exact name or id.
- An error about `telethon` not found: run the pip command in step 1 for `/usr/bin/python3`.
