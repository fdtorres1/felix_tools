# Config – givebutter-cli

## Environment Variables

The `givebutter-cli` tool relies on the following environment variables, typically set in `~/AGENTS.env`.

### Required

*   `GIVEBUTTER_API_KEY` (required): Your Givebutter API key.
    - Obtain from: [Givebutter Dashboard](https://dashboard.givebutter.com) → Settings → API
    - Also accepts: `GIVEBUTTER_TOKEN` as an alias

### Optional

*   `AGENTS_ENV_PATH` (optional): Path to an alternative `.env` file if not `~/AGENTS.env`.

*   `TELEGRAM_BOT_TOKEN` (optional): Bot token for sending Telegram notifications on errors.

*   `TELEGRAM_CHAT_ID` (optional): Your Telegram chat ID for receiving notifications.

## API Details

*   **Base URL**: `https://api.givebutter.com/v1`
*   **Authentication**: Bearer token via `Authorization: Bearer {api_key}` header
*   **Rate Limits**: Standard API rate limits apply (see Givebutter documentation)
*   **HTTPS Required**: All API requests must use HTTPS

## Obtaining Your API Key

1.  Log in to your [Givebutter Dashboard](https://dashboard.givebutter.com)
2.  Navigate to **Settings** (gear icon)
3.  Select **API** from the menu
4.  Click **Generate API Key** or copy your existing key
5.  Add to your environment:
    ```bash
    export GIVEBUTTER_API_KEY="your-api-key-here"
    ```

## Example Configuration

Add to your `~/AGENTS.env`:

```bash
# Givebutter API
export GIVEBUTTER_API_KEY="your-api-key-here"

# Optional: Default campaign for transactions
# export GIVEBUTTER_DEFAULT_CAMPAIGN="YOUR_CAMPAIGN_CODE"

# Optional: Telegram notifications
# export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
# export TELEGRAM_CHAT_ID="your-chat-id"
```

## API Endpoints Used

| Resource     | Endpoints                                           |
|--------------|-----------------------------------------------------|
| Campaigns    | GET, POST, PATCH, DELETE `/campaigns`               |
| Contacts     | GET, POST, PATCH, DELETE `/contacts`                |
| Transactions | GET, POST `/transactions`                           |
| Funds        | GET, POST, PATCH, DELETE `/funds`                   |
| Plans        | GET `/plans`                                        |
| Payouts      | GET `/payouts`                                      |
| Tickets      | GET `/tickets`                                      |
| Members      | GET, DELETE `/campaigns/{id}/members`               |
| Teams        | GET `/campaigns/{id}/teams`                         |

## Permissions

The API key provides access based on your Givebutter account permissions. Ensure your account has appropriate access to the resources you intend to manage.

## Security Notes

*   Never commit API keys to version control
*   Use environment variables or secure secret management
*   The API key provides full access to your Givebutter account – treat it like a password
*   Rotate keys periodically and revoke unused keys

