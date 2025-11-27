# EventKit Calendar CLI

A native macOS command-line tool for managing Apple Calendar events using the EventKit framework.

## Overview

This Swift-based tool provides direct access to macOS Calendar (EventKit) for listing calendars, managing events, and sending daily/weekly digests to Telegram.

## Use Cases

- **Calendar overview**: List all calendars and their sources
- **Event management**: Create, update, delete events locally
- **Daily digests**: Send schedule summaries to Telegram
- **Bulk imports**: Create multiple events from JSONL files
- **Integration**: Combine with other tools for automation

## Quickstart

### Building

```bash
# Compile the Swift source
cd src
swiftc -O -o ekcal ekcal.swift
mv ekcal ../scripts/
```

### Configuration

Add to `~/AGENTS.env`:
```bash
# Calendar selection (use IDs for reliability)
INCLUDE_CALENDAR_IDS=ABC123,DEF456
# Or use names (may be ambiguous across sources)
INCLUDE_CALENDARS=Personal,Work

# Telegram for digests (optional)
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

### Basic Usage

```bash
# List all calendars
ekcal calendars

# List today's events
ekcal events list --today --calendars 'Personal,Work'

# Create an event
ekcal events create --calendar 'Personal' --title 'Lunch' \
  --start '2025-01-15T12:00' --end '2025-01-15T13:00' --location 'Cafe'

# Send daily digest to Telegram
ekcal digest --day today
```

## Examples

### List Calendars

```bash
# Get all calendars with IDs
ekcal calendars | jq '.calendars[] | {title, id, sourceTitle}'
```

### Event Operations

```bash
# Today's events (JSON output)
ekcal events list --today --calendars 'Personal' --json

# Find events by title
ekcal events find --today --calendars 'Work' --title-contains 'Meeting'

# Create all-day event
ekcal events create --calendar 'Personal' --title 'Holiday' \
  --all-day --date '2025-01-20'

# Update event by ID
ekcal events update --id '<EVENT_ID>' --title 'New Title' --start '2025-01-15T13:00'

# Delete event
ekcal events delete --id '<EVENT_ID>'
```

### Bulk Create

```bash
# From JSONL file (dry-run)
ekcal events bulk-create --file events.jsonl --dry-run

# Apply
ekcal events bulk-create --file events.jsonl
```

JSONL format:
```json
{"calendar": "Personal", "title": "Meeting", "start": "2025-01-15T10:00", "end": "2025-01-15T11:00"}
{"calendar": "Work", "title": "Standup", "date": "2025-01-16", "all_day": true}
```

### Digests

```bash
# Today's digest
ekcal digest --day today

# Tomorrow's digest
ekcal digest --day tomorrow

# Week digest (next 7 days)
ekcal digest-week
```

## Command Reference

| Command | Description |
|---------|-------------|
| `calendars` | List all calendars |
| `events list` | List events in date range |
| `events find` | Find events by title |
| `events create` | Create an event |
| `events update` | Update an event by ID |
| `events delete` | Delete an event by ID |
| `events bulk-create` | Create events from JSONL |
| `digest` | Send daily digest to Telegram |
| `digest-week` | Send weekly digest |

## Notes

- **Calendar access**: Requires macOS Calendar permission (prompted on first run)
- **Date format**: `YYYY-MM-DD` for dates, `YYYY-MM-DDTHH:MM` for times
- **Event IDs**: Stable while event is in cache; use `events find --json` to retrieve
- **Telegram**: If `TELEGRAM_*` env vars are set, digests are sent; otherwise printed

See [CONFIG.md](CONFIG.md) for all configuration options.

