#!/bin/bash
# Install one of another-me's background services as a launchd agent for this user, or show the file it would write.
#
#   scripts/install-service.sh entry                    the agent you talk to from your phone
#   scripts/install-service.sh group-bot <chat id>      the responder for one WeChat group (an id ending in @chatroom)
#   scripts/install-service.sh rednote-browser          the windowless Chrome RedNote is read through
#   scripts/install-service.sh --print <service> ...    print the launchd file and change nothing
#   scripts/install-service.sh --remove <service>       stop it and delete its launchd file
#
# Each runs with the system Python (/usr/bin/python3) from this repository's folder, and logs to
# ~/Library/Logs/anotherme-<service>.log. The entry service and the group bot are restarted if they stop.
set -euo pipefail

usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

print=false remove=false
case "${1:-}" in
  --print) print=true; shift ;;
  --remove) remove=true; shift ;;
esac
service="${1:-}"; [ -n "$service" ] || usage; shift

repo="$(cd "$(dirname "$0")/.." && pwd)"
label="dev.anotherme.$service"
plist="$HOME/Library/LaunchAgents/$label.plist"
domain="gui/$(id -u)"

if $remove; then
  launchctl bootout "$domain/$label" 2>/dev/null || true
  rm -f "$plist"
  echo "removed $label"
  exit 0
fi

keep=true
case "$service" in
  entry)           args=(-u "$repo/context/entry.py") ;;
  group-bot)       [ $# -eq 1 ] && [[ "$1" == *@chatroom ]] || { echo "group-bot needs the group's chat id, ending in @chatroom" >&2; exit 2; }
                   args=(-u "$repo/context/wechat_bot.py" "$1") ;;
  rednote-browser) args=("$repo/context/rednote.py" start); keep=false ;;
  *) usage ;;
esac

xml() { local s="$1"; s="${s//&/&amp;}"; s="${s//</&lt;}"; s="${s//>/&gt;}"; printf '%s' "$s"; }
log="$HOME/Library/Logs/anotherme-$service.log"
{
  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
EOF
  for a in "${args[@]}"; do printf '    <string>%s</string>\n' "$(xml "$a")"; done
  cat <<EOF
  </array>
  <key>WorkingDirectory</key><string>$(xml "$repo/context")</string>
  <key>RunAtLoad</key><true/>
EOF
  $keep && printf '  <key>KeepAlive</key><true/>\n  <key>ThrottleInterval</key><integer>60</integer>\n'
  cat <<EOF
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$(xml "$log")</string>
  <key>StandardErrorPath</key><string>$(xml "$log")</string>
</dict>
</plist>
EOF
} > "${TMPDIR:-/tmp}/$label.plist.$$"

if $print; then
  cat "${TMPDIR:-/tmp}/$label.plist.$$"; rm -f "${TMPDIR:-/tmp}/$label.plist.$$"; exit 0
fi

plutil -lint "${TMPDIR:-/tmp}/$label.plist.$$" >/dev/null
mkdir -p "$HOME/Library/LaunchAgents"
launchctl bootout "$domain/$label" 2>/dev/null || true
mv "${TMPDIR:-/tmp}/$label.plist.$$" "$plist"
launchctl bootstrap "$domain" "$plist"
echo "installed $label; it logs to $log"
echo "after editing its code, restart it with: launchctl kickstart -k $domain/$label"
