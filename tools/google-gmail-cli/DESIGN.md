# Design – google-gmail-cli

## Problem Statement

Gmail needs CLI access for automation, bulk operations, and integration with other tools. The scheduled send queue enables reliable future delivery.

## Key Design Decisions

### 1. Contacts Integration

Recipients can be resolved from Google Contacts labels:
- `--to-label 'Team'` expands to all emails in that group
- Deduplication across labels and direct addresses

### 2. Scheduled Send Queue

File-based queue (`queue.jsonl`) with:
- Persistent storage across sessions
- LaunchAgent for automatic dispatch
- Backoff and retry on failures
- Telegram alerts on permanent failures

### 3. Dry-Run First

All send operations support `--dry-run` to preview:
- Resolved recipients
- Subject and content
- Without making API calls

### 4. Reply Threading

Replies automatically set:
- `In-Reply-To` header
- `References` header
- `threadId` for Gmail threading

## Future Enhancements

- Attachment support
- Template system
- Batch operations

