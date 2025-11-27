# Architecture Overview

This document describes the high-level architecture, shared patterns, and conventions used across tools in this monorepo.

## Design Principles

1. **Standalone tools** – Each tool is independent and self-contained
2. **Consistent CLI patterns** – Similar argument styles across tools
3. **Dry-run by default for mutations** – Preview before applying changes
4. **Centralized configuration** – `~/AGENTS.env` for all credentials
5. **Graceful failure** – Clear error messages, optional Telegram alerts

## Shared Patterns

### Configuration Loading

All tools auto-load environment variables from `~/AGENTS.env`:

```python
def load_agents_env(path=None):
    env_path = path or os.environ.get("AGENTS_ENV_PATH", os.path.expanduser("~/AGENTS.env"))
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")
```

### Telegram Notifications

Tools can optionally notify via Telegram on failures:

```python
def notify_telegram(msg: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": msg[:3900]}, timeout=10)
    except Exception:
        pass
```

### Dry-Run Mode

All mutating operations support `--dry-run`:

```python
if args.dry_run:
    print(json.dumps({"dry_run": True, "would_create": body}, indent=2))
    return 0
# Otherwise, execute the mutation
```

### JSON Output

Tools output JSON for programmatic consumption:

```python
print(json.dumps(result, indent=2))
```

## Tool Categories

### Google Workspace Tools

- **google-calendar-cli**: Events, free/busy, recurring events
- **google-contacts-cli**: Contacts, groups (labels)
- **google-docs-cli**: Read, append, insert headings/tables
- **google-gmail-cli**: Send, reply, drafts, labels, scheduled queue
- **google-sheets-cli**: Read, append, update cells

All use OAuth with a shared refresh token pattern. Scopes are configurable per tool.

### Task Management Tools

- **clickup-cli**: Teams, spaces, lists, tasks, bulk operations
- **linear-cli**: Issues, labels, comments via GraphQL

### Calendar Tools

- **google-calendar-cli**: Google Calendar (see above)
- **eventkit-calendar**: macOS native calendar via EventKit (Swift)

### E-commerce Tools

- **shopify-cli**: Products, customers, orders, metafields, collections

### Communication Tools

- **google-gmail-cli**: Email (see above)
- **telegram-cli**: One-off reminders and scheduled notifications

## Authentication Patterns

### OAuth (Google Tools)

1. Run `<tool>.py auth` to initiate OAuth flow
2. Browser opens for consent
3. Tool prints `GOOGLE_OAUTH_REFRESH_TOKEN`
4. Append to `~/AGENTS.env`

Shared credentials:
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REFRESH_TOKEN`

### API Tokens

- **ClickUp**: `CLICKUP_API_TOKEN`
- **Linear**: `LINEAR_AGENT_TOKEN`
- **Shopify**: `SHOPIFY_ADMIN_TOKEN` + `SHOPIFY_SHOP`
- **Telegram**: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`

## Error Handling

1. **Validation errors**: Exit with code 2 and clear message
2. **API errors**: Log status and response, optionally notify Telegram
3. **Network errors**: Retry with exponential backoff where appropriate

## Language Choices

| Language | Use Case |
|----------|----------|
| Python | API integrations, complex CLI tools |
| Bash | Simple GraphQL wrappers, quick scripts |
| Swift | macOS-specific APIs (EventKit) |

## Dependencies

Python tools share a common `requirements.txt`:

```
google-api-python-client>=2.131.0
google-auth>=2.34.0
google-auth-oauthlib>=1.2.1
requests>=2.32.3
```

Install once in a shared venv:
```bash
python3 -m venv ~/.venvs/felix-tools
source ~/.venvs/felix-tools/bin/activate
pip install -r tools/shared-requirements.txt
```

