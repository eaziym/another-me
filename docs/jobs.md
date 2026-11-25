# Jobs: hand work to a coding session

From your phone you can ask the agent to get real work done in one of your project folders. It hands the task to a Claude Code or Codex session on your Mac. The job never starts until you have seen the exact prompt and replied `ok`.

- "In the web-shop project, fix the failing login test."
- "Ask Codex to review the diff in notes-app. It may use the network."
- "Continue session 3f9c2a10 in the web-shop project and finish the migration."

The code is in [`context/jobs.py`](../context/jobs.py); the cards and commands are in [`context/handlers.py`](../context/handlers.py) and [`context/entry.py`](../context/entry.py).

## How a job goes

1. You ask. The agent writes a complete, self-contained brief and calls `session_send`. That call only writes the job down as `waiting_ok`. It starts nothing.
2. Your phone gets a job card with the folder, the model, and the exact prompt, ending "Reply ok to run it, no to cancel."
3. You reply on its own: `ok`, `ok 12`, `ok to both`, `ok all` (when several wait), or `no` / `no 12` to cancel. The reply is handled by code and never reaches the model, so an agent cannot say ok for you. It can also be an ok replying to the card.
4. The job runs in its own process. Its result is sent to you when it ends.

A job you do not answer expires after 30 minutes. A prompt is at most 3000 characters, so you can read all of it before you say ok.

## Who it runs as

- Claude Code (default): `claude -p` in the project folder in `auto` permission mode, so it can edit files and run commands there, with that project's instructions, memory and tools. Models: `sonnet` (default), `opus`, `fable`. Haiku is not offered.
- Codex: `codex exec`, with a workspace-write sandbox. It may change files in the project folder; network is off unless the job was created with network on, and the card says which. Codex runs on the model set in your own Codex settings, so the prompt does not say a model.

Jobs run in a folder under your home directory: a folder name under `~/dev`, or a full path. `~/.config/anotherme` is refused because it holds this system's tokens and records. Jobs look for Claude Code at `~/.local/bin/claude` and Codex at `~/.local/codex-cli/node_modules/.bin/codex`.

Every job is first told that it runs unattended, that it must check the agent's account of a cause rather than trust it, to follow the project's own rules, to try its work on the real path, to run the project's review script if there is one, to commit finished work locally and never push, and to end with a short summary.

## Limits

- Time: 45 minutes, or 90 on Opus. The job is told its deadline. At the limit it is asked to stop (SIGINT, so Claude Code closes with its cost and session id), reported with the last thing it said, and its processes are ended.
- Spend (Claude Code): `--max-budget-usd` of $10, or $15 on Opus and Fable. Hitting it ends the job with whatever it said last. With a local model there is no spend cap, because Claude Code would price your model as Claude.
- Commands run in the foreground, because a job is one run with no later turn.

## Continue an existing session

Give the session id (or its first characters, at least 8) and the same project folder. Find ids with `sessions_recent` (see [coding sessions](apps/coding-sessions.md)).

- Claude Code: the job's turns are added to that session's own transcript, so you find them there. If the session was written to in the last 10 minutes, or another job is using it, the job runs in a copy instead.
- Codex: a thread is continued in place only, and only while idle. If it is in use, the job stays waiting and you are told to say ok again later.

The card warns you when a Claude Code session carries more than about 50k tokens (a long session costs more to reload) or a Codex thread is over 20 MB.

## Watch it, stop it

- A status message in your Telegram chat is rewritten in place while the job runs: minutes, steps, and what it is doing now. `/jobs` shows the same for running jobs and the last few others. Commands that look like keys or tokens are shortened to `…`.
- If a job shows no step for ten minutes, you are told once. A single long command can look like this.
- `/stop` ends the one job that is running or waiting. If several are, it asks which; `/stop 12` names one. Waiting jobs are cancelled, running ones are ended.
- The agent can stop a job (`session_stop`) only in a turn where your own message spoke of stopping (`ASKS_TO_STOP` in `entry.py`: for example "stop it", "cancel job 12"). Otherwise it tells you to send `/stop`.
- `session_jobs` lets the agent read job states and results.

## Privacy and cost

By default a Claude Code job runs on Claude through Claude Code, so what it reads and writes in the project goes to Anthropic. With `local_model` set in `~/.config/anotherme/config.json` (see [models](models.md)), Claude Code jobs go to your local model instead, with no spend cap. On a local model a job also gets only this project's tool server (none of your other MCP connectors) and no WebSearch or WebFetch, so the model's tools don't carry the project's text off the Mac. The job's own commands can still use the network, as any program you run can. You see the exact prompt before you say ok.

Codex jobs go to OpenAI whatever `local_model` says.

Jobs cost money only while they run, and only the ones you approved. The prompt can include chat text the agent read; check the card before you say ok.

## If it stops working

- `no project folder 'x' under ~/dev`: the error lists close names. Use a folder name under `~/dev` or a full path in your home folder.
- `no Claude Code session ... in <project>`: the id is unknown, shorter than 8 characters, or belongs to another project. Only a session of the same project and tool can be continued.
- `Job N not started: ...`: for example a Codex thread in use. Say ok again later.
- `It ended without reporting: its process is gone`: the Mac restarted or the runner crashed.
- `Claude Code gave no result` or `Codex gave no result`: read the text after it. `Codex stopped: ...` carries Codex's own error.
- Job records and logs are in `~/.config/anotherme/jobs/` (`<n>.json`, `<n>.log`, `<n>.live`). `python3 context/jobs.py` prints the list.
- Set `ANOTHERME_JOBS_DIR` to a throwaway folder to try jobs without reporting them to your phone.
