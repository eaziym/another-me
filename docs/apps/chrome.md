# Chrome

Ask the agent what is open in your Google Chrome, or what a tab says, including tabs in the background. It can also find files you downloaded from a site.

- "Which tabs do I have open about the visa form?"
- "Read my ChatGPT tab and summarise the last answer."
- "What did I download from chatgpt.com this week?"

## How it connects

The tools are `chrome_tabs`, `chrome_read` and `downloads_from` in [`context/server.py`](../../context/server.py).

- `chrome_tabs` asks Chrome for its windows and tabs with AppleScript (JXA): window number, tab number, address, title and which tab is active in its window. Numbers start at 0. Pass `contains` to keep only tabs whose address or title contains a word.
- `chrome_read` asks Chrome to save one tab as "complete html" into a temporary folder, waits up to 20 seconds for the file to stop growing, turns it into plain text, and deletes the folder. It does not switch tabs or bring Chrome to the front.
- `downloads_from` asks Spotlight (`mdfind`) for files whose "where from" record (`kMDItemWhereFroms`) contains a site name, then reads each file's record with `mdls`.

Only Google Chrome is supported. Other browsers are not read.

## Set it up

1. Install Google Chrome and keep it running while you want the agent to read it.
2. The first time a tool runs, macOS asks whether the program running the server may control Google Chrome. Allow it. You can change this later in System Settings → Privacy & Security → Automation.
3. For `downloads_from`, Spotlight must be on for the folder your downloads go to (the default setting).
4. Try it:

```
python3 context/server.py chrome_tabs '{}'
python3 context/server.py chrome_read '{"contains": "chatgpt"}'
python3 context/server.py downloads_from '{"source": "github.com", "days": 3}'
```

## What it can and cannot do

`chrome_read` arguments:

- `contains`: pick the tab whose address or title contains this. If several match, it returns the list and asks you to narrow it, unless `first` is true.
- `window` and `tab`: pick a tab by number instead (default 0 and 0).
- `max_chars` (default 20000) and `offset`: page through a long page. The result includes `total_chars`.

What "read" returns is the visible text of the saved page: no scripts, styles or images. If the page has a `<main>` element with enough text, only that is returned. Text that the page loads or draws after you stopped looking may be missing, and text behind a login is returned only if Chrome shows it.

`downloads_from` takes `source` (default `chatgpt.com`) and `days` (default 7). It returns the path, size, modified time and the address each file came from (with the query part removed), newest first.

It cannot click, type, switch tabs or open pages. Chrome's own pages (`chrome://...`) cannot be saved, so they cannot be read.

## Privacy and cost

By default the agent's model is Claude through Claude Code, so whatever a tool returns is sent to Anthropic as part of the conversation. A tab's text can contain anything you have open: mail, bank pages, private chats. Close tabs you would not want read.

If you set `local_model` in `~/.config/anotherme/config.json` (see [models](../models.md)), the text stays on your Mac.

Nothing here costs money by itself.

## If it stops working

- `no open tab matches 'word'`: no tab's address or title contains it. Run `chrome_tabs` and look.
- `Chrome did not save the tab (internal pages such as chrome:// cannot be saved)`: the tab is a Chrome page, or the save failed. Try another tab.
- An error from `osascript` mentioning "Not authorized" or "-1743": Automation is not allowed. Open System Settings → Privacy & Security → Automation and switch on Google Chrome for the program listed there.
- `ambiguous: true` in the result: several tabs match. Pass `window` and `tab`, or `first: true`.
- `downloads_from` returns an empty list: nothing was downloaded from that site in that many days, or Spotlight has not indexed it.
