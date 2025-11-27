# Config – google-docs-cli

## Environment Variables

### Required

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REFRESH_TOKEN`

### Optional

- `GDOCS_SCOPES`  
  Default: `https://www.googleapis.com/auth/documents https://www.googleapis.com/auth/drive`

- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`

## Example ~/AGENTS.env

```bash
GOOGLE_OAUTH_CLIENT_ID=123456789-abc.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-your-secret
GOOGLE_OAUTH_REFRESH_TOKEN=1//your-refresh-token
```

