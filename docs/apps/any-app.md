# Any app

Ask the agent what is on screen in an app that has no tool of its own: which apps are open, and the text in an app's windows.

- "What apps are running?"
- "What does the Slack window say right now?"
- "Read the open Terminal and tell me what the error is."

## How it connects

The tools are `apps_running` and `app_text` in [`context/server.py`](../../context/server.py). They call a small Swift program, [`context/native/ax_text.swift`](../../context/native/ax_text.swift), which reads the text of each window through macOS Accessibility. It only reads. It never clicks or types, and it skips password fields.

The server compiles the program with `swiftc` into `context/bin/ax_text` the first time you use it, and again whenever the source file is newer.

## Set it up

1. Install the Xcode command line tools, which provide `swiftc`: `xcode-select --install`.
2. Grant Accessibility to the program that runs the server. This is whatever macOS names in the prompt or in the list: the Python that the entry service runs (`/usr/bin/python3`) when you use the agent from your phone, or Terminal when you run a tool by hand. Open System Settings → Privacy & Security → Accessibility and switch it on.
3. Try it:

```
python3 context/server.py apps_running '{}'
python3 context/server.py app_text '{"app": "Slack"}'
```

## What it can and cannot do

- `apps_running` lists apps with a window (name, bundle id, and which one is in front). Background-only programs are not listed.
- `app_text` takes `app` (a name or bundle id; part of a name works), and optionally `window` (only windows whose title contains this), `max_chars` per window (default 20000) and `offset`.
- Many apps work: editors, Slack, Terminal, Finder, Office. Apps built on Chromium or Electron publish their content only when asked, so the helper switches that on for about three seconds when it finds little text, then switches it off.
- Some apps expose no text. The result then says `this app exposes no text through Accessibility`. Use `screen_capture` instead (see [screen](screen.md)).
- It reads at most about 20,000 interface elements per app; `truncated` is true if it stopped early.
- The Mac must be awake and unlocked. A locked or sleeping Mac shows no windows to read.
- For WeChat, use the WeChat tools, not this one.

## Privacy and cost

By default the agent's model is Claude through Claude Code, so whatever a tool returns is sent to Anthropic as part of the conversation. A window can hold mail, messages and documents. Text on screen that other people wrote is treated as information, not as instructions.

If you set `local_model` in `~/.config/anotherme/config.json` (see [models](../models.md)), it stays on your Mac.

Nothing here costs money by itself.

## If it stops working

- `Accessibility permission is not granted to the app running this tool`: switch the program on in System Settings → Privacy & Security → Accessibility, then try again.
- `no running app matches <name>`: the app is not running, or has no window. Run `apps_running` to see the exact name.
- `swiftc` not found, or a compile error on first use: install the command line tools (step 1). Delete `context/bin/ax_text` to force a rebuild.
- Empty windows: the Mac is locked, the app is minimised on another Space, or the app exposes no text.
- Try one tool by hand: `python3 context/server.py app_text '{"app": "Finder"}'`.
