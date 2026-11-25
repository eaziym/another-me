#!/usr/bin/env python3
"""Jobs: work handed to a Claude Code session on this Mac, started only after the owner says ok.

A job is one headless Claude Code run in a project folder (`claude -p`, auto permission mode), so it
has that project's instructions, memory and tools, and can edit files and run commands there. It
starts a fresh session unless it is told to continue one, in which case its turns are added to that
session's own transcript (or to a copy, when the session was in use minutes ago).

A job can run Codex instead (`codex exec`, its workspace-write sandbox: it may change files in the
project folder only, with no network unless the job says so). It can continue a Codex thread, in
place only: Codex has no way to copy a thread from the command line, so a thread that is in use is
left alone and the job waits.

Because a job can run commands, it never starts on an agent's say-so. session_send only writes the
job down as "waiting_ok". The entry point (entry.py) shows the owner the exact prompt, and starts
the job when the owner replies ok. This file never starts a job by itself except through start(),
which entry.py calls after that ok.

States: waiting_ok -> running -> done | failed | stopped;  waiting_ok -> cancelled | expired
"""
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

import server                           # server.model_call: the owner's name for a model -> the model it means now

HOME = os.path.expanduser("~")
HERE = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.environ.get("ANOTHERME_JOBS_DIR") or os.path.join(HOME, ".config", "anotherme", "jobs")   # the variable is for trial runs:
#                                                          a job written to the real folder is reported to the owner's phone
SESSIONS = os.path.join(HOME, ".claude", "projects")   # Claude Code's transcripts, one folder per project
CLAUDE = os.path.join(HOME, ".local", "bin", "claude")
CODEX = next((p for p in (os.path.join(HOME, ".local", "codex-cli", "node_modules", ".bin", "codex"), "/opt/homebrew/bin/codex",
                           "/usr/local/bin/codex", os.path.join(HOME, ".local", "bin", "codex")) if os.path.exists(p)),
             shutil.which("codex") or "codex")          # where Codex is: its own folder here; Homebrew or npm elsewhere
CODEX_SESSIONS = os.path.join(HOME, ".codex", "sessions")
# What a job's PATH starts with: a launchd job has only the system folders. Codex is a node script (Homebrew), and
# ~/.local/bin holds `codex-review`, the review every project's rules ask for: job 37 could not find it (2026-11-23).
# The folder of `codex` itself is on it too: job 74 ran a bare `codex exec` and got "command not found" (2026-11-25).
JOB_PATH = "/opt/homebrew/bin:/usr/local/bin:%s:%s:" % (os.path.join(HOME, ".local", "bin"), os.path.dirname(CODEX))
MODELS = ("sonnet", "opus", "fable")     # the owner's names; the command line gets server.model_call(name)["model"]. Haiku is left out:
#                                          it could not run in auto permission mode when tried
DEFAULT_MODEL = "sonnet"
# The owner's choice, 2026-11-25: $5 ended jobs 72, 74 and 78 before they finished (an engine fix took three jobs).
MAX_USD = "10.00"
LONG_USD = {"opus": "15.00", "fable": "15.00"}
TIMEOUT_MINUTES = 45
LONG_MINUTES = {"opus": 90}              # the owner's choice, 2026-11-23: two Opus jobs that day were ended at 45, half done
LONGEST_MINUTES = max([TIMEOUT_MINUTES] + list(LONG_MINUTES.values()))
STOP_SECONDS = 20                        # how long a run out of time is given to close after it is asked to
OK_WAIT_MINUTES = 30                     # an unanswered job is dropped after this
BUSY_MINUTES = 10                        # a session written to this recently is continued in a copy, not in place
# What every job is told before its task. The second and third paragraphs are what three jobs got wrong on
# 2026-11-22: one answered from memory that a model did not exist; one changed a running service, reported that no
# restart was needed and left the old code answering, slept thirteen minutes on a refusal that was not a rate limit,
# and left its work uncommitted in the next job's way; and each task's guess at the cause was taken as the cause.
PREFACE = ("This task was sent by the owner from their phone through anotherme. You are running without anyone "
           "watching: nobody can answer questions or approve prompts, so make reasonable choices and finish what "
           "you can. This is one run with no later turn: nothing wakes you once you stop, so run every command in the "
           "foreground and wait for it, and do not end while something you started is still running. "
           "Do not push, deploy, send messages or delete data unless the task says to.\n\n"
           "The task below was written by an agent that cannot see this folder, from what the owner said on their "
           "phone. What the owner wants is the task; the agent's account of the cause is a guess, so check it against "
           "the code and the running system before acting on it. Look up names, versions and model ids (the code, the "
           "tool's own help, the web) instead of answering from memory: yours ends before today. When a service "
           "refuses or limits you, find out why or try another way; do not sleep for minutes hoping it clears.\n\n"
           "Before you call the work done:\n"
           "1. Keep the rules in the project's CLAUDE.md. Where the task and a rule disagree, keep the rule and say so.\n"
           "2. Use what you changed the way the owner will, on the real path with sending turned off. Passing unit "
           "tests are not that check.\n"
           "3. If the project has a review script, run it and fix what would break the next use.\n"
           "4. Only then: if a program that is already running had loaded code you changed, it is still running the "
           "old code. Restart it the way the project says and check it came back. If the task says to leave the "
           "change off, or the review says it should not go live, or you cannot restart it, leave it and say so in "
           "the first line of your summary.\n"
           "5. If the folder is a git repository, commit the work you finished there, never push, so the next job "
           "starts from a clean folder. Commit only files you changed. Leave unfinished work uncommitted and say "
           "which files.\n\n"
           "End with a short plain-text summary: first whether it is done and live; then what you checked against the "
           "real thing and what you did not; then anything the owner has to decide. That last message is all the owner "
           "receives.\n\n")
