# Coding sessions

Ask the agent what your Claude Code and Codex sessions are working on, or what was said in one.

- "What are my coding sessions doing right now?"
- "What was I asking Claude Code in the web-shop project this morning?"
- "Show me the last few turns of that Codex session."

To hand work to a session, see [jobs](../jobs.md).

## How it connects

The tools are `sessions_recent` and `session_read` in [`context/server.py`](../../context/server.py). They read the transcript files the two programs already keep on your Mac. Nothing is installed in either program.

- Claude Code: `~/.claude/projects/<project folder>/<session id>.jsonl`, one folder per project.
- Codex: `~/.codex/sessions/.../<file>.jsonl`.

## Set it up

Nothing to set up. If you use Claude Code or Codex, the files are there. Try it:

```
python3 context/server.py sessions_recent '{"limit": 5}'
python3 context/server.py session_read '{"session": "3f9c2a10"}'
```

## What it can and cannot do

`sessions_recent` lists the most recently active sessions of both tools, newest first. Each entry has the tool, the project, the session id, the last active time and your last few messages in it (each cut to 400 characters). Arguments: `project` (only projects whose folder contains this), `tool` (`claude-code` or `codex`; default both), `limit` (default 8) and `messages` (default 3).

`session_read` returns the last turns of one session, by id or by the first characters of the id: your messages and the assistant's text, without tool output. Arguments: `turns` (default 10) and `max_chars_each` (default 1500).

Both are read-only. They do not resume, write to or stop a session.

For a Codex session, the project is the folder it was started in. Only the most recent Codex files are searched, so a very old Codex session may not show.

## Privacy and cost

By default the agent's model is Claude through Claude Code, so whatever a tool returns is sent to Anthropic as part of the conversation. Sessions can contain code, file contents you pasted and anything you typed.

If you set `local_model` in `~/.config/anotherme/config.json` (see [models](../models.md)), it stays on your Mac.

Nothing here costs money by itself.

## If it stops working

- `no session matches '<id>'`: the id is wrong or the file is gone. Run `sessions_recent` and copy the id.
- An empty list: no transcripts in the folders above, or `project` or `tool` filtered everything out.
- Messages that look cut off: they are capped (400 characters in the list, 1500 per turn in `session_read`). Raise `max_chars_each`.
- Try one: `python3 context/server.py sessions_recent '{"tool": "codex"}'`
