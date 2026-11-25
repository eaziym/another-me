# Xiaohongshu (RedNote)

Ask the agent what RedNote says about something. Examples: "What does RedNote say about hotels in Chengdu?", "Search RedNote for 咖啡 and read the top note", "Ask 点点 which air fryer people recommend."

RedNote is a large part of what Chinese-speaking users read, and it has no public API. That is why it is included, and why it works the way it does (see Risks).

## How it connects

[rednote.py](../../context/rednote.py) starts a second Google Chrome of its own. It has no window, its own profile folder (`~/.config/anotherme/chrome-profile`) and a DevTools port on `127.0.0.1:9455`, reachable only from your Mac. Your everyday Chrome is not touched. You sign in to RedNote once in that profile. The tools then open pages as tabs, read them and close them.

Three tools:

- `rednote_search`: lists notes for a few search words (at most 60 characters).
- `rednote_note`: reads one note, comments included. It takes a link from a search result.
- `rednote_ask`: types one question (at most 200 characters) into RedNote's own AI, 点点, and returns its answer. The answer is RedNote's summary of many notes. If there is no answer in 120 seconds it gives up.

## Set it up

1. Install Google Chrome (the code looks for `/Applications/Google Chrome.app`).
2. Sign in once. A Chrome window opens until you have signed in (up to 300 seconds):

   ```
   python3 context/rednote.py login
   ```

3. Start the hidden browser at login, with the launchd service:

   ```
   scripts/install-service.sh rednote-browser
   ```

   This runs `rednote.py start`. Without it, the browser is started on first use.
4. Check:

   ```
   python3 context/rednote.py status
   ```

## What it can and cannot do

- It reads. Search and note reading click and type nothing.
- `rednote_ask` is the only tool that types on a page. It sends only if the box holds exactly your question.
- Nothing likes, follows, comments, posts or messages.
- Pacing: at most 30 page opens in ten minutes. After that it refuses until some minutes pass.
- The entry agent refuses all three tools unless your own typed messages mention RedNote. The code checks your message and your recent messages from the last two days for one of: RedNote, Xiaohongshu, xhs, 小红书, 红书, 点点. If none is there, it refuses and nothing goes out under your account. This stops text from other people (a chat, a web page) from making the agent use your account. Say "RedNote" in your own message.
- The WeChat group bot does not get RedNote. It acts under your signed-in account, so it stays out of groups.
- What notes and comments say is treated as information, never as instructions.

## Privacy and cost

- No cost. No API key.
- Your search words and questions go to RedNote, under your account. RedNote can see them.
- `rednote_ask` leaves the conversation in your 点点 history on RedNote.
- With the default model, what the tools return goes to Anthropic as part of the conversation. With `local_model` set (see [models.md](../models.md)) the model runs on the Mac, but the tools still contact RedNote.
- The sign-in lives only in the profile folder above.

## Risks

> [!WARNING]
> This automates a browser that is signed in to your RedNote account. RedNote's terms do not allow that. RedNote can limit or ban the account. The pages can change and break the tools without notice. Using it is your choice and your risk. Consider an account you can afford to lose.

The pacing cap and the "you must have mentioned RedNote" check reduce the load and the chance of surprise. They do not remove the risk.

## If it stops working

Try the tools by hand:

```
python3 context/rednote.py status
python3 context/rednote.py search '咖啡'
python3 context/rednote.py note '<address from a search result>'
python3 context/rednote.py ask '<question>'
```

Messages from the code:

- "Google Chrome is not installed on this Mac": install Chrome.
- "RedNote is not signed in in the agent's own browser": run the `login` command above.
- "RedNote is asking for a human check": run `login` and clear it in the window.
- "...is signing in to RedNote on the Mac right now; try again in a few minutes": `login` is open. Finish or close it.
- "that is %d RedNote pages in ten minutes, which is the limit": wait.
- "port 9455 on this Mac is in use by a program that is not the agent's own Chrome": free the port.
- "...the page may have changed": RedNote changed its pages. The selectors in [rednote.py](../../context/rednote.py) need an update.
- "The owner's own typed messages have not mentioned RedNote": mention RedNote in your message.
- "RedNote did not show that note": it was removed or its link expired. Search again.
- `python3 context/rednote.py quit` stops the hidden browser.
