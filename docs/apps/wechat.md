# WeChat

You can ask the agent to read your WeChat chats, open pictures, voice notes and videos in them, and send messages for you. Examples: "What did Alice say in the last two hours?", "What does the voice note from Bob say?", "Tell 小王 I will be ten minutes late."

This is the only app where the agent can write. Reading is open. Sending is guarded (see below).

## How it connects

WeChat has no public API. The agent talks to a small local program, the `wx` daemon, which signs in to WeChat as you and listens on `127.0.0.1:6174`. The daemon is a separate project: [another-me-wechat](https://github.com/eaziym/another-me-wechat). Its README has the full build and login steps.

The agent uses three tokens, each with one scope, so a tool can only do what its token allows:

| Token file (in `~/.config/anotherme/`) | Scope | Used for |
| --- | --- | --- |
| `wechat-token` | read | `wechat_chats`, `wechat_read` |
| `wechat-send-token` | send | `wechat_send`, drafts and approvals |
| `wechat-media-token` | media | `wechat_media` (picture, voice and video bytes) |

The code never uses an owner-level token.

## Set it up

1. Build and start the daemon. See the [fork's README](https://github.com/eaziym/another-me-wechat) for the exact build command, then:
   ```
   wx daemon start
   ```
2. Sign in to WeChat on the daemon. Scan the QR code with your phone:
   ```
   wx auth login
   ```
3. Create the three tokens. Each command prints its token once:
   ```
   wx tokens create another-me-read  --accounts '*' --scopes read
   wx tokens create another-me-send  --accounts '*' --scopes send
   wx tokens create another-me-media --accounts '*' --scopes media
   ```
4. Save each token to its file and make it private:
   ```
   mkdir -p ~/.config/anotherme && chmod 700 ~/.config/anotherme
   # paste each token into its file (wechat-token, wechat-send-token, wechat-media-token), then:
   chmod 600 ~/.config/anotherme/wechat-token ~/.config/anotherme/wechat-send-token ~/.config/anotherme/wechat-media-token
   ```
5. Test a read:
   ```
   python3 context/server.py wechat_chats '{"limit": 5}'
   ```
6. To drive the agent from your own WeChat chat, see [phone.md](../phone.md).

You can skip the media token if you never need attachments. Reading and sending still work.

## What it can and cannot do

Reading (read-only; nothing is sent or marked as read):

- `wechat_chats`: lists recent chats with name, id, group or direct, unread count, last activity and a preview.
- `wechat_read`: reads one chat, oldest first. Arguments: `chat`, `limit` (up to 300), `hours`, `search`. A chat is found by whole id, then whole name, then part of a name. If several match, they are listed and nothing is guessed.
- History starts when the daemon first signed in. Older messages are only on your phone.
- A photo, voice note, video, sticker or file shows as a bracketed kind such as `[image]` with an `id`.

Media:

- `wechat_media` fetches one attachment onto the Mac so the agent can open it. It waits up to 90 seconds for a download.
- For a voice note or video it also returns a transcript, made on the Mac. See [voice.md](voice.md).
- A forwarded chat record (合并转发) shows each inner picture, video or file as `[image item=N]`, `[video item=N]` or `[file item=N]`. Give `wechat_media` the record's `id` and `item=N` to fetch one. Without `item`, it lists the items and fetches nothing.
- Some stickers cannot be fetched. The tool says so.

Sending (text only, up to 1,500 characters):

- `wechat_send` sends one text message. Unless the chat is on your allowlist, it first posts a numbered draft in your own WeChat chat (the chat with yourself):
  ```
  📝 Draft #3
  To: Alice (direct chat)
  ...
  Reply ok to send, no to cancel, or say what to change.
  ```
- Reply `ok` (also `yes`, `好`, `可以`, `发吧` and similar), or `ok 3` for a specific draft. Reply `no` (or `不`, `取消`) to cancel. Any other text is read as a change request: nothing is sent, and the agent revises the draft and posts a new one that needs a fresh ok.
- You can answer by quoting the draft card. An answer counts only for a draft that is still waiting and only after its card.
- A draft expires after 60 minutes.
- `wechat_pending` reads your answers, sends approved drafts, drops refused or expired ones and lists those still waiting. The entry agent picks up your ok on its own.
- Your own chat is never a send destination. A tool that could write there could post its own "ok".

The allowlist:

- A chat on the allowlist skips the draft only when your own message, in that turn, both asks for a message to be sent and names that chat. "Tell Alice I'm late" goes straight to Alice if Alice is on the list. "Summarise this page and send it to the group" becomes a draft, and so does "don't send anything". The checks are word matches: `ASKS_TO_SEND` and `SAYS_NOT_TO_SEND` in [entry.py](../../context/entry.py), and `_named` in [wechat.py](../../context/wechat.py). A chat is named by one of its names whole, or by a word of three or more letters from one ("mira" for Mira Chen). A Chinese name counts only whole. Words you quote don't count. In any other case the send becomes a draft, because the text or the choice of chat may have come from something the agent read.
- When you use `wechat_send` from a terminal, outside the entry agent, an allowlisted chat goes straight out.
- At most 30 unapproved (allowlist) sends per hour. After that, drafts are used again.
- Each allowlist send shows a macOS notification with the text.
- Only you change the list, by typing a command to the agent from your private Telegram chat or your own WeChat chat:
  - `/allow` shows the list.
  - `/allow Alice` adds a chat by its whole name or id.
  - `/disallow Alice` removes it.
  - If a name is partial or shared, the agent offers each match as its own command (`/allow7`). A loose match never adds a chat.
  - No model, voice note or forwarded message can run these. Your own chat cannot be on the list.
- In a terminal: `python3 context/server.py --wechat-allow <chat>`, `--wechat-disallow <chat>`, `--wechat-allowlist`.

The allowlist is `~/.config/anotherme/wechat-send-allowlist.json`. Pending drafts are in `wechat-send-pending.json`. `wechat-send-log.jsonl` records the time, chat and approval of each send, never the text.

Not covered: sending pictures or files, reading WeChat Moments, changing chats in WeChat.

## Privacy and cost

- Everything runs on your Mac. The daemon talks to WeChat's servers as you do. Nothing is sent to any other service by this app.
- By default the agent's model is Claude through Claude Code. Whatever a tool returns, such as messages, transcripts and media you ask it to open, is sent to Anthropic as part of the conversation. With `local_model` set in `~/.config/anotherme/config.json` (see [models.md](../models.md)), it stays on the Mac.
- Transcripts are made locally. There is no cost from this app itself.
- Messages from other people are treated as data. They are not instructions to the agent.

## Risks

> [!WARNING]
> The `wx` daemon is an unofficial WeChat client. WeChat's terms do not allow third-party clients. Your account can be restricted or banned. A spare account is safer. Using it is your choice and risk.

- Sending is the one place the agent writes. Keep the allowlist short. A chat on it can receive a message without a draft whenever you ask for one to be sent.

## If it stops working

Try one tool by hand: `python3 context/server.py wechat_chats '{"limit": 5}'`.

- `no WeChat token at <path>`: create the token and save it to that file. For media the message names the `media` scope.
- `WeChat daemon is not reachable at ...; start it with wx daemon start`: start the daemon.
- `WeChat is not signed in on the daemon; run wx auth login`: sign in again.
- `WeChat daemon answered <code> ...`: the daemon refused the call. Read its log with `wx daemon logs`.
- `no WeChat chat or contact matches ...`: use the whole name or the chat id.
- `the user's chat with themselves is reserved for approving drafts`: you or the agent asked to send to your own chat. Send to someone else. For notes to yourself the message points to File Transfer (`filehelper`).
- `could not post the draft to the user's own chat for approval`: the send token is missing or the daemon could not send. Check `wechat-send-token`.
- `text is empty` or `text is N characters; the limit is 1500`: shorten the message.
- A draft is stuck: ask the agent to check pending drafts, or wait. It expires after 60 minutes.
- `outcome not confirmed; read the chat before sending again`: look at the chat before retrying.
