# Design – clickup-cli

## Problem Statement

Managing ClickUp tasks from the command line enables automation, scripting, and integration with other tools. The web UI is convenient for interactive use but cumbersome for bulk operations, exports, or CI/CD pipelines.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        clickup.py                            │
├─────────────────────────────────────────────────────────────┤
│  CLI Layer (argparse)                                        │
│  - Parses commands and flags                                 │
│  - Routes to appropriate handler                             │
├─────────────────────────────────────────────────────────────┤
│  Business Logic                                              │
│  - Name resolution (team, space, list, user)                 │
│  - Status/priority mapping                                   │
│  - Dry-run handling                                          │
├─────────────────────────────────────────────────────────────┤
│  HTTP Layer                                                  │
│  - GET/POST/PUT to ClickUp API v2                            │
│  - Error handling and notifications                          │
├─────────────────────────────────────────────────────────────┤
│  Config Layer                                                │
│  - Load ~/AGENTS.env                                         │
│  - Environment variable resolution                           │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Single-File Architecture

All functionality lives in one Python file for simplicity. The tool is ~1200 lines but remains manageable because:
- Clear function boundaries
- Consistent patterns
- No external state

### 2. Name-Based Resolution

Users can specify resources by name instead of ID:
- `--list-name 'Backlog'` instead of `--list 12345`
- `--assignee-name 'jamie@example.com'` instead of numeric user IDs

This requires extra API calls but dramatically improves usability.

### 3. Dry-Run First

All mutations support `--dry-run` to preview changes. This is critical for:
- Learning the tool safely
- Validating bulk operations
- Debugging integrations

### 4. Subcommand Structure

Commands are organized hierarchically:
- `teams`, `spaces`, `lists`, `users` – Browse hierarchy
- `tasks search|list|export|find|cleanup|bulk-create|import` – Batch operations
- `task get|create|update|close|comment|tag|fields` – Single-task operations

### 5. JSON Output

All output is JSON for programmatic parsing. Human-readable summaries are secondary.

### 6. Graceful Failure

- Clear error messages with context
- Optional Telegram notifications for unattended operations
- Optional macOS notifications via `terminal-notifier`

## Data Flow

### Task Creation

```
1. Parse CLI args
2. Load ~/AGENTS.env
3. Resolve list ID (by name if needed)
4. Resolve assignee IDs (by name/email if needed)
5. Resolve status name (validate against list)
6. Map priority name to number
7. Build request body
8. If --dry-run: print body and exit
9. POST to /list/{id}/task
10. Print response JSON
11. Optionally notify macOS
```

### Task Search

```
1. Parse CLI args
2. Load ~/AGENTS.env
3. Resolve team ID
4. Resolve user IDs for assignee filters
5. Build query params
6. Paginate through results (if --all)
7. Filter client-side if needed
8. Project fields (if --fields)
9. Output as JSON or JSONL
```

## Trade-offs

| Decision | Benefit | Cost |
|----------|---------|------|
| Single file | Simple deployment | Harder to test in isolation |
| Name resolution | User-friendly | Extra API calls |
| JSON output | Scriptable | Less human-readable |
| No caching | Always fresh data | Slower for repeated calls |

## Future Enhancements

- Webhooks integration for real-time updates
- Local caching for hierarchy (teams/spaces/lists)
- Natural-language task creation
- Interactive mode with fuzzy search

