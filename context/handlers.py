#!/usr/bin/env python3
"""What the owner's commands do, once entry.py has decided a message is one: an ok, a no or a stop for a job (and
the cards and status lines a job is shown with), /keep and /forget for notes, and /allow and /disallow for the
WeChat chats that get messages without an ok to each one.

None of this calls a model, and none of it is reachable by one: entry.command() hands over only what the owner
typed in their private Telegram chat or their own WeChat chat. A `channel` is entry's Telegram or WeChat object.
This module does not import entry: the one thing it needs from there, saving the state, is handed in.
"""
import os
import re
import time

import jobs
import memory
import wechat

HOME = os.path.expanduser("~")
YES, NO, SEVERAL = wechat._WX_YES, wechat._WX_NO, wechat._WX_SEVERAL   # "ok", "no 12", "ok to both"
STATUS_SECONDS = 20                                            # a running job's status message is rewritten no more often than this
STATUS = {}                                                    # per job: (status text shown, when)


def shown_jobs(at=None):
    """Jobs that wait for an ok and whose prompt the owner had been shown by the time `at` (default: now).
    An ok can only be about something they have seen."""
    at = int(at or time.time())            # message times are whole seconds: an ok counts from the second after the card
    return [j for j in jobs.all_jobs() if j["state"] == "waiting_ok" and j.get("announced") and int(j.get("announced_at", 0)) < at]


def approval(text):
    """An ok or a no and the jobs it names, as (yes, None | "both" | "all" | [numbers]); None when the text is neither.
    "ok", "ok 10", "ok to 10", "ok to both", "no to 10 and 11": the ways the owner has written it."""
    t = text.strip()
    one = YES.match(t) or NO.match(t)
    if one:
        return bool(YES.match(t)), [int(one.group(2))] if one.group(2) else None
    more = SEVERAL.match(t)
    if more:
        which = more.group(2).lower()
        return more.group(1).lower() not in ("no", "cancel"), which if which in ("both", "all") else [int(n) for n in re.findall(r"\d+", which)]
    return None


def answer_job(channel, text, at=None):
    """If the text is an ok/no and a job the owner was shown is waiting, start or cancel it. Returns True when it was."""
    said, shown = approval(text), shown_jobs(at)
    if not shown or not said:
        return False
    yes, which = said
    if isinstance(which, list):
        absent = [n for n in which if n not in [j["n"] for j in shown]]
        shown = [j for j in shown if j["n"] in which]
        if not shown:
            return False
        if absent:
            channel.send("Not waiting for an ok: job %s." % ", ".join(map(str, absent)))
    elif len(shown) > 1 and which != "all" and not (which == "both" and len(shown) == 2):   # "both" of three is not a choice
        channel.send("%d jobs are waiting: %s. Say which, for example ok %d, or ok all." % (len(shown), ", ".join(str(j["n"]) for j in shown), shown[-1]["n"]))
        return True
    for job in shown:
        if not yes:
            jobs.stop(job["n"])
            channel.send("Job %d cancelled." % job["n"])
            continue
        try:
            job = jobs.start(job)
        except RuntimeError as e:          # a Codex thread that is in use, a session that is gone: said, not swallowed
            channel.send("Job %d not started: %s." % (job["n"], str(e).rstrip(".")))
            continue
        where = ""
        if job.get("resume"):
            where = (", in a copy of session %s because that session is in use" if job.get("copy")
                     else ", inside %s %s (reopen it to see the work)" % ("Codex thread" if job.get("tool") == "codex" else "session", "%s")) % job["resume"][:8]
        channel.send("Job %d started in %s%s. I'll send the result when it finishes; /stop ends it." % (job["n"], os.path.basename(job["project"]), where))
    return True


