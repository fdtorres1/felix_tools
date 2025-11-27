# Config – google-contacts-cli

## Environment Variables

### Required

- `GOOGLE_OAUTH_CLIENT_ID`  
  OAuth client ID from Google Cloud Console.

- `GOOGLE_OAUTH_CLIENT_SECRET`  
  OAuth client secret.

- `GOOGLE_OAUTH_REFRESH_TOKEN`  
  Set after running `gcontacts.py auth`.

### Optional

- `GCONTACTS_SCOPES`  
  Override default scopes. Default: `https://www.googleapis.com/auth/contacts` (read/write).  
  Use `https://www.googleapis.com/auth/contacts.readonly` for read-only.

- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`  
  For failure notifications.

## Configuration File

All environment variables are loaded from `~/AGENTS.env`.

## Example ~/AGENTS.env

```bash
GOOGLE_OAUTH_CLIENT_ID=123456789-abc.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-your-secret
GOOGLE_OAUTH_REFRESH_TOKEN=1//your-refresh-token
```

## Google Cloud Setup

1. Enable **People API** in Google Cloud Console
2. Use same OAuth credentials as other Google tools
3. Run `gcontacts.py auth` to add Contacts scope

