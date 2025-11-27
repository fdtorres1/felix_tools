# Config – eventkit-calendar

## Environment Variables

### Calendar Selection

- `INCLUDE_CALENDAR_IDS`  
  Comma-separated EventKit calendar IDs (preferred for reliability).

- `INCLUDE_CALENDARS`  
  Comma-separated calendar titles (fallback if IDs not set).  
  Note: Titles may be ambiguous across sources (iCloud, Google, Exchange).

### Telegram (Optional)

- `TELEGRAM_BOT_TOKEN`  
  Bot token from @BotFather for sending digests.

- `TELEGRAM_CHAT_ID`  
  Your Telegram chat ID for receiving digests.

## Configuration File

Environment variables are loaded from `~/AGENTS.env`.

## Example ~/AGENTS.env

```bash
# Calendar selection (prefer IDs)
INCLUDE_CALENDAR_IDS=1A2B3C4D-5E6F-7890-ABCD-EF1234567890,ANOTHER-ID-HERE
# Or use names
INCLUDE_CALENDARS=Personal,Work,Family

# Telegram for digests
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321
```

## System Requirements

- macOS 12+ (Monterey or later)
- Calendar access permission (granted on first run)
- Swift runtime (included in macOS)

## Permissions

On first run, macOS will prompt for Calendar access. Grant permission in:
System Preferences → Security & Privacy → Privacy → Calendars

## Finding Calendar IDs

```bash
# List all calendars with IDs
ekcal calendars | jq '.calendars[] | {title, id}'
```

