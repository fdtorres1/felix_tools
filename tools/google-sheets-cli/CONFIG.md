# Config – google-sheets-cli

## Environment Variables

### Required

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REFRESH_TOKEN`

### Optional

- `GSHEETS_SCOPES`  
  Default: `https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive`

- `SHEETS_DEFAULT_SPREADSHEET_ID`  
  Default spreadsheet for operations

- `SHEETS_DEFAULT_WORKSHEET`  
  Default tab name

- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`

## Example ~/AGENTS.env

```bash
GOOGLE_OAUTH_CLIENT_ID=123456789-abc.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-your-secret
GOOGLE_OAUTH_REFRESH_TOKEN=1//your-refresh-token
SHEETS_DEFAULT_SPREADSHEET_ID=1Vr_E3S5NwjK3Avos...
```

