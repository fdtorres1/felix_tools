# Design – google-calendar-cli

## Problem Statement

Google Calendar's web UI is good for interactive use but lacks CLI capabilities for automation, bulk operations, and integration with scripts.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        gcal.py                               │
├─────────────────────────────────────────────────────────────┤
│  CLI Layer (argparse)                                        │
│  - Commands: auth, calendars, events, freebusy               │
├─────────────────────────────────────────────────────────────┤
│  Google API Client                                           │
│  - OAuth credential management                               │
│  - Calendar API v3                                           │
│  - People API (for contacts labels)                          │
├─────────────────────────────────────────────────────────────┤
│  Business Logic                                              │
│  - RRULE builder for recurring events                        │
│  - Attendee resolution from labels                           │
│  - Dry-run handling                                          │
├─────────────────────────────────────────────────────────────┤
│  Config Layer                                                │
│  - Load ~/AGENTS.env                                         │
│  - OAuth token refresh                                       │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. OAuth Desktop Flow

Desktop OAuth provides:
- Refresh tokens that persist
- No server-side component needed
- User owns their credentials

### 2. RRULE Builder

Instead of manual RRULE strings, use flags:
```bash
--repeat WEEKLY --by-day MO,WE,FR --count 52
```

More user-friendly than:
```bash
--recurrence 'RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=52'
```

### 3. Contacts Label Integration

Attendees can come from Google Contacts labels:
```bash
--attendees-label 'Project Team'
```

This resolves to email addresses automatically.

### 4. Dry-Run Mode

All mutations support `--dry-run` to preview:
- The request body
- Resolved attendees
- Without making API calls

## Trade-offs

| Decision | Benefit | Cost |
|----------|---------|------|
| OAuth refresh | Long-lived tokens | Initial setup complexity |
| RRULE builder | User-friendly | Limited to common patterns |
| Labels → emails | Convenient | Extra API calls |
| Single file | Simple deployment | Harder to test |

## Future Enhancements

- Calendar sharing management
- Event reminders configuration
- Working hours/out-of-office
- Calendar color management