def stop_job(channel, state, n=None):
    """/stop: end job n. Without a number, end the only job that is running or waiting, or ask which."""
    if n is None:
        live = [j for j in jobs.all_jobs() if j["state"] in ("running", "waiting_ok")]
        if not live:
            return channel.send("Nothing is running or waiting.")
        if len(live) > 1:
            channel.send("Which one? %s. Reply with the number." % ", ".join(
                "%d (%s, %s)" % (j["n"], os.path.basename(j["project"]), "running" if j["state"] == "running" else "waiting for ok") for j in live))
            state["asked_stop"] = {"at": time.time(), "jobs": [j["n"] for j in live]}   # only once the question went out
            return
        n = live[0]["n"]
    try:
        before = jobs.load(n)["state"]
        job = jobs.stop(n, reported=True)  # said here, so the job watcher does not say it again
    except FileNotFoundError:
        return channel.send("There is no job %d." % n)
    if job["state"] == before:
        return channel.send("Job %d had already ended (%s)." % (n, before))
    channel.send("Job %d %s." % (n, job["state"]))


def job_card(job):
    """What the owner is shown before a job may start: where it runs, what it continues, and the exact prompt."""
    codex = job.get("tool") == "codex"
    kind = ("Codex, may change files in this folder only" + (", with network access" if job.get("network") else ", no network")) if codex else job["model"]
    where = job["project"].replace(HOME + os.sep, "~/", 1)       # the whole path: two folders can share a name
    head = "▶️ Job %d in %s (%s)" % (job["n"], where, kind)
    if job.get("resume"):
        size, big = job.get("resume_tokens") or 0, job.get("resume_megabytes") or 0
        head += "\nContinues %s %s, last used %s%s." % (
            "Codex thread" if codex else "session", job["resume"][:8],
            time.strftime("%a %H:%M", time.localtime(job.get("resume_last_used") or job["created"])),
            ". It carries about %dk tokens, so this costs more than a fresh session" % (size // 1000) if size > 50000
            else ". The thread is %d MB long, so it is slow to pick up" % big if big > 20 else "")
    return "%s\n\n%s\n\nReply ok to run it, no to cancel." % (head, job["prompt"])


def job_status(job):
    """How a job stands, in a line or two: for the message kept up to date while it runs, and for /jobs."""
    seen, ended = jobs.live(job["n"]), job.get("finished")
    mins = ((ended or time.time()) - job.get("started", job["created"])) / 60
    mark = {"running": "⏳", "done": "✅", "failed": "⚠️", "stopped": "⏹"}.get(job["state"], "•")
    head = "%s Job %d · %s · %s · %d min" % (mark, job["n"], os.path.basename(job["project"]), job["state"], mins)
    if not seen:
        return head
    head += " · %d steps" % seen.get("steps", 0)
    if ended or not seen.get("now"):
        return head
    spent = (time.time() - seen.get("since", seen["at"])) / 60
    return "%s\n%s%s" % (head, seen["now"], " (%d min)" % spent if spent >= 1 else "")


def show_status(tg, job):
    """Bring the job's status message in the owner's Telegram chat up to date, if what it says has changed."""
    n, text = job["n"], job_status(job)
    shown, at = STATUS.get(n, ("", 0))
    if text == shown or (job["state"] == "running" and time.time() - at < STATUS_SECONDS):
        return
    if job["state"] == "running":
        STATUS[n] = (text, time.time())    # first: a failed rewrite waits for the next change. The closing one is tried until it lands
    message = tg.status(text, job.get("status_message"))
    STATUS[n] = (text, time.time())
    if message != job.get("status_message") or job["state"] != "running":
        jobs.change(n, status_message=message, status_closed=job["state"] != "running")


# The owner's word on notes, in the ways they write it. Telegram makes a command tappable only up to its first
# space, so a note is offered as /keep4 and /forget4; /keep on its own keeps every note that is waiting (each was
# shown to them when it was proposed), and numbers can be a list or a range: /keep 6-14, 20. Said without a slash
# it works too ("rmb them", "keep 6-14"), but only while something is waiting: otherwise those are ordinary words
# for the agent. Forgetting always takes numbers.
NOTE_COMMAND = re.compile(r"/(keep|forget)_?(?:@\w+)?(?![a-z])\s*(.*)", re.I | re.S)
KEEP_WORDS = re.compile(r"(?:please\s+|pls\s+)?(?:keep|rmb|remember|记住|记下)\s*"
                        r"(them|those|these|all|both|everything|(?:them|those|these)\s+all|all\s+of\s+(?:them|those|these)|"
                        r"这些|那些|全部|(?:notes?\s+)?#?\d[\d\s,，#and to\-–]*)\s*[.!。！]?", re.I)


def note_numbers(words):
    """The note numbers in "4", "6-14, 20" or "3 and 5"; None when the words are anything else. A range is capped."""
    words = re.sub(r"\b(notes?|and)\b|#", " ", words.lower()).replace("，", ",").replace("–", "-")
    words = re.sub(r"\s+to\s+", "-", words)
    found = []
    for part in re.split(r"[,\s]+", words.strip()):
        m = re.fullmatch(r"(\d{1,6})(?:-(\d{1,6}))?", part)
        if not m:
            return None
        first, last = int(m.group(1)), int(m.group(2) or m.group(1))
        if last < first or last - first > 500:
            return None
        found.extend(range(first, last + 1))
    return list(dict.fromkeys(found)) or None


def spans(numbers):
    """[3, 4, 5, 9] as "3-5, 9"."""
    out, numbers = [], sorted(numbers)
    for n in numbers:
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return ", ".join(str(a) if a == b else "%d-%d" % (a, b) for a, b in out)


def notes_command(channel, t, at=None):
    """/keep, /keep4, /keep 6-14, "rmb them"; /forget4, /forget 6-14. Only the owner's typed words reach this."""
    m, words = NOTE_COMMAND.fullmatch(t), KEEP_WORDS.fullmatch(t)
    verb, rest = (m.group(1).lower(), m.group(2).strip()) if m else ("keep", words.group(1).strip())
    everything = rest.lower() in ("", "all") or (not m and not rest[:1].isdigit() and not rest.lower().startswith(("note", "#")))
    numbers = None if everything else note_numbers(rest)
    if verb == "forget":
        if not numbers:
            return channel.send("Send /forget and the numbers, for example /forget 4 or /forget 6-9; /notes lists them.")
        gone = [n for n in numbers if memory.memory_forget({"id": n})["forgotten"]]
        return channel.send("Forgotten: %s." % spans(gone) if gone else "No note has that number; /notes lists them.")
    if everything:
        numbers = memory.memory_waiting(at)   # only what was already waiting when they wrote: a note proposed since has not been seen
        if not numbers:
            return channel.send("No note is waiting; /notes lists what I remember.")
    elif not numbers:
        return channel.send("Send /keep to keep every note that is waiting, or the numbers: /keep 4, /keep 6-14; /notes lists them.")
    kept = [n for n in numbers if memory.memory_keep(n)]
    missed = [n for n in numbers if n not in kept]
    channel.send(("Kept %d note%s: %s. /forget and a number removes one." % (len(kept), "" if len(kept) == 1 else "s", spans(kept)) if kept else "Nothing kept.")
                 + (" Not waiting: %s." % spans(missed) if missed and not everything else ""))


def chat_label(chat):
    also = ", also called %s" % " / ".join(chat["also_called"]) if chat.get("also_called") else ""
    return "%s (%s%s)" % (chat["name"], "group" if str(chat["id"]).endswith("@chatroom") else "direct chat", also)


def allow_chat(channel, chat):
    try:
        out = wechat.wechat_allow_set(chat["id"], chat["name"], True)
    except RuntimeError as e:                                  # the owner's chat with themselves
        return channel.send(str(e)[:1].upper() + str(e)[1:] + ".", verbatim=True)
    try:
        channel.send(("%s is on the list: what I send there goes out without asking you first. /disallow %s takes it off." if out["changed"]
                      else "%s is already on the list. /disallow %s takes it off.") % (chat_label(chat), chat["name"]), verbatim=True,
                     key="allow-%s-%d" % (chat["id"], time.time()))   # a key: WeChat has to confirm it arrived, or the change is undone
    except Exception:
        if out["changed"]:                                     # a chat is on the list only if the owner was told so
            wechat.wechat_allow_set(chat["id"], chat["name"], False)
        raise
    if out["changed"]:
        print("allowlist: %s (%s) added by the owner's command on %s" % (chat["name"], chat["id"], channel.name), flush=True)


# /allow, /allow <chat>, /allow7 (one of the chats just offered), /disallow <chat>, with Telegram's @botname allowed.
ALLOW_COMMAND = re.compile(r"/(allowed|allow|disallow)_?(\d{1,9})?(?:@\w+)?(?:\s+(.*))?", re.I | re.S)
ALLOW_OFFER_SECONDS = 600


def allow_command(channel, t, state, at, save):
    """/allow, /allow <chat>, /disallow <chat>: the WeChat chats wechat_send may message without the owner's ok to
    each message. Only a command the owner typed reaches this: no model, voice note or forwarded Telegram message
    can. A chat's whole name adds it at once. Part of a name, or a name two chats share, is only offered back, each
    chat as its own command (/allow7) with a number that is never used twice, so an old offer or a bare "1" meant
    for something else cannot add a chat. `save` writes the state down (entry.save_state)."""
    verb, pick, rest = ALLOW_COMMAND.fullmatch(t).groups()
    verb, rest = "/" + verb.lower(), (rest or "").strip().strip("\"'“”‘’").strip()
    if pick and verb == "/allow" and not rest:
        offer = state.get("allow_offer") or {}
        chat = offer.get("chats", {}).get(pick)
        if not chat or not 0 <= (at or time.time()) - int(offer.get("at", 0)) < ALLOW_OFFER_SECONDS:
            return channel.send("That choice is no longer open. Send /allow and the name again.")
        state.pop("allow_offer", None)
        return allow_chat(channel, chat)
    if pick or (verb == "/allowed" and rest):
        return channel.send("Send /allow and a friend's or group's name, or /disallow and a name. /allow on its own shows the list.")
    if not rest:
        chats = wechat._wx_allowlist()
        return channel.send(("I send to these WeChat chats without asking you first:\n%s" % "\n".join("- " + chat_label(c) for c in chats) if chats
                             else "No WeChat chat is on the list: every message waits for your ok.")
                            + "\n\n/allow and a name adds a friend or group. /disallow and a name takes one off.", verbatim=True)
    if verb == "/disallow":
        try:
            out = wechat.wechat_allow(rest, allow=False)
        except RuntimeError:
            out = {"ambiguous": True, "matches": []}
        if out.get("ambiguous"):                               # several on the list, or several chats of which one may be on it
            on = {c["id"] for c in wechat._wx_allowlist()}
            listed = [c for c in out["matches"] if c["id"] in on]
            if len(listed) != 1:
                return channel.send("Several on the list match: %s. Send /disallow with the whole name." % ", ".join(chat_label(c) for c in listed) if listed
                                    else "Nothing on the list matches that. /allow shows the list.", verbatim=True)
            out = wechat.wechat_allow_set(listed[0]["id"], listed[0]["name"], False)
        if out["changed"]:
            print("allowlist: %s (%s) removed by the owner's command on %s" % (out["chat"], out["id"], channel.name), flush=True)
        return channel.send(("%s is off the list: I'll ask before sending there." if out["changed"] else "%s was not on the list.") % out["chat"], verbatim=True)
    try:
        matches, exact = wechat.wechat_allow_matches(rest)
    except RuntimeError as e:                                  # no chat by that name, or the WeChat daemon is not answering
        return channel.send(str(e)[:1].upper() + str(e)[1:] + ".", verbatim=True)
    if exact:
        return allow_chat(channel, matches[0])
    first = int(state.get("allow_n", 0)) + 1
    state["allow_n"] = first + len(matches) - 1                # numbers are never used twice: an older offer's commands are dead
    state.pop("allow_offer", None)
    save(state)                                                # before the offer goes out, so a restart cannot hand its numbers out again
    channel.send(("Which chat? Send its command." if len(matches) > 1 else "No chat has exactly that name. If you mean this one, send its command.")
                 + "".join("\n/allow%d  %s" % (first + i, chat_label(c)) for i, c in enumerate(matches))
                 + ("\nThese are the first %d. Send more of the name to narrow it down." % len(matches) if len(matches) >= 15 else ""), verbatim=True)
    state["allow_offer"] = {"at": time.time(), "chats": {str(first + i): c for i, c in enumerate(matches)}}   # only once the offer went out
