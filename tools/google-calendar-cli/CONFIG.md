# Config – google-calendar-cli

## Environment Variables

### Required

- `GOOGLE_OAUTH_CLIENT_ID`  
  OAuth client ID from Google Cloud Console (Desktop app).

- `GOOGLE_OAUTH_CLIENT_SECRET`  
  OAuth client secret.

- `GOOGLE_OAUTH_REFRESH_TOKEN`  
  Set after running `gcal.py auth`.

### Optional

- `GCAL_SCOPES`  
  Space-separated scopes. Default: `https://www.googleapis.com/auth/calendar` (read/write).  
  Use `https://www.googleapis.com/auth/calendar.readonly` for read-only.

- `TELEGRAM_BOT_TOKEN`  
  Bot token for failure notifications.

- `TELEGRAM_CHAT_ID`  
  Chat ID for notifications.

## Configuration File

All environment variables are loaded from `~/AGENTS.env`.

## Example ~/AGENTS.env

```bash
# Google OAuth
GOOGLE_OAUTH_CLIENT_ID=123456789-abc.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-your-secret-here
GOOGLE_OAUTH_REFRESH_TOKEN=1//your-refresh-token

# Optional: Calendar scope override
# GCAL_SCOPES=https://www.googleapis.com/auth/calendar.readonly

# Telegram notifications
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321
```

## Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable **Google Calendar API**
4. Create OAuth credentials:
   - Application type: Desktop app
   - Download or copy Client ID and Secret
5. Run `gcal.py auth` to get refresh token

## Permissions

The OAuth token requires:
- `calendar` scope for read/write
- `calendar.readonly` scope for read-only

## External Dependencies

- Google Calendar API
- Google People API (for Contacts label attendees)

