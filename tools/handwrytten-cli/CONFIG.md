# Config – handwrytten-cli

## Environment Variables

### Required

- `HANDWRYTTEN_API_KEY` (required): API key for authenticating with the Handwrytten API. Obtain from [app.handwrytten.com](https://app.handwrytten.com) → Integrations menu.

### Optional

- `HANDWRYTTEN_API_URL` (optional): Base URL for the Handwrytten API. Defaults to `https://api.handwrytten.com/v2`.

- `HANDWRYTTEN_TEST_MODE` (optional): Set to `true` to enable test/sandbox mode. In test mode, orders are created but not actually sent. Defaults to `false`.

## Configuration File

The tool reads configuration from a `.env` file in the tool directory. See `env.example` for a template.

```bash
# Copy the example and edit with your values
cp env.example .env
```

## Default Sender Information

For convenience, you can set default sender information in the environment:

- `HANDWRYTTEN_SENDER_NAME` (optional): Default sender name for cards
- `HANDWRYTTEN_SENDER_ADDRESS1` (optional): Default sender address line 1
- `HANDWRYTTEN_SENDER_ADDRESS2` (optional): Default sender address line 2
- `HANDWRYTTEN_SENDER_CITY` (optional): Default sender city
- `HANDWRYTTEN_SENDER_STATE` (optional): Default sender state
- `HANDWRYTTEN_SENDER_ZIP` (optional): Default sender ZIP code
- `HANDWRYTTEN_SENDER_COUNTRY` (optional): Default sender country (defaults to "United States")

## External Dependencies

- **Handwrytten API v2**: REST API at `https://api.handwrytten.com/v2`
  - Rate limits: Contact Handwrytten for specific limits
  - Authentication: API key in Authorization header
  - Documentation: [https://www.handwrytten.com/api/](https://www.handwrytten.com/api/)

## Permissions Required

- Valid Handwrytten account with API access enabled
- Credit card on file or invoicing arrangement for sending cards
- For test mode: Account set to test mode in Handwrytten dashboard

