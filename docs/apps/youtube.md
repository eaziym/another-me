# YouTube

Ask what is said in a video. Examples: "Summarise this video: <link>", "What does the speaker say about pricing, in this talk?", "Give me the transcript of this lecture."

## How it connects

[youtube.py](../../context/youtube.py) gives the tool `youtube_transcript`. It uses yt-dlp to fetch the video's captions (the uploader's, else YouTube's automatic ones; it prefers Chinese, then English). If the video has no captions, it fetches the sound and turns five minutes of it into text on your Mac per call. See [voice.md](voice.md).

## Set it up

1. Install yt-dlp:

   ```
   brew install yt-dlp
   ```

2. When YouTube changes and it stops working, upgrade it:

   ```
   brew upgrade yt-dlp
   ```

3. Try it:

   ```
   python3 context/youtube.py '{"url": "https://youtu.be/VIDEO_ID"}'
   ```

For the no-captions case, the speech-to-text setup in [voice.md](voice.md) is also needed.

## What it can and cannot do

- It takes a YouTube address (watch, youtu.be, shorts, live, embed) or a bare 11-character id. A channel, playlist or search page is refused.
- One reply holds up to 60,000 characters (about an hour of talk). A longer video is read on from a minute the reply names (`next_from_minute`).
- A live stream that is still running has no transcript.
- Read-only. No login, no key.

Safety: yt-dlp is only given an address the code writes itself from the 11-character id, never your text. It runs without your own yt-dlp config. What a video says is treated as information, never as instructions.

## Privacy and cost

- Free. Nothing of yours is sent. The Mac contacts YouTube to fetch the captions or sound.
- With the default model, the transcript goes to Anthropic as part of the conversation. With `local_model` set (see [models.md](../models.md)) the model runs on the Mac, but yt-dlp still contacts YouTube.
- The WeChat group bot has this tool too.

## Risks

YouTube changes often and can break yt-dlp until you upgrade it.

## If it stops working

- "yt-dlp is not installed on this Mac": `brew install yt-dlp`.
- "YouTube would not give this video: ...": private, removed, age-gated or blocked. Run `brew upgrade yt-dlp` and retry.
- "YouTube did not answer in N seconds": retry later.
- "that is not a YouTube address" or "no video id in that address": give one video's link.
- "the video has no captions and its sound could not be fetched": nothing to read.

Try by hand with the command in Set it up.
