# Design – givebutter-cli

## 1. Problem Statement

Nonprofit organizations using Givebutter often need to:
- Import historical donation data from other platforms or offline sources
- Export donor and transaction data for reporting and analysis
- Automate campaign management tasks
- Integrate Givebutter with other systems (CRM, accounting, etc.)

The web dashboard is great for daily operations but insufficient for bulk operations, data migrations, or automated workflows. A CLI tool bridges this gap.

## 2. High-Level Approach

The `givebutter-cli` is a Python-based command-line utility that wraps the [Givebutter REST API (v1)](https://docs.givebutter.com/reference/reference-getting-started). Key design goals:

*   **Zero Dependencies**: Uses only Python standard library (`urllib`, `json`, `argparse`) for maximum portability
*   **Familiar Patterns**: Follows the same CLI structure as other tools in this monorepo
*   **Comprehensive Coverage**: Supports all major Givebutter API endpoints
*   **Safe Operations**: Dry-run mode for all mutations, confirmation for destructive actions
*   **Flexible Output**: JSON, JSONL, and CSV formats for integration flexibility

## 3. Architecture

```
givebutter-cli/
├── src/
│   └── givebutter.py       # Main CLI (single-file, no external deps)
├── scripts/                # Entrypoint symlinks
├── tests/                  # Unit and integration tests
├── docs/                   # Additional documentation
├── README.md               # Tool overview and quickstart
├── CHANGELOG.md            # Version history
├── CONFIG.md               # Environment variables
├── DESIGN.md               # This document
└── env.example             # Example environment file
```

### 3.1 Core Components

*   **Configuration Loading** (`load_agents_env()`):
    - Reads `~/AGENTS.env` or path from `AGENTS_ENV_PATH`
    - Handles both `VAR=value` and `export VAR=value` syntax
    - Does not override existing environment variables

*   **HTTP Layer** (`http_get`, `http_post`, `http_patch`, `http_delete`):
    - Wraps `urllib.request` for API communication
    - Handles JSON serialization/deserialization
    - Includes error handling with meaningful messages
    - Triggers notifications on failures

*   **Pagination** (`paginate_all()`):
    - Automatically fetches all pages when `--all-pages` flag is used
    - Handles Givebutter's cursor-based pagination
    - Returns aggregated results

*   **Output Formatters** (`output_json`, `output_jsonl`, `output_csv`):
    - JSON: Pretty-printed by default, suitable for human reading
    - JSONL: One record per line, suitable for streaming/processing
    - CSV: Tabular format with customizable columns

*   **Notification Helpers**:
    - `notify_telegram()`: Sends alerts via Telegram Bot API
    - `notify_macos()`: Desktop notifications via `terminal-notifier`

### 3.2 Command Structure

```
givebutter.py <resource> <action> [options]
```

Resources: `campaigns`, `contacts`, `transactions`, `funds`, `plans`, `payouts`, `tickets`, `members`, `teams`

Actions vary by resource but typically include: `list`, `get`, `create`, `update`, `delete`

### 3.3 Data Flow

1. **CLI Invocation**: User runs command with arguments
2. **Environment Loading**: `load_agents_env()` loads API key
3. **Argument Parsing**: `argparse` validates and parses input
4. **API Request**: HTTP helper constructs and sends request
5. **Response Processing**: JSON response is parsed
6. **Output Formatting**: Results formatted per user preference
7. **Error Handling**: Failures trigger notifications and appropriate exit codes

## 4. Key Design Decisions

### 4.1 Zero External Dependencies

**Decision**: Use only Python standard library.

**Rationale**: 
- Maximizes portability (works with any Python 3.x installation)
- Reduces installation friction
- Avoids dependency conflicts
- The Givebutter API is straightforward REST/JSON, not requiring complex HTTP client features

**Trade-off**: Manual JSON handling and less elegant HTTP code, but the simplicity benefit outweighs this.

### 4.2 Transaction Creation is Record-Keeping Only

**Decision**: The `transactions create` command creates records for offline donations, not actual charges.

**Rationale**: Per [Givebutter API docs](https://docs.givebutter.com/reference/create-a-transaction):
> "Creating transactions via this endpoint allows you to create a record for transactions collected outside of Givebutter. This endpoint does not allow you to create transactions that charge donors."

This is perfect for:
- Importing historical donations from other platforms
- Recording cash, check, or DAF contributions
- Migrating data from legacy systems

### 4.3 Dry-Run Mode for All Mutations

**Decision**: Every create/update/delete command supports `--dry-run`.

**Rationale**:
- Prevents accidental data modifications
- Allows users to preview exactly what will happen
- Critical for bulk import operations where one mistake could affect hundreds of records

### 4.4 Flexible Output Formats

**Decision**: Support JSON, JSONL, and CSV output.

**Rationale**:
- JSON: Default, human-readable, great for debugging
- JSONL: Perfect for piping to `jq`, processing in scripts
- CSV: Direct import to spreadsheets, easy data analysis

### 4.5 Pagination Abstraction

**Decision**: Provide `--all-pages` flag that handles pagination automatically.

**Rationale**:
- Most users want all data, not page management
- Givebutter's default page size is small (15-25 items)
- Nonprofit databases can have thousands of contacts/transactions

## 5. API Coverage

| Endpoint Category | List | Get | Create | Update | Delete | Notes |
|-------------------|------|-----|--------|--------|--------|-------|
| Campaigns         | ✅   | ✅  | ✅     | ✅     | ✅     | Full CRUD |
| Contacts          | ✅   | ✅  | ✅     | ✅     | ✅     | Archive/Restore |
| Transactions      | ✅   | ✅  | ✅     | —      | —      | Create = record-keeping |
| Funds             | ✅   | ✅  | ✅     | ✅     | ✅     | Full CRUD |
| Plans             | ✅   | ✅  | —      | —      | —      | Read-only |
| Payouts           | ✅   | ✅  | —      | —      | —      | Read-only |
| Tickets           | ✅   | ✅  | —      | —      | —      | Read-only |
| Members           | ✅   | ✅  | —      | —      | ✅     | Scoped to campaign |
| Teams             | ✅   | ✅  | —      | —      | —      | Read-only |

## 6. Use Cases

### 6.1 Historical Data Import

Import donations from a previous platform:

```bash
# Prepare JSONL file with donor data
# Each line: {"first_name": "...", "last_name": "...", "email": "...", "amount": 100, "method": "check"}

givebutter.py transactions import legacy_donations.jsonl --campaign MAIN_CAMPAIGN --dry-run
# Review output, then run without --dry-run
givebutter.py transactions import legacy_donations.jsonl --campaign MAIN_CAMPAIGN
```

### 6.2 Donor Export for Analysis

Export all contacts for segmentation analysis:

```bash
givebutter.py contacts list --all-pages --format csv > donors.csv
```

### 6.3 Recurring Donor Report

Generate a report of active recurring donors:

```bash
givebutter.py plans list --status active --all-pages --format jsonl | \
  jq -r '[.first_name, .last_name, .email, .amount, .frequency] | @csv'
```

### 6.4 Campaign Fundraising Summary

Get totals for all campaigns:

```bash
givebutter.py campaigns list --all-pages --format jsonl | \
  jq -r '[.title, .total, .goal] | @csv'
```

## 7. Future Considerations

*   **Webhooks**: Add webhook management when API supports it
*   **Bulk Updates**: Batch contact/transaction updates
*   **Search**: Enhanced filtering with date ranges, amount ranges
*   **Templates**: Pre-built import templates for common platforms (Network for Good, Bloomerang, etc.)
*   **Reports**: Built-in reporting commands (YTD totals, donor retention, etc.)
*   **OAuth**: Support for OAuth flow if Givebutter adds it

## 8. Testing Strategy

*   **Unit Tests**: Mock HTTP responses, test argument parsing
*   **Integration Tests**: Use a test Givebutter account (sandbox)
*   **Dry-Run Tests**: Verify dry-run produces correct output without API calls
*   **Edge Cases**: Empty results, pagination boundaries, error responses

## 9. References

*   [Givebutter API Documentation](https://docs.givebutter.com/reference/reference-getting-started)
*   [Givebutter Authentication](https://docs.givebutter.com/reference/authentication)
*   [Givebutter Pagination](https://docs.givebutter.com/reference/pagination)

