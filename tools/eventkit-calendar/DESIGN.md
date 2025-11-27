# Design – eventkit-calendar

## Problem Statement

macOS Calendar is powerful but lacks CLI access. AppleScript is cumbersome, and third-party tools often require syncing to external services. A native EventKit CLI provides direct, fast access to local calendars.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        ekcal (Swift)                         │
├─────────────────────────────────────────────────────────────┤
│  CLI Layer                                                   │
│  - Minimal arg parsing                                       │
│  - Command routing                                           │
├─────────────────────────────────────────────────────────────┤
│  EventKit Integration                                        │
│  - EKEventStore for calendar access                          │
│  - Predicates for date-range queries                         │
│  - Event CRUD operations                                     │
├─────────────────────────────────────────────────────────────┤
│  Output Layer                                                │
│  - JSON serialization                                        │
│  - Human-readable formatting                                 │
│  - Telegram API integration                                  │
├─────────────────────────────────────────────────────────────┤
│  Config Layer                                                │
│  - Read ~/AGENTS.env                                         │
│  - Environment variable fallback                             │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Swift + EventKit

Native Swift provides:
- Direct EventKit API access
- No Python dependencies
- Fast startup time
- Full macOS integration

### 2. Single-File Architecture

All code in one `.swift` file for:
- Easy compilation (`swiftc -O -o ekcal ekcal.swift`)
- No package manager needed
- Simple distribution

### 3. Calendar ID Preference

IDs are preferred over names because:
- Names can be duplicated across sources
- IDs are stable identifiers
- Avoids ambiguity

### 4. Telegram Integration

Built-in Telegram support for digests:
- No external dependencies
- Direct HTTP POST via URLSession
- Falls back to stdout if not configured

### 5. JSON Output

All commands support JSON output for:
- Scripting and automation
- Integration with other tools
- Predictable parsing

## Data Flow

### Event Creation

```
1. Parse CLI args
2. Load ~/AGENTS.env
3. Request calendar access
4. Find calendar by title
5. Create EKEvent
6. Set properties (title, dates, location)
7. Save to store
8. Output created event ID
```

### Digest Generation

```
1. Parse CLI args (day, calendars)
2. Load config
3. Request calendar access
4. Filter calendars by ID/name
5. Query events for date range
6. Sort by start time
7. Group by calendar
8. Format as text
9. If Telegram configured: POST to API
10. Otherwise: print to stdout
```

## Trade-offs

| Decision | Benefit | Cost |
|----------|---------|------|
| Swift native | Fast, no deps | macOS only |
| Single file | Simple build | No modularization |
| EventKit | Direct access | Requires permission |
| ID preference | Reliable | Less user-friendly |

## Future Enhancements

- Recurring event support
- Attendee management
- Alarm/reminder configuration
- Calendar creation/deletion
- iCloud sync status

