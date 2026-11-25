# Screen

Ask the agent for a picture or a short recording of your Mac's screen, sent to your phone.

- "Screenshot my screen."
- "Record my screen for 15 seconds."
- "What is on my screen right now?"

## How it connects

The tools are `screen_capture` and `screen_record` in [`context/server.py`](../../context/server.py). They use macOS's `screencapture`.

- `screen_capture` takes a picture of one display, shrinks it to at most 2200 pixels on the long side, and saves it as a JPEG. The agent can open the file to look at it.
- `screen_record` records 1 to 30 seconds (default 10). The agent cannot watch a recording; it can only say that one was made.
- `display` picks the display (1 is the main one, the default).

Files are saved with owner-only permissions in `~/.config/anotherme/entry-cwd/inbox`. The entry service removes files there that are more than a week old when it starts.

## Set it up

1. Run a capture once: `python3 context/server.py screen_capture '{}'`.
2. The first time, macOS shows a prompt and lists the program in System Settings. Open System Settings → Privacy & Security → Screen & System Audio Recording and switch it on for the Python or Terminal entry that appears. For use from your phone, that is the Python that the entry service runs.
3. Ask again.

## What it can and cannot do

It only looks. Nothing is clicked or typed.

The picture goes to your phone only under these rules:

- Only your own Telegram chat receives it. The server holds no Telegram token; it writes a request down, and `entry.py` uploads it. Nothing is sent to WeChat, to another chat, or anywhere else. If you asked over WeChat, the picture still goes to your Telegram chat and the reply says so.
- Only in a turn where your own message asked to see the screen. `entry.py` checks your message against `ASKS_TO_SEE` (words like "screenshot", "my screen", "record my screen", and the Chinese 截图, 屏幕, 录屏). Text you quote or forward does not count. If your message did not ask, the tool answers "Not sent" and the file stays on the Mac.
- Only files the screen tools made, for that turn, are sent.
- Run outside the phone agent, a capture is never sent.

The agent can look at a picture itself (it opens the file) when it needs to answer "what is on my screen". That picture goes to the model, not to your chat.

## Privacy and cost

By default the agent's model is Claude through Claude Code, so a picture the agent opens is sent to Anthropic as part of the conversation. A recording is not opened by the agent, but it is uploaded to Telegram. Your screen can show anything; close what you would not want seen.

If you set `local_model` in `~/.config/anotherme/config.json` (see [models](../models.md)), the model must be able to read images to describe a picture; the picture stays on your Mac, apart from the Telegram upload.

Nothing here costs money by itself.

## If it stops working

- `macOS has not allowed screen capture for the program I run under...`: do step 2 above, then ask again.
- `the capture produced no file`: the screen was not captured, often because of a missing permission or a locked screen.
- `Not sent: a capture is sent only when the owner asks in their own message to see the screen.`: ask in plain words, for example "screenshot my screen".
- `Not sent: only the owner's phone agent can send it to them.`: you ran the tool by hand. The file path is in the result.
- Try one: `python3 context/server.py screen_capture '{}'`
