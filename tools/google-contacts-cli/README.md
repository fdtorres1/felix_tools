# Google Contacts CLI

A command-line interface for managing Google Contacts using the People API with OAuth authentication.

## Overview

This tool enables you to list, search, create, update, and delete contacts, as well as manage contact groups (labels) from the command line.

## Use Cases

- **Contact lookup**: Search contacts by name, email, or phone
- **Group management**: Create and manage contact labels/groups
- **Bulk resolution**: Get all emails from a contact group
- **Integration**: Use with Gmail tool for recipient resolution

## Quickstart

### Installation

```bash
source ~/.venvs/felix-tools/bin/activate
pip install -r ../../tools/shared-requirements.txt
```

### Authentication

```bash
python src/gcontacts.py auth
# Copy GOOGLE_OAUTH_REFRESH_TOKEN to ~/AGENTS.env
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
# List contacts
python src/gcontacts.py list --fields names,emailAddresses

# Search contacts
python src/gcontacts.py search --query 'john' --fields names,emailAddresses

# List contact groups
python src/gcontacts.py groups list

# Get emails from a group
python src/gcontacts.py groups emails --group 'Project Team'
```

## Examples

### Contact Operations

```bash
# List with phone numbers
python src/gcontacts.py list --fields names,emailAddresses,phoneNumbers --page-size 100

# Get specific contact
python src/gcontacts.py get --resource people/c123456789 --fields names,emailAddresses

# Create contact
python src/gcontacts.py create \
  --given-name John \
  --family-name Doe \
  --email john@example.com \
  --phone '+1-555-123-4567' \
  --org 'Acme Inc' \
  --title 'Engineer'

# Update contact
python src/gcontacts.py update \
  --resource people/c123456789 \
  --email john.doe@newcompany.com

# Delete contact
python src/gcontacts.py delete --resource people/c123456789
```

### Group Operations

```bash
# List all groups (labels)
python src/gcontacts.py groups list

# Create a group
python src/gcontacts.py groups create --name 'Project Alpha'

# Add contact to group
python src/gcontacts.py groups add \
  --resource people/c123456789 \
  --group 'Project Alpha'

# Remove from group
python src/gcontacts.py groups remove \
  --resource people/c123456789 \
  --group 'Project Alpha'

# Get all emails from a group
python src/gcontacts.py groups emails --group 'Project Alpha'

# Delete a group
python src/gcontacts.py groups delete --group 'Project Alpha'
```

## Command Reference

| Command | Description |
|---------|-------------|
| `auth` | Run OAuth flow |
| `list` | List contacts |
| `search` | Search by query |
| `get` | Get specific contact |
| `create` | Create contact |
| `update` | Update contact |
| `delete` | Delete contact |
| `groups list` | List groups |
| `groups create` | Create group |
| `groups add` | Add to group |
| `groups remove` | Remove from group |
| `groups emails` | Get group emails |
| `groups delete` | Delete group |

## Notes

- **Resource names**: Use `people/c123456789` or just the ID
- **Labels vs Groups**: In Contacts UI they're "labels"; API calls them "contactGroups"
- **Field masks**: Use `--fields` to specify which data to return
- **etag**: Updates auto-fetch etag for conflict handling

See [CONFIG.md](CONFIG.md) for all configuration options.

