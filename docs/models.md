# Models and privacy

Every model call another-me makes goes through Claude Code, run headless. This covers the agent on your phone, the
WeChat group bot, the daily look at what you typed, the daily feed and Claude Code jobs. Claude Code is the harness:
it runs the conversation, offers only the tools each service allows and enforces their flags. You choose the model
behind it, and that choice decides where the agent's words go.

## Claude (the default)

Install Claude Code with its native installer, which puts it at `~/.local/bin/claude` (the services look there), and
sign in once by running `claude`. A Claude subscription is usually the cheapest way to run another-me. Claude Code's
other ways of signing in work as they do in Claude Code.

- The agent on your phone starts on Sonnet. `/model haiku`, `/model sonnet`, `/model opus` or `/model fable`
  switches it. Each name maps to a full model id in `MODEL_IDS` in [server.py](../context/server.py). Change that
  table when a model is replaced.
- Every call has a spending cap (`--max-budget-usd`). The caps are in the code: `MAX_USD_PER_CALL` in
  [entry.py](../context/entry.py), and one per service. `/cost` shows today's spend.
- The agent has Claude's web search.

**What goes to Anthropic.** Your messages to the agent, your notes, and everything a tool returns in that
conversation: chat messages, transcripts, page text, files you attach, pictures it opens. Anthropic's terms for your
plan cover that data. Check your privacy settings there.

## A model on your Mac

Set `local_model` in `~/.config/anotherme/config.json`:

```json
{
  "local_model": {"url": "http://127.0.0.1:11434", "model": "qwen3:8b", "token": "ollama"}
}
```

`url` and `model` are required. `token` is whatever your server expects, and anything works for a server with no
key. The server must speak Anthropic's Messages API. These do:

| Server | Version | url |
|---|---|---|
| [Ollama](https://docs.ollama.com/integrations/claude-code) | 0.14 or later | `http://127.0.0.1:11434` |
| [LM Studio](https://lmstudio.ai/docs/integrations/claude-code) | 0.4.1 or later | `http://127.0.0.1:1234` |
| llama.cpp `llama-server` | with the Messages API | its address |

For example, with Ollama:

```bash
brew install ollama
OLLAMA_CONTEXT_LENGTH=32768 ollama serve      # the agent's instructions and tool list need a long context
ollama pull qwen3:8b
```

Run Ollama as a service (`brew services start ollama`) if it should be there after a restart, and set its context
length the same way.

The setting is read once per call, at the start, and applies to every service. A `local_model` that lacks its `url` or
`model` stops every call with an error; it never falls back to Claude.

**What changes on a local model**

- The call goes to your server. Every model Claude Code might pick for a side task is your model. Claude Code's
  non-essential traffic (update checks, error reports) is turned off.
- No web search; it runs on Anthropic's servers. The agent and the group bot are told so.
- No spending caps, and costs are logged as zero. Claude Code would price an unknown model as Claude, and the cap
  would cut free runs short.
- `/model` says which local model is in use; the Claude names do nothing until you remove the setting.
- A conversation is continued only on the model it was held with. Switching starts a fresh one, so a transcript is
  never handed from one to the other.
- The daily feed does not run: it checks what it reports with web search.
- Claude Code jobs get only this project's tool server, none of your other MCP connectors, and no WebSearch or
  WebFetch.

**What still leaves your Mac.** The model call doesn't. These still do:

- Tools that are online by nature: X lookups go to OpenRouter and xAI. Web pages, YouTube, RedNote, Hupu and
  market data come from their sites.
- WeChat and Telegram traffic between their own servers and the daemon or Telethon.
- Codex jobs go to OpenAI.
- A job's own commands can reach the network, like any program you run.

We checked this on a real call: Ollama with qwen3:8b, the agent asked which apps were running. We sampled every TCP
connection of the agent's processes several times a second. The only one was to `127.0.0.1:11434`. Sampling can miss
a very short connection, so treat this as evidence, not proof.

**Which model.** The agent's instructions are long and it uses many tools, so larger models follow them better. In
that test qwen3:8b on an Apple-silicon Mac with 24 GB answered a one-tool question in 30 to 45 seconds. Use the
largest model that runs comfortably on your Mac, and give it at least 32k of context.

## Switching back

Remove `local_model` from `config.json`. The next message starts a fresh conversation on Claude.