# A job is told how long it has: jobs 34 and 35 were not, and were ended mid-command with nothing committed or said.
LIMIT = ("Time: this run is ended %d minutes after it started (%s), finished or not, whatever it is doing then. `date` "
         "tells you the time. Do the part that matters most first, check the time before a long step, and with ten "
         "minutes left start nothing new: commit what is finished and write the summary, saying what is left.\n\nTask:\n")
# A headless run ends with its last message. A command moved to the background (as any command over two minutes
# was) left job 10 saying "I'll wait for the notification" as its whole result, with its review killed half way.
FOREGROUND = {"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1", "BASH_DEFAULT_TIMEOUT_MS": "900000", "BASH_MAX_TIMEOUT_MS": "1800000"}


def minutes(job):
    """How long this job may run."""
    return LONG_MINUTES.get(job.get("model"), TIMEOUT_MINUTES)


def max_usd(job):
    """How much this job may spend, in dollars, as the command line takes it."""
    return LONG_USD.get(job.get("model"), MAX_USD)


def task(job):
    """What the run is given on standard input: the rules for every job, its time limit, then the task."""
    return PREFACE + LIMIT % (minutes(job), time.strftime("%H:%M", time.localtime(job.get("started") or time.time()))) + job["prompt"]


def _path(n):
    return os.path.join(JOBS_DIR, "%d.json" % n)


