# Gmail CLI

A comprehensive command-line interface for Gmail with support for sending, replying, drafts, labels, aliases, and scheduled sends.

## Overview

This tool enables complete Gmail management from the command line, including email composition, label management, alias configuration, and a queue system for scheduled sends.

## Use Cases

- **Email sending**: Send text or HTML emails with attachments
- **Recipient resolution**: Expand Contacts labels to email addresses
- **Label management**: Create, apply, and remove labels
- **Alias configuration**: Manage sendAs aliases
- **Scheduled sends**: Queue emails for future delivery
- **Automation**: Integrate with scripts and workflows

## Quickstart

### Installation

```bash
source ~/.venvs/felix-tools/bin/activate
pip install -r ../../tools/shared-requirements.txt
```

### Authentication

```bash
python src/gmail.py auth
# Copy GOOGLE_OAUTH_REFRESH_TOKEN to ~/AGENTS.env
```

### Basic Usage

```bash
# Check profile
python src/gmail.py me

# Send email (dry-run)
python src/gmail.py send --to 'user@example.com' --subject 'Hello' --text 'Hi there' --dry-run

# List messages
python src/gmail.py list --q 'in:inbox newer_than:7d' --max 10
```

## Examples

### Sending Email

```bash
# Simple text email
python src/gmail.py send --to 'user@example.com' --subject 'Hello' --text 'Body text'

# HTML email
python src/gmail.py send --to 'user@example.com' --subject 'Hello' --html '<b>Bold</b>'

# With CC/BCC
python src/gmail.py send --to 'a@example.com' --cc 'b@example.com' --bcc 'c@example.com' \
  --subject 'Team Update' --text 'Content'

# From alias
python src/gmail.py send --to 'user@example.com' --subject 'Hello' --text 'Hi' \
  --sender alias@yourdomain.com
```

### Using Contacts Labels

```bash
# Send to everyone in a label
python src/gmail.py send --to-label 'Project Team' --subject 'Update' --text 'Hi all'

# Combine labels and direct addresses
python src/gmail.py send --to 'boss@example.com' --cc-label 'Project Team' \
  --subject 'Report' --text 'Attached'

# Resolve recipients (preview)
python src/gmail.py resolve --to-label 'Team' --cc 'extra@example.com'
```

### Replying

```bash
# Simple reply
python src/gmail.py reply --id <MSG_ID> --text 'Thanks!'

# Reply all
python src/gmail.py reply --id <MSG_ID> --reply-all --text 'Thanks all'

# Preview reply
python src/gmail.py reply --id <MSG_ID> --text 'Thanks!' --dry-run
```

### Drafts

```bash
# Create draft
python src/gmail.py draft create --to 'user@example.com' --subject 'Draft' --text 'Content'

# Send draft
python src/gmail.py draft send --id <DRAFT_ID>

# Delete draft
python src/gmail.py draft delete --id <DRAFT_ID>
```

### Labels

```bash
# List labels
python src/gmail.py labels list

# Create label
python src/gmail.py labels create --name 'Important/Projects'

# Apply label to message
python src/gmail.py labels apply --message <MSG_ID> --add 'Projects' --remove 'INBOX'
```

### Scheduled Sends (Queue)

```bash
# Queue email for later
python src/gmail.py queue add --to 'user@example.com' --subject 'Reminder' \
  --text 'Follow up' --send-at '2025-01-15T09:00:00-06:00'

# List pending
python src/gmail.py queue list

# Dispatch due emails
python src/gmail.py queue dispatch

# Update queued email
python src/gmail.py queue update --id <QUEUE_ID> --text 'Updated body'

# Cancel queued email
python src/gmail.py queue cancel --id <QUEUE_ID>
```

### Aliases

```bash
# List aliases
python src/gmail.py aliases list

# Create alias
python src/gmail.py aliases create --email alias@domain.com --display-name 'Alias'

# Set default alias
python src/gmail.py aliases set-default --email alias@domain.com
```

## Command Reference

| Command | Description |
|---------|-------------|
| `auth` | OAuth flow |
| `me` | Show profile |
| `list` | List messages |
| `get` | Get message |
| `resolve` | Resolve recipients |
| `send` | Send email |
| `reply` | Reply to message |
| `draft create/send/delete` | Manage drafts |
| `labels list/create/apply` | Manage labels |
| `aliases list/create/update` | Manage sendAs |
| `queue add/list/dispatch` | Scheduled sends |

## Notes

- **Dry-run**: Always preview with `--dry-run` before sending
- **Contacts labels**: Use `--to-label`, `--cc-label`, `--bcc-label`
- **Queue**: Use LaunchAgent for automatic dispatch (see docs/)

See [CONFIG.md](CONFIG.md) for all configuration options.

