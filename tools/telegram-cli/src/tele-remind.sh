#!/usr/bin/env bash
# teleremind — One-off Telegram reminders
# Usage:
#   teleremind 5m "Message text"        # delay (supports 30s, 5m, 1h30m)
#   teleremind 2025-09-12T13:14 "Message" # absolute local time (ISO)
#
# Notes:
# - Loads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from ~/AGENTS.env
# - Schedules a background sleep in the current shell session; not durable across reboot/logout
set -euo pipefail

die() { echo "tele-remind: $*" >&2; exit 1; }

[[ $# -ge 2 ]] || die "Usage: teleremind <duration|ISO_LOCAL> 'Message'"

TARGET="$1"; shift
MSG="$*"

# Load env (if present)
# Load env safely (ignore non-assignment lines)
if [[ -f "$HOME/AGENTS.env" ]]; then
  # export only lines like KEY=VALUE, ignoring comments and blanks
  # shellcheck disable=SC2046
  # Only simple KEY=VALUE without spaces; ignore lines with spaces to avoid URLs/scope lists
  while IFS= read -r line; do
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    # skip lines containing spaces to avoid invalid identifiers/values
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]+$ ]]; then
      export "$line"
    fi
  done < "$HOME/AGENTS.env"
fi

: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN missing (set in ~/AGENTS.env)}"
: "${TELEGRAM_CHAT_ID:?TELEGRAM_CHAT_ID missing (set in ~/AGENTS.env)}"

secs_from_duration() {
  local s="$1" total=0 num unit
  # supports forms like 90s, 5m, 2h, or combination 1h30m
  while [[ "$s" =~ ^([0-9]+)([smh])(.*)$ ]]; do
    num="${BASH_REMATCH[1]}"; unit="${BASH_REMATCH[2]}"; s="${BASH_REMATCH[3]}"
    case "$unit" in
      s) total=$(( total + num )) ;;
      m) total=$(( total + num*60 )) ;;
      h) total=$(( total + num*3600 )) ;;
    esac
  done
  [[ $total -gt 0 ]] || die "Invalid duration; use like 90s, 5m, 1h30m"
  echo "$total"
}

schedule_after() {
  local seconds="$1"
  nohup bash -c "sleep $seconds; curl -sS -X POST 'https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage' --data-urlencode chat_id='${TELEGRAM_CHAT_ID}' --data-urlencode text='$MSG' >/dev/null" \
    >/dev/null 2>&1 &
  disown || true
}

if [[ "$TARGET" =~ ^[0-9]+([smh][0-9smh]*)?$ || "$TARGET" =~ ^([0-9]+[smh])+$ ]]; then
  seconds=$(secs_from_duration "$TARGET")
  schedule_after "$seconds"
  echo "Scheduled Telegram reminder in ${TARGET}: $MSG"
else
  # at <ISO_LOCAL>, e.g., 2025-09-12T13:14 or 2025-09-12T13:14:30
  iso="$TARGET"
  # macOS date parsing
  if date -j -f '%Y-%m-%dT%H:%M:%S' "$iso" '+%s' >/dev/null 2>&1; then
    target_epoch=$(date -j -f '%Y-%m-%dT%H:%M:%S' "$iso" '+%s')
  elif date -j -f '%Y-%m-%dT%H:%M' "$iso" '+%s' >/dev/null 2>&1; then
    target_epoch=$(date -j -f '%Y-%m-%dT%H:%M' "$iso" '+%s')
  else
    die "Invalid input. Use duration like 5m or ISO time YYYY-MM-DDTHH:MM[:SS]"
  fi
  now_epoch=$(date '+%s')
  delay=$(( target_epoch - now_epoch ))
  [[ $delay -gt 0 ]] || die "Time is in the past"
  schedule_after "$delay"
  echo "Scheduled Telegram reminder at ${iso}: $MSG"
fi
