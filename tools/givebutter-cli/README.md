# Givebutter CLI

A command-line interface for the [Givebutter API](https://docs.givebutter.com/reference/reference-getting-started), enabling nonprofit organizations to manage campaigns, contacts, transactions, funds, and more directly from the terminal.

## 1. Overview

*   **Purpose**: Automate Givebutter fundraising operations via CLI – perfect for data imports, reporting, and integration with other tools.
*   **Capabilities**:
    *   **Campaigns**: List, get, create, update, delete campaigns
    *   **Contacts**: List, search, create, update, archive, restore donor contacts
    *   **Transactions**: List, get, create (record-keeping for offline donations), bulk import
    *   **Funds**: List, get, create, update, delete designated funds
    *   **Plans**: List and view recurring donation plans
    *   **Payouts**: List and view payout details
    *   **Tickets**: List and view event tickets
    *   **Members**: List, get, delete campaign fundraising members
    *   **Teams**: List and view campaign peer-to-peer teams
*   **Output Formats**: JSON (default), JSONL, CSV
*   **Notifications**: Optional Telegram and macOS alerts

## 2. Quickstart

### 2.1 Installation

1.  **Activate Virtual Environment**:
    ```bash
    source ~/.venvs/codex-tools/bin/activate
    ```

2.  **Dependencies**: This tool uses only Python standard library modules (`urllib`, `json`, `argparse`). No additional packages required.

### 2.2 Authentication

1.  **Get API Key**: 
    - Log in to your [Givebutter Dashboard](https://dashboard.givebutter.com)
    - Navigate to **Settings → API**
    - Generate or copy your API key

2.  **Set Environment Variable** in `~/AGENTS.env`:
    ```bash
    export GIVEBUTTER_API_KEY="your-api-key-here"
    ```

3.  **Source Environment**:
    ```bash
    source ~/AGENTS.env
    ```

### 2.3 Basic Usage

**List all campaigns:**
```bash
python3 src/givebutter.py campaigns list
```

**Get a specific campaign:**
```bash
python3 src/givebutter.py campaigns get CAMPAIGN_CODE
```

**List transactions with pagination:**
```bash
python3 src/givebutter.py transactions list --all-pages --format csv
```

**Create an offline transaction (record-keeping):**
```bash
python3 src/givebutter.py transactions create \
  --campaign YOUR_CAMPAIGN \
  --method check \
  --amount 500.00 \
  --first-name "Jane" \
  --last-name "Doe" \
  --email "jane@example.com" \
  --captured-at "2025-11-01T00:00:00Z" \
  --dry-run
```

**Bulk import transactions from JSONL:**
```bash
python3 src/givebutter.py transactions import donations.jsonl --campaign YOUR_CAMPAIGN --dry-run
```

**Export contacts to CSV:**
```bash
python3 src/givebutter.py contacts list --all-pages --format csv > contacts.csv
```

## 3. Commands Reference

### Campaigns
```bash
givebutter.py campaigns list [--limit N] [--all-pages] [--format json|jsonl|csv]
givebutter.py campaigns get <id>
givebutter.py campaigns create --title "Title" [--type standard|event|membership] [--goal 5000] [--dry-run]
givebutter.py campaigns update <id> [--title "New Title"] [--goal 10000] [--status active|closed] [--dry-run]
givebutter.py campaigns delete <id> [--dry-run]
```

### Contacts
```bash
givebutter.py contacts list [--email filter] [--all-pages] [--format json|jsonl|csv]
givebutter.py contacts get <id>
givebutter.py contacts create --email "email@example.com" [--first-name "First"] [--last-name "Last"] [--dry-run]
givebutter.py contacts update <id> [--email "new@example.com"] [--first-name "New"] [--dry-run]
givebutter.py contacts archive <id> [--dry-run]
givebutter.py contacts restore <id> [--dry-run]
```

### Transactions
```bash
givebutter.py transactions list [--campaign CODE] [--contact ID] [--status succeeded|pending|failed] [--all-pages]
givebutter.py transactions get <id>
givebutter.py transactions create --campaign CODE --method check --amount 100 [--first-name "Name"] [--dry-run]
givebutter.py transactions import <file.jsonl> [--campaign CODE] [--dry-run]
```

### Funds
```bash
givebutter.py funds list [--all-pages] [--format json|jsonl|csv]
givebutter.py funds get <id>
givebutter.py funds create --title "Fund Name" [--description "..."] [--goal 10000] [--dry-run]
givebutter.py funds update <id> [--title "New Name"] [--dry-run]
givebutter.py funds delete <id> [--dry-run]
```

### Plans (Recurring Donations)
```bash
givebutter.py plans list [--status active|paused|cancelled] [--all-pages]
givebutter.py plans get <id>
```

### Payouts
```bash
givebutter.py payouts list [--all-pages] [--format json|jsonl|csv]
givebutter.py payouts get <id>
```

### Tickets
```bash
givebutter.py tickets list [--campaign CODE] [--all-pages]
givebutter.py tickets get <id>
```

### Members (Peer-to-Peer Fundraisers)
```bash
givebutter.py members list --campaign CODE [--all-pages]
givebutter.py members get --campaign CODE <id>
givebutter.py members delete --campaign CODE <id> [--dry-run]
```

### Teams (P2P Teams)
```bash
givebutter.py teams list --campaign CODE [--all-pages]
givebutter.py teams get --campaign CODE <id>
```

## 4. Bulk Import Format

For `transactions import`, prepare a JSONL file (one JSON object per line):

```jsonl
{"first_name": "John", "last_name": "Doe", "email": "john@example.com", "amount": 100, "method": "check", "captured_at": "2025-01-15"}
{"first_name": "Jane", "last_name": "Smith", "email": "jane@example.com", "amount": 250, "method": "donor_advised_fund", "note": "Via Fidelity DAF"}
```

**Supported `method` values:**
- `cash`
- `check`
- `wire_transfer`
- `donor_advised_fund`
- `stock`
- `cryptocurrency`
- `other`

## 5. Configuration

See `CONFIG.md` for environment variables and setup details.

## 6. Design

See `DESIGN.md` for architecture and implementation details.

## 7. Changelog

See `CHANGELOG.md` for version history.

---

**API Documentation**: https://docs.givebutter.com/reference/reference-getting-started

