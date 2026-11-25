#!/usr/bin/env python3
"""The owner's two channels, Telegram and their own WeChat chat: sending a reply out (markdown as formatting on
Telegram, plain text on WeChat), fetching what they attached, and telling a message the owner wrote from anything
else in those chats (another sender, a forward, our own cards and replies).

entry.py makes one Telegram and one WeChat object and does everything else. This module does not import entry.
"""
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import wechat

MARK = "🤖"                                                    # in front of everything the agent posts on WeChat

# ---------------------------------------------------------------- formatting

# Replies and job results arrive as markdown. Telegram shows HTML tags, WeChat shows only plain text.
HTML = {"b": "<b>%s</b>", "i": "<i>%s</i>", "s": "<s>%s</s>", "code": "<code>%s</code>", "pre": "<pre>%s</pre>",
        "a": '<a href="%(url)s">%(text)s</a>', "esc": lambda t: html.escape(t, quote=False)}
PLAIN = {"b": "%s", "i": "%s", "s": "%s", "code": "%s", "pre": "%s", "a": "%(text)s (%(url)s)", "esc": lambda t: t}
_FENCE = re.compile(r"\s*```")


_ITALIC = re.compile(r"(?<![A-Za-z0-9_*/\\.])\*(?=[^\s*])([^*<\n]+?)(?<=[^\s*])\*(?![A-Za-z0-9_*/])")   # not the * in src/*.py or 2*3


def _inline(line, f):
    kept = []                              # code and links are set aside, so nothing below reads into them

    def keep(shown):
        kept.append(shown)
        return "\x00%d\x00" % (len(kept) - 1)
    line = re.sub(r"`([^`\n]+)`", lambda m: keep(f["code"] % f["esc"](m.group(1))), line.replace("\x00", ""))
    line = re.sub(r"\[([^\]\n]+)\]\((https?://(?:[^\s()]|\([^\s()]*\))+)\)",
                  lambda m: keep(f["a"] % {"text": f["esc"](m.group(1)), "url": f["esc"](m.group(2)).replace('"', "%22")}), line)
    line = f["esc"](line)
    line = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", lambda m: f["b"] % m.group(1), line)
    line = _ITALIC.sub(lambda m: f["i"] % m.group(1), line)
    line = re.sub(r"~~(?=\S)([^<\n]+?)(?<=\S)~~", lambda m: f["s"] % m.group(1), line)   # never across a tag: tags must nest
    for _ in range(3):                     # a link's text may hold code
        line = re.sub("\x00(\\d+)\x00", lambda m: kept[int(m.group(1))], line)
    return line


def render(text, f):
    """Markdown as Telegram HTML (f=HTML) or as plain text with the markdown signs taken out (f=PLAIN)."""
    out, code = [], None
    for line in text.split("\n"):
        if _FENCE.match(line):
            if code is None:
                code = []
            else:
                out += [f["pre"] % f["esc"]("\n".join(code))] if code else []
                code = None
        elif code is not None:
            code.append(line)
        elif re.match(r"\s*\|?[\s:|-]*-[\s:|-]*\|[\s:|-]*$", line):
            pass                                               # the dashes row under a table's header
        elif re.match(r"\s*([-*_])(\s*\1){2,}\s*$", line):
            out.append("———")
        else:
            head = re.match(r"\s*#{1,6}\s+(.*?)[\s#]*$", line)
            if head:                                           # a heading: one bold line, with nothing nested in it
                out.append(f["b"] % _inline(re.sub(r"\*\*|`", "", head.group(1)), f))
            else:
                line = re.sub(r"^(\s*)[-*+]\s+(?=\S)", "\\1• ", line)
                line = re.sub(r"^\s*\|(.*)\|\s*$", lambda m: " | ".join(c.strip() for c in m.group(1).split("|")), line)
                out.append(_inline(line, f))
    if code:
        out.append(f["pre"] % f["esc"]("\n".join(code)))    # a code block that was never closed
    return "\n".join(out)


