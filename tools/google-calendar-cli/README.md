# Google Calendar CLI

A command-line interface for managing Google Calendar events using OAuth authentication.

## Overview

This tool enables you to list calendars, create/update/delete events, handle recurring events, add Google Meet links, and perform bulk operations from the command line.

## Use Cases

- **Event management**: Create, update, and delete calendar events
- **Bulk operations**: Import events from JSON/JSONL files
- **Meeting scheduling**: Add attendees, Google Meet links
- **Free/busy lookup**: Check availability
- **Recurring events**: Create with RRULE patterns

## Quickstart

### Installation

```bash
source ~/.venvs/felix-tools/bin/activate
pip install -r ../../tools/shared-requirements.txt
```

### Authentication

```bash
# Run OAuth flow
python src/gcal.py auth

# Copy the printed GOOGLE_OAUTH_REFRESH_TOKEN to ~/AGENTS.env
```

### Configuration

Add to `~/AGENTS.env`:
```bash
GOOGLE_OAUTH_CLIENT_ID=your-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
GOOGLE_OAUTH_REFRESH_TOKEN=your-refresh-token
```

### Basic Usage

```bash
# List calendars
python src/gcal.py calendars

# List events (next 7 days)
python src/gcal.py events list --calendar primary

# Create event
python src/gcal.py events create --calendar primary \
  --summary 'Meeting' \
  --start 2025-01-15T10:00:00-06:00 \
  --end 2025-01-15T11:00:00-06:00
```

## Examples

### Create Events

```bash
# Timed event with location
python src/gcal.py events create --calendar primary \
  --summary 'Team Standup' \
  --start 2025-01-15T09:00:00-06:00 \
  --end 2025-01-15T09:30:00-06:00 \
  --location 'Conference Room A'

# All-day event
python src/gcal.py events create --calendar primary \
  --summary 'Company Holiday' \
  --start 2025-01-20 \
  --end 2025-01-20

# With Google Meet link
python src/gcal.py events create --calendar primary \
  --summary 'Video Call' \
  --start 2025-01-15T14:00:00-06:00 \
  --end 2025-01-15T15:00:00-06:00 \
  --meet

# With attendees
python src/gcal.py events create --calendar primary \
  --summary 'Planning Meeting' \
  --start 2025-01-15T10:00:00-06:00 \
  --end 2025-01-15T11:00:00-06:00 \
  --attendees 'alice@example.com,bob@example.com' \
  --send-updates all
```

### Recurring Events

```bash
# Weekly on Monday, Wednesday, Friday
python src/gcal.py events create --calendar primary \
  --summary 'Standup' \
  --start 2025-01-15T09:00:00-06:00 \
  --end 2025-01-15T09:15:00-06:00 \
  --repeat WEEKLY --by-day MO,WE,FR --count 52

# Monthly on the 1st
python src/gcal.py events create --calendar primary \
  --summary 'Monthly Review' \
  --start 2025-02-01T10:00:00-06:00 \
  --end 2025-02-01T11:00:00-06:00 \
  --repeat MONTHLY --by-month-day 1 --until 2025-12-31
```

### Bulk Create

```bash
# From JSONL file (dry-run)
python src/gcal.py events bulk-create --file events.jsonl --dry-run

# Apply
python src/gcal.py events bulk-create --file events.jsonl
```

### Free/Busy Lookup

```bash
python src/gcal.py freebusy --calendar primary \
  --from 2025-01-15T09:00:00Z \
  --to 2025-01-15T18:00:00Z
```

## Command Reference

| Command | Description |
|---------|-------------|
| `auth` | Run OAuth flow |
| `calendars` | List calendars |
| `events list` | List events |
| `events create` | Create an event |
| `events update` | Update an event |
| `events delete` | Delete an event |
| `events quick-add` | Natural language event |
| `events bulk-create` | Create from file |
| `freebusy` | Check availability |

## Notes

- **Time format**: ISO8601 with offset (`2025-01-15T10:00:00-06:00`) or `Z` for UTC
- **All-day events**: Use `YYYY-MM-DD` format for start/end
- **Dry-run**: Add `--dry-run` to preview without creating
- **Send updates**: Use `--send-updates all|externalOnly|none`

See [CONFIG.md](CONFIG.md) for all configuration options.

