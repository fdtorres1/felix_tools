# Tools Overview

Complete catalog of all tools in this monorepo.

## Tool Index

| Tool | Path | Description | Language | Status |
|------|------|-------------|----------|--------|
| clickup-cli | `tools/clickup-cli/` | ClickUp task management | Python | ✅ Active |
| eventkit-calendar | `tools/eventkit-calendar/` | macOS Calendar (EventKit) | Swift | ✅ Active |
| givebutter-cli | `tools/givebutter-cli/` | Givebutter nonprofit fundraising | Python | ✅ Active |
| google-calendar-cli | `tools/google-calendar-cli/` | Google Calendar management | Python | ✅ Active |
| handwrytten-cli | `tools/handwrytten-cli/` | Handwrytten handwritten cards | Python | ✅ Active |
| google-contacts-cli | `tools/google-contacts-cli/` | Google Contacts management | Python | ✅ Active |
| google-docs-cli | `tools/google-docs-cli/` | Google Docs operations | Python | ✅ Active |
| google-gmail-cli | `tools/google-gmail-cli/` | Gmail with scheduled sends | Python | ✅ Active |
| google-sheets-cli | `tools/google-sheets-cli/` | Google Sheets operations | Python | ✅ Active |
| linear-cli | `tools/linear-cli/` | Linear issue tracking | Bash | ✅ Active |
| shopify-cli | `tools/shopify-cli/` | Shopify Admin GraphQL | Python | ✅ Active |
| telegram-cli | `tools/telegram-cli/` | Telegram notifications | Bash | ✅ Active |

## Quick Reference

### ClickUp CLI

```bash
# List teams
clickup.py teams

# Search tasks
clickup.py tasks search --team <TEAM_ID> --query 'keyword'

# Create task
clickup.py task create --list <LIST_ID> --name 'Title' --dry-run
```

### EventKit Calendar

```bash
# List calendars
ekcal calendars

# Today's events
ekcal events list --today --calendars 'Personal,Work'

# Send daily digest to Telegram
ekcal digest --day today
```

### Givebutter CLI

```bash
# List campaigns
givebutter.py campaigns list

# List transactions with all pages
givebutter.py transactions list --all-pages --format csv

# Create offline donation (record-keeping)
givebutter.py transactions create --campaign CODE --method check --amount 100 --first-name 'Jane' --email 'jane@example.com' --dry-run

# Bulk import from JSONL
givebutter.py transactions import donations.jsonl --campaign CODE --dry-run
```

### Google Calendar CLI

```bash
# List calendars
gcal.py calendars

# Create event
gcal.py events create --calendar primary --summary 'Meeting' --start 2025-01-15T10:00:00-06:00 --end 2025-01-15T11:00:00-06:00

# Bulk create from file
gcal.py events bulk-create --file events.jsonl --dry-run
```

### Handwrytten CLI

```bash
# List available cards
handwrytten.py cards list --with-images

# List fonts (handwriting styles)
handwrytten.py fonts list

# Send a card
handwrytten.py orders send --card-id 3404 --message 'Dear John,\n\nThank you!' --wishes 'Best regards' --recipient-name 'John Doe' --recipient-address1 '123 Main St' --recipient-city 'Phoenix' --recipient-state 'AZ' --recipient-zip '85001'

# Get order status
handwrytten.py orders get --order-id 12345
```

### Google Contacts CLI

```bash
# List contacts
gcontacts.py list --fields names,emailAddresses

# Search
gcontacts.py search --query 'john' --fields names,emailAddresses

# Get emails from a group
gcontacts.py groups emails --group 'My Label'
```

### Google Docs CLI

```bash
# Read document
gdocs.py get --document <DOC_ID> --as text

# Append text
gdocs.py append --document <DOC_ID> --text 'New content'

# Insert heading
gdocs.py insert-heading --document <DOC_ID> --text 'Section' --level 2
```

### Gmail CLI

```bash
# Send email
gmail.py send --to 'user@example.com' --subject 'Hello' --text 'Body' --dry-run

# Reply to message
gmail.py reply --id <MSG_ID> --text 'Thanks!' --dry-run

# Queue scheduled send
gmail.py queue add --to 'user@example.com' --subject 'Hi' --text 'Body' --send-at '2025-01-15T09:00:00-06:00'
```

### Google Sheets CLI

```bash
# Read range
gsheets.py read --spreadsheet <ID> --range 'Sheet1!A1:D10'

# Append row
gsheets.py append --spreadsheet <ID> --range 'Sheet1!A:Z' --values '["a","b","c"]'

# Create new spreadsheet
gsheets.py create-sheet --title 'My Sheet'
```

### Linear CLI

```bash
# Source the helper
source linear.sh

# List teams
li_teams

# Search issues
li_issues_find --title-contains 'bug' --team TEAM_KEY

# Create issue (dry-run by default)
li_issue_create --team-id <ID> --title 'New issue'
```

### Shopify CLI

```bash
# Auth check
shopify.py auth

# List products
shopify.py products list --query 'vendor:Acme' --csv /tmp/products.csv

# Get orders
shopify.py orders list --query 'tag:VIP' --jsonl /tmp/orders.jsonl
```

### Telegram CLI

```bash
# Send reminder in 5 minutes
teleremind 5m 'Meeting starting'

# Send at specific time
teleremind 2025-01-15T14:00 'Call John'
```

## Environment Setup

All tools read from `~/AGENTS.env`. Example:

```bash
# Google OAuth
GOOGLE_OAUTH_CLIENT_ID=your-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
GOOGLE_OAUTH_REFRESH_TOKEN=your-refresh-token

# ClickUp
CLICKUP_API_TOKEN=your-token

# Givebutter
GIVEBUTTER_API_KEY=your-api-key

# Handwrytten
HANDWRYTTEN_API_KEY=your-api-key

# Linear
LINEAR_AGENT_TOKEN=lin_oauth_...

# Shopify
SHOPIFY_SHOP=myshop.myshopify.com
SHOPIFY_ADMIN_TOKEN=your-admin-token

# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

## Contact

- **Owner**: Felix Torres
- **Email**: felix@caminosdelinka.org

