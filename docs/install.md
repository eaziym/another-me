# Install

This takes an afternoon the first time. You can stop after any step: each app works on its own, and the agent says
what is missing when it tries one that is not set up.

## 1. What you need

- A Mac. It has been run on Apple silicon with a recent macOS.
- The system Python, `/usr/bin/python3`, which comes with Apple's command line tools: `xcode-select --install`. The
  services always use this one, by full path. Their packages are installed for it, and a Homebrew Python that comes
  first on your PATH will not see them.
- [Homebrew](https://brew.sh) for a few tools (ffmpeg, yt-dlp, poppler).
- Claude Code, installed with its native installer so it is at `~/.local/bin/claude`. Sign in once by running
  `claude`. To use a model on your Mac instead, see [models.md](models.md). Claude Code is still the harness.
- Codex, only if you want Codex jobs.

## 2. Get the code

```bash
git clone https://github.com/eaziym/another-me ~/another-me
cd ~/another-me
mkdir -p ~/.config/anotherme && chmod 700 ~/.config/anotherme
```

`~/.config/anotherme/` holds everything personal: tokens, the send allowlist, drafts, job records, the memory
database and logs. It is never inside the repository.

Optional: copy [`config.example.json`](../config.example.json) to `~/.config/anotherme/config.json` and keep only the
settings you want.

## 3. Let your own Claude Code sessions use the tools

```bash
claude mcp add --scope user anotherme-context -- /usr/bin/python3 ~/another-me/context/server.py
claude mcp get anotherme-context
```

Any Claude Code session can now read your apps through these tools. Run one tool by hand to check:

```bash
python3 context/server.py apps_running '{}'
```

## 4. Set up the apps you want

Each page says what to install, what to grant and how to test it:

- Messages: [WeChat](apps/wechat.md) (needs the [another-me-wechat](https://github.com/eaziym/another-me-wechat)
  daemon), [Telegram](apps/telegram.md), [WhatsApp](apps/whatsapp.md)
- On the Mac: [Chrome](apps/chrome.md), [any app](apps/any-app.md), [the screen](apps/screen.md),
  [Claude Code and Codex sessions](apps/coding-sessions.md), [voice](apps/voice.md)
- Online: [RedNote](apps/rednote.md), [X](apps/x.md), [YouTube](apps/youtube.md), [Hupu](apps/hupu.md),
  [markets](apps/markets.md), [web pages](apps/web-pages.md)

## 5. The agent on your phone

1. Create the Telegram bot and save its token and your id ([phone.md](phone.md)).
2. Give the agent its own copy of Claude Code, so macOS permissions stick:
   ```bash
   mkdir -p ~/.config/anotherme/bin
   cp ~/.local/bin/claude ~/.config/anotherme/bin/claude-bot
   ```
   macOS holds the program that runs the agent responsible for what its tools read. The installed Claude Code moves
   with every update; this copy stays put. If you use WhatsApp, give this file Full Disk Access now (System Settings
   → Privacy & Security → Full Disk Access → +, then press Cmd-Shift-G and type the path). Other permissions are asked
   for the first time a tool needs them, and the agent tells you on your phone when a dialog is waiting.
3. Start the service:
   ```bash
   scripts/install-service.sh entry
   ```
4. Send your bot a message.

## 6. Optional services

```bash
scripts/install-service.sh rednote-browser          # after: python3 context/rednote.py login
scripts/install-service.sh group-bot 12345@chatroom  # one WeChat group; see docs/group-bot.md
```

`scripts/install-service.sh --print <service>` shows the launchd file without installing it.
`scripts/install-service.sh --remove <service>` stops and removes one. The daily feed runs inside the entry service:
see [apps/feed.md](apps/feed.md).

## Updating

```bash
cd ~/another-me && git pull
launchctl kickstart -k gui/$(id -u)/dev.anotherme.entry      # and any other service you installed
```

A service keeps running the code it started with until it is restarted. After updating Claude Code, refresh the
agent's copy with a rename, so a call in progress keeps the old file:

```bash
cd ~/.config/anotherme/bin && cp ~/.local/bin/claude claude-bot.new && mv claude-bot.new claude-bot
```

Then check that WhatsApp still reads. If macOS dropped the grant, give Full Disk Access to the new copy.

## Tests

```bash
cd context
/usr/bin/python3 -m unittest test_wechat test_memory test_entry test_hupu test_markets test_webpage test_youtube test_rednote test_xposts test_odds test_pdfread
```

They need no daemon, network or model, and change nothing in `~/.config/anotherme/`.

## Uninstall

```bash
scripts/install-service.sh --remove entry          # and each other service you installed
claude mcp remove anotherme-context
rm -rf ~/.config/anotherme                         # tokens, allowlist, notes, logs: everything it kept
```