def chunks(text, size, fences=True):
    """Pieces of at most `size` characters, cut at line ends. A code block cut in two is closed and reopened."""
    out, cur, fenced = [], [], False
    for line in text.split("\n"):
        for piece in [line[i:i + size - 8] for i in range(0, len(line), size - 8)] or [""]:
            if cur and sum(len(x) + 1 for x in cur) + len(piece) > size - 8:
                out.append("\n".join(cur + (["```"] if fenced else [])))
                cur = ["```"] if fenced else []
            cur.append(piece)
        if fences and _FENCE.match(line):
            fenced = not fenced
    return out + ["\n".join(cur)]


# ---------------------------------------------------------------- channels

class Telegram:
    name = "telegram"

    def __init__(self, token_file, owner_file, inbox):
        with open(token_file) as f:
            self.token = f.read().strip()
        with open(owner_file) as f:
            self.owner = int(f.read().strip())
        self.inbox = inbox                 # the folder files the owner sends are saved in

    def call(self, method, wait=30, **params):
        """One Bot API call. `wait` is how long to wait for the answer; every other argument goes to Telegram."""
        data = urllib.parse.urlencode(params).encode()
        with urllib.request.urlopen("https://api.telegram.org/bot%s/%s" % (self.token, method), data=data, timeout=wait) as r:
            return json.load(r)["result"]

    def send(self, text, verbatim=False, key=None):
        """Markdown is sent as formatting. Verbatim text goes out character for character."""
        for piece in chunks(text, 3800, fences=not verbatim):  # Telegram's limit is 4096 characters a message
            shown = piece if verbatim else render(piece, HTML)
            if not shown.strip():
                continue
            try:
                self._post(shown, None if verbatim else "HTML")
            except urllib.error.HTTPError as e:
                if verbatim or e.code != 400:                  # 400: Telegram could not read the formatting
                    raise
                self._post(render(piece, PLAIN))

    def status(self, text, message_id=None):
        """A message that is kept up to date: sent once without a sound, then rewritten in place. Returns its id."""
        if message_id:
            try:
                self.call("editMessageText", wait=8, chat_id=self.owner, message_id=message_id, text=text)
                return message_id
            except urllib.error.HTTPError as e:
                if e.code != 400:
                    raise
                if b"not modified" in e.read():
                    return message_id
                # else the message is gone or too old to edit: a new one takes its place
        return self.call("sendMessage", wait=8, chat_id=self.owner, text=text, disable_notification="true")["message_id"]

    def upload(self, path, caption=""):
        """Send a picture or a recording of the screen from this Mac to the owner's chat."""
        if os.path.getsize(path) > 49 * 1024 * 1024:
            raise RuntimeError("the file is %d MB, more than Telegram takes from a bot" % (os.path.getsize(path) // 1048576))
        method, field = ("sendVideo", "video") if path.endswith(".mov") else ("sendPhoto", "photo")
        mark = "anotherme%d" % time.time_ns()
        fields = [("chat_id", str(self.owner))] + ([("caption", caption)] if caption else [])
        body = b"".join(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (mark, k, v)).encode() for k, v in fields)
        with open(path, "rb") as f:
            body += ('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\nContent-Type: application/octet-stream\r\n\r\n'
                     % (mark, field, os.path.basename(path))).encode() + f.read() + ("\r\n--%s--\r\n" % mark).encode()
        request = urllib.request.Request("https://api.telegram.org/bot%s/%s" % (self.token, method), data=body,
                                         headers={"Content-Type": "multipart/form-data; boundary=" + mark})
        with urllib.request.urlopen(request, timeout=180) as r:
            return json.load(r)["result"]

    def _post(self, text, mode=None):
        params = dict({"parse_mode": mode, "disable_web_page_preview": "true"} if mode else {}, chat_id=self.owner, text=text)
        try:
            return self.call("sendMessage", **params)
        except urllib.error.HTTPError:
            raise
        except OSError:                    # no answer in time: once more, since a lost reply is worse than a double
            return self.call("sendMessage", **params)

    def typing(self):
        self.call("sendChatAction", chat_id=self.owner, action="typing")

    def download(self, file_id, name):
        """Save a file the owner sent into the inbox and return its path."""
        info = self.call("getFile", file_id=file_id)
        os.makedirs(self.inbox, exist_ok=True)
        safe = re.sub(r"[^\w.\-]", "_", name)[-80:]
        path = os.path.join(self.inbox, "%d_%s" % (int(time.time()), safe))
        with urllib.request.urlopen("https://api.telegram.org/file/bot%s/%s" % (self.token, info["file_path"]), timeout=120) as r, \
                open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as f:
            f.write(r.read())
        return path


class WeChat:
    name = "wechat"

    def __init__(self, inbox):
        self.inbox = inbox

    def send(self, text, verbatim=False, key=None):
        """Into the owner's own chat. With a `key` the message must be confirmed as arrived, and sending it again
        under the same key within ten minutes does not post it twice: for what the owner has to have seen."""
        me = wechat._wx_me()
        for i, piece in enumerate(chunks(text if verbatim else render(text, PLAIN), 1400, fences=False)):
            if piece.strip():
                once = "entry-%s-%d-%d" % (key, time.time() // 600, i) if key else "entry-%d-%d" % (os.getpid(), time.time() * 1000)
                sent = wechat._wx_deliver(me, MARK + " " + piece, once)
                if sent.get("state") in ("failed", "cancelled", "needs_review") or (key and sent.get("state") != "accepted"):
                    raise RuntimeError("WeChat did not take the message (%s)" % sent.get("state"))

    def typing(self):
        pass

    def download(self, message_id):
        """Save an attachment the owner sent in their own chat into the inbox and return its path."""
        os.makedirs(self.inbox, mode=0o700, exist_ok=True)
        fetched = wechat.wechat_media({"message_id": message_id}, into=self.inbox, transcribe=False)   # entry.heard transcribes it, once
        if "path" not in fetched:
            raise RuntimeError(fetched.get("note") or "WeChat did not have it (%s)" % fetched.get("state"))
        return fetched["path"]


def telegram_message(update, owner):
    """The message of a private update from the owner, or None for anything else."""
    m = update.get("message") or {}
    if (m.get("chat") or {}).get("type") != "private":
        return None
    if (m.get("from") or {}).get("id") != owner or (m.get("chat") or {}).get("id") != owner:
        return None
    return m


def forwarded(m):
    """Whether a Telegram message carries someone else's words: the owner passed it on (or a bot wrote it for
    them), they did not type it."""
    return any(m.get(k) for k in ("forward_origin", "forward_date", "forward_from", "forward_from_chat", "forward_sender_name", "via_bot"))


def wechat_owner_text(m, me):
    """The text of something the owner typed in their own chat, or None for our own cards, notes and replies."""
    if not (m.get("direction") == "outgoing" or m.get("senderId") == me):
        return None
    body = (m.get("body") or "").strip()
    if not body or not (m.get("type") == 1 or m.get("quote")) or body.startswith(wechat._WX_OURS):
        return None
    return body


def wechat_owner_media(m, me):
    """What the owner sent in their own chat when it is not text: 'image' or 'file' to fetch and attach the same
    way a Telegram photo or document is, 'voice' or 'video' to fetch and transcribe, or None when wechat_owner_text already covers it (or there is nothing of the owner's here at all)."""
    if not (m.get("direction") == "outgoing" or m.get("senderId") == me):
        return None
    if wechat_owner_text(m, me) is not None:
        return None
    t, app_t = m.get("type"), m.get("appMessageType")
    if t == 3:
        return "image"
    if t == 49 and app_t == 6:
        return "file"
    if t == 34:
        return "voice"
    if t == 43:
        return "video"
    return None
