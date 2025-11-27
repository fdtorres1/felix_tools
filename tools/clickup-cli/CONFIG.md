# Config – clickup-cli

## Environment Variables

### Required

- `CLICKUP_API_TOKEN` (or `CLICKUP_TOKEN`)  
  Personal API token from ClickUp Settings → Apps → API Token.

### Optional

- `CLICKUP_DEFAULT_TEAM_ID`  
  Default team (workspace) ID. Eliminates need for `--team` flag.

- `CLICKUP_DEFAULT_LIST_ID`  
  Default list ID for create/update operations.

### Notifications (Optional)

- `TELEGRAM_BOT_TOKEN`  
  Bot token from @BotFather for failure notifications.

- `TELEGRAM_CHAT_ID`  
  Your Telegram chat ID for notifications.

## Configuration File

All environment variables are loaded from `~/AGENTS.env` by default.

You can override with `--env /path/to/other.env`.

## Example ~/AGENTS.env

```bash
# ClickUp
CLICKUP_API_TOKEN=pk_12345678_ABCDEFGHIJKLMNOP
CLICKUP_DEFAULT_TEAM_ID=1234567
CLICKUP_DEFAULT_LIST_ID=987654

# Notifications (optional)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321
```

## External Dependencies

- **ClickUp API v2**: `https://api.clickup.com/api/v2`
- **Telegram Bot API**: For notifications (optional)

## Permissions

The ClickUp API token requires:
- Read access to teams, spaces, folders, lists
- Write access to tasks (create, update, delete)
- Write access to comments and tags

## Rate Limits

ClickUp API has rate limits. The tool does not auto-throttle; add delays in batch scripts if needed.

