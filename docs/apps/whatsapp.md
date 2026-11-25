# WhatsApp

You can ask the agent to read your WhatsApp chats. Examples: "What did the family group say today?", "Find the address Alice sent me last week", "Do I have unread chats?" It cannot send.

## How it connects

The agent reads the local database of the WhatsApp app for Mac. It opens the file read-only:

```
~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite
```

The tools are `whatsapp_chats` and `whatsapp_read`, in [server.py](../../context/server.py). Nothing goes to WhatsApp's servers.

## Set it up

1. Install WhatsApp for Mac, sign in and let it sync. The agent reads only what is already on this Mac.
2. Give the program that runs the agent Full Disk Access. macOS protects this folder.
   - Open System Settings → Privacy & Security → Full Disk Access.
   - Add the program and switch it on.
3. Which program? The entry agent (the one you talk to from your phone) runs on its own copy of Claude Code at `~/.config/anotherme/bin/claude-bot`. A fixed path lets macOS keep the permission. Make the copy:
   ```
   mkdir -p ~/.config/anotherme/bin
   cp ~/.local/bin/claude ~/.config/anotherme/bin/claude-bot
   ```
   Then give `claude-bot` Full Disk Access. If the file exists, the entry agent uses it. If not, it uses `~/.local/bin/claude`, whose path changes with each version.
4. When you replace the copy, update it like this so a call in progress keeps the old file:
   ```
   cd ~/.config/anotherme/bin && cp ~/.local/bin/claude claude-bot.new && mv claude-bot.new claude-bot
   ```
   Check the permission still holds with a WhatsApp question. If macOS asks again, grant it again.
5. To try it from a terminal, the terminal app needs Full Disk Access too:
   ```
   python3 context/server.py whatsapp_chats '{"limit": 5}'
   ```

## What it can and cannot do

- `whatsapp_chats`: recent chats with name, group or direct, unread count, last activity and how many messages are on this Mac.
- `whatsapp_read`: messages from one chat, oldest first. Arguments: `chat` (name or part of a name), `limit` (default 50), `hours`, `search`. If several chats match, they are listed and nothing is guessed.
- Pictures, voice notes and other media show as a placeholder such as `[image]`. The agent does not open them.
- It covers only what WhatsApp has synced to this Mac.
- It never sends, and it does not mark anything as read.

## Privacy and cost

- The database is read on the Mac. Nothing leaves it from this app.
- By default the agent's model is Claude through Claude Code. Whatever a tool returns, which here is chat names and message text, is sent to Anthropic as part of the conversation. With `local_model` set in `~/.config/anotherme/config.json` (see [models.md](../models.md)), it stays on the Mac.
- No cost from this app.

## Risks

- Full Disk Access is broad. It lets that program read many protected files on your Mac, not only WhatsApp's. Give it only to the program that runs the agent.
- WhatsApp may change its database layout. Then reads can fail or return wrong data. That is not covered by the code.

## If it stops working

Try one tool by hand: `python3 context/server.py whatsapp_chats '{"limit": 5}'`.

- `WhatsApp database not found; is WhatsApp for Mac installed and signed in?`: install and sign in. If it is installed, the program has no Full Disk Access, so the file looks missing. Grant it (step 2).
- `no WhatsApp chat matches ...`: use the chat name as the list shows it.
- A permission dialog on the Mac, or an error about access: grant Full Disk Access to the program named in the dialog. After replacing `claude-bot`, grant it again.
