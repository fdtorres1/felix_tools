# ClickUp CLI

A command-line interface for managing ClickUp tasks, teams, spaces, and lists using the ClickUp API.

## Overview

This tool enables you to search, create, update, and close ClickUp tasks from your terminal. It supports bulk operations, dry-run previews, and optional Telegram + macOS notifications.

## Use Cases

- **Task management**: Create, update, and close tasks from the command line
- **Bulk operations**: Import tasks from JSON/JSONL files
- **Search and export**: Find tasks by criteria and export to JSONL/CSV
- **Automation**: Integrate with scripts and workflows
- **Cleanup**: Batch close test or stale tasks

## Quickstart

### Installation

```bash
# Use the shared venv
source ~/.venvs/felix-tools/bin/activate
pip install -r ../../tools/shared-requirements.txt
```

### Configuration

Add to `~/AGENTS.env`:
```bash
CLICKUP_API_TOKEN=your-api-token-here
CLICKUP_DEFAULT_TEAM_ID=your-team-id       # optional
CLICKUP_DEFAULT_LIST_ID=your-list-id       # optional
```

### Basic Usage

```bash
# Auth check - list teams
python src/clickup.py teams

# List spaces in a team
python src/clickup.py spaces --team <TEAM_ID>

# List lists in a space
python src/clickup.py lists --space <SPACE_ID>

# Search tasks
python src/clickup.py tasks search --team <TEAM_ID> --query 'keyword'

# Create a task (dry-run)
python src/clickup.py task create --list <LIST_ID> --name 'Follow up' --dry-run

# Update a task
python src/clickup.py task update --id <TASK_ID> --status 'In Progress' --dry-run
```

## Examples

### Search Tasks

```bash
# Search with filters
python src/clickup.py tasks search \
  --team <TEAM_ID> \
  --query 'onboarding' \
  --status-name 'In Progress' \
  --assignee-name 'anne@example.com' \
  --limit 50

# Export to JSONL
python src/clickup.py tasks export \
  --team <TEAM_ID> \
  --query 'Q4' \
  --all \
  --out /tmp/tasks.jsonl

# Export to CSV
python src/clickup.py tasks export \
  --team <TEAM_ID> \
  --query 'Q4' \
  --csv /tmp/tasks.csv \
  --fields id,name,status,due_date,url
```

### Create Tasks

```bash
# Create with assignee by name
python src/clickup.py task create \
  --list-name 'Backlog' \
  --team <TEAM_ID> \
  --name 'Review proposal' \
  --assignee-name 'jamie@example.com' \
  --priority-name high \
  --due '2025-01-20T17:00:00-06:00' \
  --dry-run

# Bulk create from file
python src/clickup.py tasks bulk-create \
  --file tasks.jsonl \
  --dry-run
```

### Comments and Tags

```bash
# Add comment
python src/clickup.py task comment add --id <TASK_ID> --text 'Note'

# Add tag
python src/clickup.py task tag add --id <TASK_ID> --tag urgent

# Remove tag
python src/clickup.py task tag remove --id <TASK_ID> --tag urgent
```

### Cleanup Test Tasks

```bash
# Close tasks matching filters (safe, non-destructive)
python src/clickup.py tasks cleanup \
  --team <TEAM_ID> \
  --name-contains 'Test task' \
  --created-after 2025-01-01T00:00:00Z \
  --dry-run
```

## Command Reference

| Command | Description |
|---------|-------------|
| `teams` | List workspaces (teams) |
| `spaces --team <ID>` | List spaces in a team |
| `lists --space <ID>` | List lists in a space |
| `statuses --list <ID>` | List statuses for a list |
| `users --team <ID>` | List team members |
| `tasks search` | Search tasks across a team |
| `tasks list` | List tasks in a specific list |
| `tasks export` | Export tasks to JSONL/CSV |
| `tasks find` | Find tasks by name |
| `tasks cleanup` | Batch close tasks by filters |
| `tasks bulk-create` | Create tasks from JSON/JSONL |
| `tasks import` | Import tasks with name resolution |
| `task get --id <ID>` | Get a single task |
| `task create` | Create a task |
| `task update --id <ID>` | Update a task |
| `task close --id <ID>` | Close a task |
| `task comment add` | Add a comment |
| `task tag add/remove` | Manage tags |
| `task fields --id <ID>` | Show custom fields |

## Notes

- **Dry-run**: Add `--dry-run` to preview mutations without applying
- **Date format**: Use ISO8601 (e.g., `2025-01-15T17:00:00-06:00`)
- **Name resolution**: Use `--list-name`, `--team`, `--space` for friendly names
- **Assignees**: Use `--assignee-name` with email or username
- **Notifications**: Set `TELEGRAM_*` env vars for failure alerts

See [CONFIG.md](CONFIG.md) for all configuration options.

