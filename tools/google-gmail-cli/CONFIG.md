# Config – google-gmail-cli

## Environment Variables

### Required

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REFRESH_TOKEN`

### Optional

- `GMAIL_SCOPES`  
  Default includes: `gmail.readonly`, `gmail.send`, `gmail.modify`, `gmail.settings.basic`, `contacts.readonly`

- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`  
  For failure notifications on scheduled sends

## Queue Configuration

The outbox queue stores pending emails in `~/.codex/tools/gmail_outbox/`:
- `queue.jsonl` - Pending emails
- `history.jsonl` - Sent/failed history
- `dispatch.log` - LaunchAgent logs

## LaunchAgent Setup

Create `~/Library/LaunchAgents/com.fdtorres.gmail.outbox.dispatch.plist` for automatic dispatch.

## Example ~/AGENTS.env

```bash
GOOGLE_OAUTH_CLIENT_ID=123456789-abc.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-your-secret
GOOGLE_OAUTH_REFRESH_TOKEN=1//your-refresh-token

# For queue failure alerts
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjkl
TELEGRAM_CHAT_ID=987654321
```

