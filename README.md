# Felix Tools Monorepo

A collection of CLI tools for productivity, automation, and API integrations.

## Overview

This monorepo contains various tools for managing:
- **Task Management**: ClickUp, Linear
- **Calendar**: Google Calendar, macOS EventKit
- **Email & Communication**: Gmail, Telegram
- **E-commerce**: Shopify Admin API
- **Documents & Data**: Google Docs, Google Sheets, Google Contacts

## Repository Structure

```
.
├── AGENTS.md              # How work is organized (for humans and Cursor)
├── README.md              # This file
├── CONTRIBUTING.md        # Contribution guidelines
├── docs/
│   ├── architecture.md    # High-level architecture and conventions
│   └── tools-overview.md  # Catalog of all tools
├── tools/
│   ├── clickup-cli/       # ClickUp task management CLI
│   ├── eventkit-calendar/ # macOS Calendar (EventKit) CLI
│   ├── google-calendar-cli/   # Google Calendar CLI
│   ├── google-contacts-cli/   # Google Contacts CLI
│   ├── google-docs-cli/   # Google Docs CLI
│   ├── google-gmail-cli/  # Gmail CLI with scheduled sends
│   ├── google-sheets-cli/ # Google Sheets CLI
│   ├── linear-cli/        # Linear issue tracking CLI
│   ├── shopify-cli/       # Shopify Admin GraphQL CLI
│   └── telegram-cli/      # Telegram notifications CLI
└── scripts/               # Shared helper scripts
```

## Quick Start

### Prerequisites

- Python 3.9+ (for Python-based tools)
- Swift (for EventKit calendar on macOS)
- `jq` and `curl` (for shell-based tools)

### Setup

1. Create a shared virtual environment:
   ```bash
   python3 -m venv ~/.venvs/felix-tools
   source ~/.venvs/felix-tools/bin/activate
   pip install -r tools/shared-requirements.txt
   ```

2. Configure environment variables in `~/AGENTS.env`:
   ```bash
   # Copy the example and fill in your values
   cp tools/<tool-name>/.env.example ~/AGENTS.env
   ```

3. Each tool auto-loads `~/AGENTS.env` on startup.

## Tools

| Tool | Description | Language |
|------|-------------|----------|
| [clickup-cli](tools/clickup-cli/) | ClickUp task management | Python |
| [eventkit-calendar](tools/eventkit-calendar/) | macOS Calendar (EventKit) | Swift |
| [google-calendar-cli](tools/google-calendar-cli/) | Google Calendar management | Python |
| [google-contacts-cli](tools/google-contacts-cli/) | Google Contacts management | Python |
| [google-docs-cli](tools/google-docs-cli/) | Google Docs operations | Python |
| [google-gmail-cli](tools/google-gmail-cli/) | Gmail with scheduled sends | Python |
| [google-sheets-cli](tools/google-sheets-cli/) | Google Sheets operations | Python |
| [linear-cli](tools/linear-cli/) | Linear issue tracking | Bash |
| [shopify-cli](tools/shopify-cli/) | Shopify Admin GraphQL | Python |
| [telegram-cli](tools/telegram-cli/) | Telegram notifications | Bash |

## Documentation

- [AGENTS.md](AGENTS.md) – How work is organized
- [CONTRIBUTING.md](CONTRIBUTING.md) – Contribution guidelines
- [docs/architecture.md](docs/architecture.md) – Architecture overview
- [docs/tools-overview.md](docs/tools-overview.md) – Complete tools catalog

## License

Private repository. All rights reserved.

