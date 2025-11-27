# Telegram CLI

A lightweight Bash script for sending one-off Telegram notifications and reminders.

## Overview

This tool provides a simple way to schedule and send Telegram messages from the command line, useful for reminders and alerts during interactive sessions.

## Use Cases

- **Quick reminders**: Set timers for meetings, tasks
- **Alerts**: Send notifications from scripts
- **Integration**: Use with other tools for failure alerts

## Quickstart

### Configuration

Add to `~/AGENTS.env`:
```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321
```

### Basic Usage

```bash
# Send in 5 minutes
./src/tele-remind.sh 5m 'Meeting starting'

# Send at specific time
./src/tele-remind.sh 2025-01-15T14:00 'Call John'

# Immediate send via curl
source ~/AGENTS.env
curl -sS -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  --data-urlencode chat_id="$TELEGRAM_CHAT_ID" \
  --data-urlencode text='Hello!'
```

## Examples

### Duration-Based Reminders

```bash
# 30 seconds
./src/tele-remind.sh 30s 'Quick check'

# 5 minutes
./src/tele-remind.sh 5m 'Stand up!'

# 1 hour
./src/tele-remind.sh 1h 'Lunch time'

# Combined
./src/tele-remind.sh 1h30m 'End of focus block'
```

### Time-Based Reminders

```bash
# Specific time (local timezone)
./src/tele-remind.sh 2025-01-15T09:00 'Morning standup'

# With seconds
./src/tele-remind.sh 2025-01-15T14:30:00 'Afternoon meeting'
```

### Shell Alias

Add to `~/.zshrc`:
```bash
alias teleremind='~/.codex/tools/telegram/tele-remind.sh'
# Or point to new location
alias teleremind='/path/to/felix_tools/tools/telegram-cli/src/tele-remind.sh'
```

Then use:
```bash
teleremind 5m 'Check email'
```

## How It Works

1. Parses duration (e.g., `5m`) or ISO time
2. Calculates seconds until target time
3. Spawns background process with `sleep`
4. After delay, sends via Telegram Bot API
5. Process survives shell (via `nohup`)

## Notes

- **Session-scoped**: Reminders run in background but don't survive logout/reboot
- **For durable scheduling**: Use `launchd` on macOS instead
- **Why not `at`?**: On macOS, `at` relies on `atrun` which may not be active. Background sleep is more reliable in interactive shells.

See [CONFIG.md](CONFIG.md) for configuration details.

