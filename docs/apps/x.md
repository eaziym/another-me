# X (Twitter) posts

Ask what an account posted or what people are saying about a topic. Examples: "What did these AI labs post today?", "What is being said on X about the new phone?", "Recent posts from @example_user."

## How it connects

X has no free way to read posts. [xposts.py](../../context/xposts.py) asks a Grok model (`x-ai/grok-4.3`) through OpenRouter to search X once and quote what it finds. The tool is `x_posts`. It returns each post's author, time, quoted text and a link.

Because a model does the quoting, it can misquote. Open the link before relying on a post.

## Set it up

1. Get an OpenRouter key at openrouter.ai and add credit.
2. Save it in one file:

   ```
   mkdir -p ~/.config/anotherme
   printf '%s' 'YOUR_KEY' > ~/.config/anotherme/openrouter_key
   chmod 600 ~/.config/anotherme/openrouter_key
   ```

3. Try it:

   ```
   python3 context/xposts.py '{"about": "what AI labs announced", "handles": ["example_lab"], "days": 2}'
   ```

## What it can and cannot do

- `about`: what to look for, up to 300 characters.
- `handles`: only posts from these accounts, up to 20.
- `days`: 1 to 7 back. Default 2.
- `limit`: 1 to 15 posts. Default 8. Fewer is cheaper.
- Public posts only. It cannot read your account, your timeline or your messages.
- The model is told to search once, then stop.
- When nothing fits, `posts` is empty and the note says "No posts were found."

## Privacy and cost

Cost: about 7 cents is set aside per call and corrected to the real cost afterwards (the comments in the code measured about 6 cents). Most of it is the posts fetched. Each caller has its own cap per local day, kept in code:

| Caller | Daily cap |
| --- | --- |
| You, talking to the agent | $0.50 |
| The WeChat group bot | $0.25 |
| The [daily feed](feed.md) | $0.40 |

A call that would take its caller past the cap is refused before anything is sent. Spending is counted in `~/.config/anotherme/x_spend.json`. The caps reset each day.

What leaves the Mac: your request text (`about`, the handles, the date) goes to OpenRouter and on to xAI, which runs Grok. Your key goes only to OpenRouter. With the default model, the posts returned also go to Anthropic as part of the conversation. With `local_model` set (see [models.md](../models.md)) the model runs on the Mac, but this tool still calls OpenRouter.

## Risks

- It costs real money, up to the caps above per caller per day.
- Posts are quoted by a model, so check them.

## If it stops working

- "no OpenRouter key is set up for X posts": create the key file above.
- "Today's budget for X posts ... is used up": wait until tomorrow.
- "OpenRouter could not be reached": check your network.
- "Grok gave no answer": OpenRouter returned an error. The message includes it. Check your credit.
- "handles are X account names ...": use plain names, no spaces.

Try by hand with the command in Set it up.
