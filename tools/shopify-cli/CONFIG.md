# Config – shopify-cli

## Environment Variables

### Required

- `SHOPIFY_SHOP`  
  Your Shopify store domain (e.g., `myshop.myshopify.com`)

- `SHOPIFY_ADMIN_TOKEN`  
  Admin API access token from a custom app

### Optional

- `SHOPIFY_API_VERSION`  
  API version to use. Default: `2024-07`

- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`  
  For failure notifications

## Configuration File

Environment variables are loaded from `~/AGENTS.env`.

## Example ~/AGENTS.env

```bash
SHOPIFY_SHOP=mystore.myshopify.com
SHOPIFY_ADMIN_TOKEN=shpat_abc123def456...
SHOPIFY_API_VERSION=2024-07
```

## Getting an Admin Token

1. Go to Shopify Admin → Settings → Apps and sales channels
2. Click "Develop apps" → "Create an app"
3. Configure Admin API scopes (read/write access needed)
4. Install the app
5. Copy the Admin API access token

## Required Scopes

Depending on operations, you may need:
- `read_products`, `write_products`
- `read_customers`
- `read_orders`, `write_orders`
- `read_content`, `write_content`
- `read_metaobjects`, `write_metaobjects`

