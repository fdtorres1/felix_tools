# Config – telegram-cli

## Environment Variables

### Required

- `TELEGRAM_BOT_TOKEN`  
  Bot token from @BotFather

- `TELEGRAM_CHAT_ID`  
  Your user or group chat ID

## Configuration File

Environment variables are loaded from `~/AGENTS.env`.

## Example ~/AGENTS.env

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321
```

## Getting Bot Token

1. Message @BotFather on Telegram
2. Send `/newbot`
3. Follow prompts to name your bot
4. Copy the token provided

## Getting Chat ID

1. Message your bot
2. Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Find your chat ID in the response

