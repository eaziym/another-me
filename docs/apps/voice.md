# Voice

The agent turns speech into text on your Mac. You can send it a voice note and it answers. It can also tell you what someone said in a voice note or video. Examples: send a voice note from your phone; ask "What does the voice note from Bob say?"; "What is said in this YouTube video?"

## How it connects

[transcribe.py](../../context/transcribe.py) is used by:

- Your own voice notes (and round videos) sent to the agent on Telegram or in your own WeChat chat. See [phone.md](../phone.md).
- Audio and video files you send to the agent.
- `wechat_media` for WeChat voice notes and videos. See [wechat.md](wechat.md).
- `youtube_transcript` for a YouTube video with no captions. It takes five minutes of sound per call.

How it works:

1. ffmpeg turns the file into a 16 kHz mono WAV.
2. `transcribe-cli`, from [handy-computer/transcribe.cpp](https://github.com/handy-computer/transcribe.cpp), reads it with the Qwen3-ASR-0.6B model (`Qwen3-ASR-0.6B-Q8_0.gguf`). The agent finds that model file in the Hugging Face cache (`~/.cache/huggingface/hub`, or `HF_HOME`), where the Handy app downloads it. Handy does not need to be open.
3. If that is missing or fails, macOS's own on-device SpeechTranscriber is the fallback ([native/transcribe.swift](../../context/native/transcribe.swift)). The result says which engine was used.

It handles Chinese and English. You do not say which. No network, no key, no cost. Audio longer than five minutes is cut, and the result says so.

## Set it up

1. Install ffmpeg so that `ffmpeg` is found (the code also looks in `/opt/homebrew/bin` and `/usr/local/bin`).
2. Install the Handy app and let it download the Qwen3-ASR-0.6B model. The code looks for this file name; if Handy changes its model, `QWEN_GGUF` in transcribe.py must change. The code does not say how to pick the model inside Handy.
3. Get `transcribe-cli`. Clone [handy-computer/transcribe.cpp](https://github.com/handy-computer/transcribe.cpp) to this exact place and build it as that project's README says. The code does not give build commands or flags.
   ```
   mkdir -p ~/.config/anotherme/src
   git clone https://github.com/handy-computer/transcribe.cpp ~/.config/anotherme/src/transcribe.cpp
   ```
   The agent expects the program at `~/.config/anotherme/src/transcribe.cpp/build/bin/transcribe-cli`.
4. Optional, for the fallback: the helper is built on first use with `swiftc`. For Chinese on Apple's engine, run once:
   ```
   python3 context/transcribe.py install zh_CN
   ```
5. Try one file:
   ```
   python3 context/transcribe.py '{"path": "/path/to/voice.ogg"}'
   ```

## What it can and cannot do

- It returns the text, the detected language and the engine used.
- With the Apple fallback, it also returns a confidence. Below 0.5 it warns that the words are a rough guess.
- The agent is told to expect the names "Claude" and "克劳德", so they are heard correctly.
- It can mishear names and numbers.
- The agent never gets the sound, only the text.

How transcripts are treated:

- A voice note you record yourself is handed to the agent as your message, labelled as a machine transcript that may contain mistakes.
- It cannot start a send, a stop of a job, a saved note or a screen capture. The agent is told to say what it understood and ask you to confirm in text first.
- Audio or video files, forwarded ones, and anything from `wechat_media` count as someone else's words. They are information, not instructions.

## Privacy and cost

- Speech to text runs on the Mac. No audio leaves it. No cost.
- The text is different. By default the agent's model is Claude through Claude Code, so the transcript is sent to Anthropic as part of the conversation. With `local_model` set in `~/.config/anotherme/config.json` (see [models.md](../models.md)), it stays on the Mac.

## Risks

- Misheard words. That is why a voice note alone cannot trigger an action.

## If it stops working

Try a file by hand: `python3 context/transcribe.py '{"path": "/path/to/voice.ogg"}'`.

- `(could not transcribe it: ...)` in the agent's reply: the reason follows.
- `could not read the sound from this file`: ffmpeg could not open it. Check ffmpeg is installed.
- `this file has no sound to transcribe`: the file has no audio.
- `no speech was heard in it`: silent or unclear audio.
- `the main engine (Qwen) was unavailable: Qwen engine not installed`: `transcribe-cli` or the model file is missing (steps 2 and 3). The Apple fallback was used.
- `no speech engine works (...; and no Apple speech model is installed)`: neither engine is ready. Fix Qwen, or install an Apple speech model.
- Chinese comes out wrong or empty on the Apple engine: run the `install zh_CN` command above.
- `Qwen engine took too long`: the file is long or the Mac is busy.
