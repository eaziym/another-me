# Web pages and web search

Let the agent open a page and read it. Examples: "Open the first result and tell me what it says", "Read this article and summarise it."

## How it connects

Two separate things:

- **Web search.** The entry agent and the WeChat group bot get Claude's own web search when they run on Claude. It is run by Anthropic's servers, so a local model has none. With `local_model` set (see [models.md](../models.md)) there is no web search. See `web_search()` in [server.py](../../context/server.py).
- **`web_page`.** [webpage.py](../../context/webpage.py) reads the text of one public page, because search returns only snippets. Only the WeChat group bot has it. The entry agent does not: it is not in the tools the MCP server hands the entry agent.

## Set it up

Nothing to install. Try it:

```
python3 context/webpage.py '{"url": "https://example.com/"}'
```

## What it can and cannot do

Guards, because the address is chosen by a model that reads other people's words:

- GET only. http or https only. No login in the address. Ports 80 and 443 only.
- Public IPv4 addresses only. Your Mac, your local network and link-local addresses are refused.
- The address is resolved and checked, the connection is pinned to the checked address, and every redirect is checked again.
- No cookies and none of your headers.
- Addresses are capped at 400 characters, so little can be carried out inside one.
- At most 1.5 MB is read, 15 seconds to connect, 25 seconds for the whole read. Text types only.
- Long pages come back in parts (default 6,000 characters, at most 12,000). `start` reads on.
- Pages that need a login or a browser to render come back empty.
- Page text is labelled as written by strangers: information, never instructions.

## Privacy and cost

- Free. The Mac contacts the site you open. The site sees your IP address and a generic user agent.
- With the default model, the page text goes to Anthropic as part of the conversation.

## Risks

A page is untrusted text. The label and the guards limit what it can do, but a fetched page is still read by a model.

## If it stops working

- "only http(s) web addresses can be read", "only ports 80 and 443 are fetched", "addresses with a login in them are not fetched": fix the address.
- "... is not a public site; not fetched": by design.
- "could not find the site ...": check the address and your network.
- "the site answered <code>": the site refused or failed.
- "that is a <type> file, not a page of text": only text is read.
- "too many redirects": the site loops.