def save(job):
    os.makedirs(JOBS_DIR, mode=0o700, exist_ok=True)
    fd = os.open(_path(job["n"]) + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(job, f, ensure_ascii=False, indent=1)
    os.replace(_path(job["n"]) + ".tmp", _path(job["n"]))
    return job


def load(n):
    with open(_path(int(n))) as f:
        return json.load(f)


def all_jobs():
    if not os.path.isdir(JOBS_DIR):
        return []
    out = []
    for name in os.listdir(JOBS_DIR):
        if name.endswith(".json"):
            with open(os.path.join(JOBS_DIR, name)) as f:
                out.append(json.load(f))
    return sorted(out, key=lambda j: j["n"])


def projects_root():
    """Where project folders are looked for by name: config.json's projects_dir, else ~/dev."""
    return os.path.expanduser(server.config().get("projects_dir") or os.path.join(HOME, "dev"))


def project_dir(name):
    """A project folder from a path or a folder name in projects_root(). Raises with close names when there is none."""
    name = str(name).strip()
    root = projects_root()
    for cand in (os.path.expanduser(name), os.path.join(root, name)):
        if os.path.isabs(cand) and os.path.isdir(cand) and os.path.realpath(cand).startswith(HOME + os.sep):
            if (os.path.realpath(cand) + os.sep).startswith(os.path.realpath(os.path.join(HOME, ".config", "anotherme")) + os.sep):
                raise RuntimeError("%s holds this system's own tokens, allowlist and job records; no job runs there" % cand)
            return os.path.realpath(cand)
    near = sorted(d for d in (os.listdir(root) if os.path.isdir(root) else []) if name.lower() in d.lower())[:10]
    raise RuntimeError("no project folder %r in %s%s" % (name, root, "; close names: " + ", ".join(near) if near else ""))


def session_info(sid, project):
    """The Claude Code session `sid` (its id, or the first characters of it) of this project folder: its full
    id, transcript, when it was last written to, and roughly how many tokens of context it carries."""
    sid = str(sid).strip()
    folder = os.path.join(SESSIONS, re.sub(r"[^A-Za-z0-9]", "-", project))

    def matches(d):
        return [f for f in os.listdir(d) if f.endswith(".jsonl") and f.startswith(sid)] if os.path.isdir(d) else []
    names = matches(folder) if len(sid) >= 8 else []
    if len(names) != 1:
        others = [d for d in (os.listdir(SESSIONS) if os.path.isdir(SESSIONS) and len(sid) >= 8 else [])
                  if d != os.path.basename(folder) and matches(os.path.join(SESSIONS, d))]
        raise RuntimeError("no Claude Code session %r in %s%s. Only a Claude Code session of the same project can be continued."
                           % (sid, project, "; it belongs to another project (%s), so pass that project" % ", ".join(others) if others else ""))
    path = os.path.join(folder, names[0])
    tokens = None
    with open(path, "rb") as f:                       # the last model call records how much context it read
        f.seek(max(0, os.path.getsize(path) - 2000000))
        for line in f.read().decode("utf-8", "ignore").splitlines():
            try:
                usage = (json.loads(line).get("message") or {}).get("usage")
            except (ValueError, AttributeError):
                continue
            if usage:
                tokens = sum(usage.get(k) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return {"id": names[0][:-6], "path": path, "last_used": os.path.getmtime(path), "tokens": tokens}


def codex_session_info(sid, project):
    """The Codex thread `sid` (its id, or the first characters of it) started in this project folder: its full id,
    file, when it was last written to, and its size."""
    sid, found = str(sid).strip().lower(), []
    for base, _, names in os.walk(CODEX_SESSIONS) if len(sid) >= 8 else []:
        found += [os.path.join(base, f) for f in names if f.endswith(".jsonl") and f[-42:-6].startswith(sid)]
    if len(found) != 1:
        raise RuntimeError("no Codex thread %r%s" % (sid, " (%d match)" % len(found) if found else ""))
    with open(found[0], encoding="utf-8", errors="ignore") as f:
        try:
            meta = json.loads(f.readline()).get("payload") or {}
        except ValueError:
            meta = {}
    if os.path.realpath(meta.get("cwd") or "/nowhere") != project:
        raise RuntimeError("Codex thread %s belongs to %s, not %s; pass that project" % (sid, meta.get("cwd") or "an unknown folder", project))
    return {"id": found[0][-42:-6], "path": found[0], "last_used": os.path.getmtime(found[0]), "megabytes": round(os.path.getsize(found[0]) / 1e6, 1)}


def create(project, prompt, model=None, resume=None, tool=None, network=False):
    prompt = str(prompt or "").strip()
    if not prompt:
        raise RuntimeError("prompt is empty")
    if len(prompt) > 3000:
        raise RuntimeError("prompt is %d characters; the limit is 3000 so the owner can read all of it before saying ok" % len(prompt))
    tool = (tool or "claude").lower()
    if tool not in ("claude", "codex"):
        raise RuntimeError("tool must be claude or codex")
    if tool == "codex":
        if model:
            raise RuntimeError("a Codex job runs on the model set in the owner's Codex settings; leave model out")
        model = "codex"
    else:
        model = (model or DEFAULT_MODEL).lower()
        if model not in MODELS:
            raise RuntimeError("model must be one of %s" % ", ".join(MODELS))
    job = {"state": "waiting_ok", "project": project_dir(project), "prompt": prompt, "model": model, "tool": tool, "resume": None,
           "network": bool(network) and tool == "codex", "created": time.time(), "announced": False, "reported": False}
    if resume and tool == "codex":
        info = codex_session_info(resume, job["project"])
        job.update(resume=info["id"], resume_last_used=info["last_used"], resume_megabytes=info["megabytes"])
    elif resume:
        info = session_info(resume, job["project"])
        job.update(resume=info["id"], resume_last_used=info["last_used"], resume_tokens=info["tokens"])
    with _locked():                    # two agents asking at once must not be given the same number
        job["n"] = max([j["n"] for j in all_jobs()] + [0]) + 1
        return save(job)


def change(n, expect=None, **fields):
    """Set fields on a job in one step, under the jobs lock, so two programs never write over each other's news.
    With `expect`, nothing is changed unless the job is still in that state; the job comes back either way."""
    with _locked():
        job = load(n)
        if expect is None or job["state"] == expect:
            job.update(fields)
            save(job)
        return job


class _locked:
    def __enter__(self):
        os.makedirs(JOBS_DIR, mode=0o700, exist_ok=True)
        self.f = open(os.path.join(JOBS_DIR, ".lock"), "w")
        fcntl.flock(self.f, fcntl.LOCK_EX)

    def __exit__(self, *exc):
        self.f.close()


def start(job):
    """Run the job in a process of its own, so it outlives whoever started it. Call only after the owner's ok."""
    with _locked():
        job = load(job["n"])
        if job["state"] != "waiting_ok":   # someone else started, cancelled or expired it first
            raise RuntimeError("job %d is %s, not waiting for an ok" % (job["n"], job["state"]))
        copy = None
        if job.get("resume"):
            # In place, so the work shows up in the session the owner knows. Two writers would tangle a transcript,
            # so a session that was written to minutes ago (open and in use), or that another job is working in,
            # is continued in a copy instead. A Codex thread cannot be copied from here, so that job is not started.
            taken = any(j["state"] == "running" and j.get("resume") == job["resume"] and not j.get("copy") for j in all_jobs())
            info = codex_session_info(job["resume"], job["project"]) if job.get("tool") == "codex" else session_info(job["resume"], job["project"])
            copy = taken or time.time() - info["last_used"] < BUSY_MINUTES * 60
            if copy and job.get("tool") == "codex":
                raise RuntimeError("Codex thread %s %s. Two writers would tangle it, so job %d is still waiting: say ok again when the thread is idle"
                                   % (job["resume"][:8], "has another job working in it" if taken else "was in use in the last %d minutes" % BUSY_MINUTES, job["n"]))
        job.update(state="running", started=time.time(), copy=copy)
        save(job)
    try:
        with open(os.path.join(JOBS_DIR, "%d.log" % job["n"]), "w") as log:
            subprocess.Popen([sys.executable, os.path.abspath(__file__), "run", str(job["n"])], stdout=log, stderr=log,
                             stdin=subprocess.DEVNULL, start_new_session=True, cwd=HERE)
    except OSError as e:
        return change(job["n"], expect="running", state="failed", finished=time.time(), result="Could not start it: %s" % e)
    return job


def run(n):
    """The body of a running job: one headless Claude Code call in the project folder."""
    try:
        return _run(n)
    except Exception as e:             # whatever goes wrong, the job must not be left looking as if it still runs
        return change(n, expect="running", state="failed", finished=time.time(), result="The job runner failed: %s" % e)


def _command_for(job, last, call=None):
    """The program and arguments for a job. The task itself goes in on standard input. `call` is the settings read
    for this run (server.model_call), so its command and its environment agree on the backend."""
    if job.get("tool") == "codex":
        # Spelled out in full, so the job has what its card says and nothing the owner's own Codex settings would add.
        sandbox = ["-c", 'sandbox_mode="workspace-write"', "-c", "sandbox_workspace_write.writable_roots=[]",
                   "-c", "sandbox_workspace_write.network_access=%s" % ("true" if job.get("network") else "false")]
        cmd = [CODEX, "exec"] + (["resume"] if job.get("resume") else []) + sandbox + ["--skip-git-repo-check", "--json", "-o", last]
        return cmd + ([job["resume"]] if job.get("resume") else []) + ["-"]
    call = call or server.model_call(job["model"], max_usd(job))
    cmd = [CLAUDE, "-p", "--model", call["model"], "--permission-mode", "auto", "--output-format", "stream-json", "--verbose",   # a line per step: see _step
           *call["budget"]]
    if call["local"]:
        # On this Mac's own model a job gets this project's tool server and none of the owner's other connectors, and no
        # web tools: those would carry the project's text off the Mac. Its commands can still reach the network, as
        # any program the owner runs can; the card shows the prompt they say ok to.
        cmd += ["--strict-mcp-config", "--mcp-config", json.dumps({"mcpServers": {"anotherme-context": {
                    "command": "/usr/bin/python3", "args": [os.path.join(HERE, "server.py")]}}}), "--disallowedTools", "WebSearch,WebFetch"]
    if job.get("resume"):
        cmd += ["--resume", job["resume"]] + (["--fork-session"] if job.get("copy", True) else [])
    return cmd


def _outcome(job, out, err, last, code=0, cut=None):
    """What a finished run amounts to, as fields for the job. `cut`: why the runner ended it, when it did; such a
    run is failed, and reported with that reason and the last thing it said."""
    if job.get("tool") == "codex":
        events = []
        for line in out.split("\n"):
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        events = [e for e in events if isinstance(e, dict)]
        thread = next((e.get("thread_id") for e in events if e.get("type") == "thread.started"), None)
        said = [e["item"].get("text") or "" for e in events if e.get("type") == "item.completed" and (e.get("item") or {}).get("type") == "agent_message"]
        failed = [str(e.get("message") or (e.get("error") or {}).get("message") or e)[:300] for e in events if e.get("type") in ("error", "turn.failed")]
        try:
            with open(last) as f:
                result = f.read().strip()
        except FileNotFoundError:
            result = ""
        result = result or (said[-1].strip() if said else "")
        ended = code == 0 and any(e.get("type") == "turn.completed" for e in events)   # else "Looking..." would pass for a result
        if cut:
            return dict(state="failed", session=thread, result="%s. %s" % (cut, "The last it said:\n\n" + result if result else "It had said nothing yet."))
        if failed or not result or not ended:
            return dict(state="failed", session=thread, result=("Codex stopped: " + failed[-1]) if failed else
                        "Codex stopped before finishing. The last it said: %s" % result[:400] if result else
                        "Codex gave no result: %s" % ((err or out).strip()[-400:] or "no output"))
        return dict(state="done", session=thread, result=result)
    d, said = None, ""
    for line in out.split("\n"):       # the closing record is the last line that says "result"; not splitlines, which
        try:                           # also breaks at separators JSON may carry inside a string
            e = json.loads(line)
        except ValueError:
            continue
        if not isinstance(e, dict):
            continue
        if e.get("type") == "result":
            d = e
        elif e.get("type") == "assistant" and not e.get("parent_tool_use_id") and isinstance(e.get("message"), dict):
            texts = [b.get("text") or "" for b in e["message"].get("content") or [] if isinstance(b, dict) and b.get("type") == "text"]
            said = "\n\n".join(t.strip() for t in texts if t.strip()) or said
    last_said = "The last it said:\n\n" + said if said else "It had said nothing yet."
    if d is None:
        return dict(state="failed", result="%s. %s" % (cut, last_said) if cut else
                    "Claude Code gave no result: %s" % ((err or out).strip()[-400:] or "no output"))
    result = (d.get("result") or "").strip()
    if cut or not result:
        # A run stopped by its spending limit closes without a summary, though the job has usually just written one
        # (job 14 did, and the owner was sent "(no summary)" for five dollars of work).
        why = cut or {"error_max_budget_usd": "It reached its $%s spending limit" % max_usd(job), "error_max_turns": "It reached its limit of turns"}.get(
            d.get("subtype"), "It stopped without a summary (%s)" % (d.get("subtype") or "no reason given"))
        result = "%s. %s" % (why, last_said)
    return dict(state="failed" if cut or d.get("is_error") else "done", result=result,
                usd=d.get("total_cost_usd") if job.get("backend", "claude") in ("claude", "codex") else 0,   # a local model costs nothing
                turns=d.get("num_turns"), session=d.get("session_id"),
                denied=[x.get("tool_name") for x in d.get("permission_denials") or []])


def _live_path(n):
    return os.path.join(JOBS_DIR, "%d.live" % int(n))


def live(n):
    """What a running job is doing, as its runner last wrote it down: {"at", "steps", "now", "since", "session"}.
    Empty when nothing was written."""
    try:
        with open(_live_path(n)) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


SECRET_LOOKING = re.compile(r"(?i)((?:bearer|token|secret|password|passwd|api[-_]?key|authorization)[\"']?\s*[=: ]\s*[\"']?(?:bearer\s+)?)\S+|[A-Za-z0-9_\-+/]{32,}")


def _doing(name, args):
    """A tool call in a few words: the tool and the command, file or purpose it was given. It is shown in the
    owner's chat, so anything that looks like a key or token in a command is left out."""
    args = args if isinstance(args, dict) else {}
    what = args.get("description") or args.get("command") or args.get("file_path") or args.get("pattern") or args.get("query") or args.get("prompt") or ""
    if args.get("file_path"):
        what = os.path.basename(str(what))
    what = SECRET_LOOKING.sub(lambda m: (m.group(1) or "") + "…", " ".join(str(what).split()))
    return ("%s: %s" % (name, what[:90])).rstrip(": ")


def _step(seen, line, codex=False):
    """Take one line of the run's output into `seen`, the job's live state. Returns True when something changed.
    Calls made together end one by one: `seen["open"]` holds those still running, so the first to come back does not
    turn a command that is still going into "thinking" (job 37 showed that for a quarter of an hour of tests)."""
    try:
        e = json.loads(line)
    except ValueError:
        return False
    if not isinstance(e, dict):
        return False
    now = time.time()
    seen["at"] = now
    doing = None
    if codex:
        item = e.get("item") if isinstance(e.get("item"), dict) else {}
        if e.get("type") == "thread.started":
            seen["session"] = e.get("thread_id")
        elif e.get("type") == "item.started":
            doing = _doing(item.get("type") or "step", {"command": item.get("command") or item.get("text") or item.get("query")})
            seen["steps"] = seen.get("steps", 0) + 1
        elif e.get("type") == "item.completed":
            doing = "thinking"
    else:
        seen["session"] = e.get("session_id") or seen.get("session")
        blocks = (e.get("message") or {}).get("content") if isinstance(e.get("message"), dict) else None
        blocks = [b for b in blocks or [] if isinstance(b, dict)] if isinstance(blocks, list) else []
        if e.get("parent_tool_use_id"):
            pass                       # a helper it started is at work: alive, but what the job itself is doing stays as it was
        elif e.get("type") == "assistant":
            for b in blocks:
                if b.get("type") == "tool_use":
                    doing = _doing(b.get("name") or "tool", b.get("input"))
                    seen["steps"] = seen.get("steps", 0) + 1
                    if b.get("id"):
                        seen.setdefault("open", {})[b["id"]] = [doing, now]
                elif b.get("type") == "text" and (b.get("text") or "").strip() and not doing:
                    doing = "writing"
        elif e.get("type") == "user" and any(b.get("type") == "tool_result" for b in blocks):
            still = seen.get("open") or {}
            for b in blocks:
                still.pop(b.get("tool_use_id"), None)
            if still:                  # back to the newest call still running, and to when that one began
                seen["now"], seen["since"] = list(still.values())[-1]
                return True
            doing = "thinking"
    if doing and doing != seen.get("now"):
        seen["now"], seen["since"] = doing, now
    return True


def _write_live(n, seen):
    fd = os.open(_live_path(n) + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(seen, f, ensure_ascii=False)
    os.replace(_live_path(n) + ".tmp", _live_path(n))


def _held_elsewhere(job, call):
    """The model another job held the session this one continues on, when that is not this run's: a session held
    on this Mac's own model is not handed, transcript and all, to Anthropic (or the other way) by a later job."""
    if not call or not job.get("resume"):
        return None
    other = {j.get("backend") for j in all_jobs() if j.get("session") == job["resume"] and j["n"] != job["n"]} - {None, "codex", call["backend"]}
    return sorted(other)[0] if other else None


def _run(n):
    last = os.path.join(JOBS_DIR, "%d.last" % n)       # where Codex writes its final message
    job = load(n)
    if job.get("tool") != "codex" and job.get("resume"):
        elsewhere = _held_elsewhere(job, server.model_call(job["model"], max_usd(job)))
        if elsewhere:
            return change(n, expect="running", state="failed", finished=time.time(),
                          result="It continues a session that ran on %s, and the models are set differently now, so it did not "
                                 "start. Start a fresh session for this work, or switch the model setting back." % elsewhere)
    with _locked():                    # together with stop(): either it sees our pids, or we see that it stopped the job
        job = load(n)
        if job["state"] != "running":
            return job
        call = None if job.get("tool") == "codex" else server.model_call(job["model"], max_usd(job))   # read once for this run
        p = subprocess.Popen(_command_for(job, last, call), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             cwd=job["project"], env=dict({k: v for k, v in (call["env"] if call else os.environ).items()
                                                           if k != "CODEX_HOME"},   # threads were looked up in ~/.codex
                                                          PATH=JOB_PATH + os.environ.get("PATH", "/usr/bin:/bin"), **FOREGROUND))
        job.update(pid=p.pid, pid_started=_started(p.pid), runner=os.getpid(), backend=call["backend"] if call else "codex")
        save(job)
    # The run prints a line per step. Each is noted as it comes, so the owner can see what the job is doing and
    # how long ago it last did anything, and all of them are kept for the outcome.
    lines, errors, seen = [], [], {"at": time.time(), "steps": 0, "now": "starting", "since": time.time()}

    def follow():
        for line in p.stdout:
            lines.append(line)
            try:
                if _step(seen, line, job.get("tool") == "codex"):
                    _write_live(n, seen)
            except Exception:
                pass                   # the status is a courtesy; reading the run to its end is not

    try:
        _write_live(n, seen)
    except OSError:
        pass
    readers = [threading.Thread(target=follow, daemon=True), threading.Thread(target=lambda: errors.append(p.stderr.read()), daemon=True)]
    for r in readers:
        r.start()
    try:
        p.stdin.write(task(job))
        p.stdin.close()
    except OSError:
        pass                           # it ended before reading the task: the outcome below says why
    try:
        p.wait(timeout=minutes(job) * 60)
        for r in readers:
            r.join(5)                  # the output of a run that has ended; not for as long as a command it left behind holds the pipe
        out, err = "".join(lines), "".join(errors)
    except subprocess.TimeoutExpired:
        # It is asked to stop first: an interrupted Claude Code closes with its cost, turns and session (under a
        # second on 2.1.330). That is waited for briefly and nothing else is: a command the call started may hold its
        # output open for as long as it likes. Then the outcome is saved, with the last thing the run said, and the
        # runner leads the job's process group (see start), so the group is ended, the command and this runner with it.
        try:
            p.send_signal(signal.SIGINT)
            p.wait(timeout=STOP_SECONDS)
            readers[0].join(5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        cut = "It was stopped at its %d-minute limit, unfinished" % minutes(job)
        try:
            fields = _outcome(job, "".join(list(lines)), "", last, 1, cut=cut)
        except Exception:              # whatever its output holds, the job is closed and its processes are ended
            fields = dict(state="failed", result=cut + ".")
        if not fields.get("session") and seen.get("session"):
            fields["session"] = seen["session"]    # where the work is, so it can be continued
        try:
            job = change(n, expect="running", finished=time.time(), **fields)
        finally:
            p.kill()
            if os.getpgrp() == os.getpid():
                os.killpg(os.getpid(), signal.SIGTERM)
        return job
    return change(n, expect="running", finished=time.time(), **_outcome(job, out, err, last, p.returncode))   # a stopped job keeps saying stopped


def stop(n, **also):
    """Cancel a waiting job or end a running one. A job that has already ended is returned unchanged."""
    with _locked():
        job = load(n)
        if job["state"] == "waiting_ok":
            job.update(also, state="cancelled", finished=time.time())
        elif job["state"] == "running":
            job.update(also, state="stopped", finished=time.time(), result="Stopped before it finished.")
            _kill(job)
        else:
            return job
        return save(job)


def _command(pid):
    return subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout if pid else ""


def _started(pid):
    return subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True).stdout.strip() if pid else ""


def _claude_alive(job):
    """Whether the job's own Claude Code or Codex call still runs: the same program, started at the same moment.
    A pid alone proves nothing, since pids are reused."""
    program = "codex" if job.get("tool") == "codex" else CLAUDE
    return bool(job.get("pid_started")) and program in _command(job.get("pid")) and job["pid_started"] == _started(job["pid"])


def _runner_alive(job):
    return bool(job.get("runner")) and bool(re.search(r"jobs\.py run %d\s*$" % job["n"], _command(job["runner"])))


def alive(job):
    """Whether a running job still has its runner or its Claude Code call. With neither (a restart, a crash)
    it will never report."""
    return _runner_alive(job) or _claude_alive(job)


def _kill(job):
    """End a running job and whatever it started. The runner leads its own process group (see start), so the
    group is signalled. Pids get reused, so nothing is signalled unless it still is this job's runner or its
    Claude Code call."""
    try:
        if _runner_alive(job):
            os.killpg(job["runner"], signal.SIGTERM)
        elif _claude_alive(job):
            os.kill(job["pid"], signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


def brief(job):
    out = {"job": job["n"], "state": job["state"], "project": os.path.basename(job["project"]), "tool": job.get("tool", "claude"),
           "model": job["model"], "prompt": job["prompt"][:200]}
    if job.get("started"):
        out["minutes"] = round(((job.get("finished") or time.time()) - job["started"]) / 60, 1)
    seen = live(job["n"]) if job["state"] == "running" else {}
    if job["state"] == "running":
        out["minutes_allowed"] = minutes(job)
    if seen:                           # so "how is job 13" is answered from what it is doing, not from a guess
        out.update(steps_so_far=seen.get("steps", 0), doing_now=seen.get("now"),
                   doing_that_for_seconds=int(time.time() - seen.get("since", seen["at"])), seconds_since_last_sign_of_life=int(time.time() - seen["at"]))
    if job.get("resume"):
        out["continues_session"] = job["resume"]
    for k in ("result", "usd", "session", "denied"):
        if job.get(k):
            out[k] = job[k]
    return out


# ---------------------------------------------------------------- tools for the context server

def session_send(args):
    job = create(args["project"], args.get("prompt"), args.get("model"), args.get("resume"), args.get("tool"), args.get("network"))
    return {"job": job["n"], "state": "waiting_ok", "project": job["project"],
            "note": "Not started. The owner is shown this exact prompt and the job runs only after they reply ok. "
                    "Its result is sent to them when it finishes; session_jobs shows it too. Do not send it again."}


def session_stop(args):
    # The entry agent reads other people's messages, so it may stop a job only in a turn where the owner's own
    # message spoke of stopping. entry.py sets ANOTHERME_MAY_STOP for exactly those turns.
    if os.environ.get("ANOTHERME_ENTRY") and not os.environ.get("ANOTHERME_MAY_STOP"):
        raise RuntimeError("A job is stopped only when the owner asks for it in their own message. Tell them to send /stop.")
    job = stop(int(args["job"]))
    return dict(brief(job), note="Stopped." if job["state"] in ("stopped", "cancelled") else "It had already ended, so nothing was stopped.")


def session_jobs(args):
    jobs = all_jobs()
    if args.get("job"):
        return brief(load(args["job"]))
    return [brief(j) for j in jobs[-int(args.get("limit", 10)):]]


def schemas(schema):
    return {
        "session_send": (session_send, "Hand work to a coding session on this Mac, Claude Code unless tool is codex: it runs headless in a project folder with that project's instructions, memory and tools, and can edit files and run commands there. Use it when the owner asks for work to be done in a project (code, analysis, a draft that needs the repo). The job does not start until the owner replies ok to the exact prompt, which they are shown automatically, so write the prompt as a complete, self-contained brief: what the owner asked for and what was observed, not your guess at the cause. It starts a fresh session, which is the cheap default; pass resume only when the owner asks to continue a particular session. Returns a job number; the result is sent to the owner when it finishes.",
                         schema({"project": {"type": "string", "description": "Project folder name in the projects folder (config.json projects_dir, default ~/dev), or a full path"},
                                 "prompt": {"type": "string", "description": "The full task, self-contained, up to 3000 characters. Include any chat excerpts the session needs, quoted as data."},
                                 "model": {"type": "string", "description": "For Claude Code: sonnet (default), opus or fable. Use a bigger model only if the owner asks. Leave out for Codex."},
                                 "tool": {"type": "string", "description": "claude (default) or codex. Use codex when the owner asks for Codex or wants a Codex thread continued. A Codex job may change files in the project folder only."},
                                 "network": {"type": "boolean", "description": "Codex only: let the job use the network (installing packages, calling an API). Off unless the task needs it; the owner is shown it."},
                                 "resume": {"type": "string", "description": "Only when the owner asks to continue a session: the id of a session of that same project and that same tool (sessions_recent lists both kinds; or a finished job's session). A Codex thread is continued in place and only while it is idle. The job's turns are added to that session itself, so the owner finds them there; if the session was in use in the last few minutes it is continued in a copy instead. A long session costs dollars to reload, and the owner is shown its size."}},
                                ["project", "prompt"])),
        "session_stop": (session_stop, "Stop a running job, or cancel one that is still waiting for the owner's ok. Use it when the owner says to stop or cancel a job.",
                         schema({"job": {"type": "integer", "description": "The job number"}}, ["job"])),
        "session_jobs": (session_jobs, "List recent jobs handed to Claude Code sessions with their state (waiting_ok, running, done, failed, stopped, cancelled, expired), or show one job's result.",
                         schema({"job": {"type": "integer", "description": "Show this job in full"}, "limit": {"type": "integer"}})),
    }


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "run":
        run(int(sys.argv[2]))
    else:
        print(json.dumps([brief(j) for j in all_jobs()], ensure_ascii=False, indent=1))
