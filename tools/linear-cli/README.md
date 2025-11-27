# Linear CLI

A lightweight Bash-based CLI for Linear issue tracking using the GraphQL API.

## Overview

This tool provides shell functions for querying and mutating Linear issues, labels, and comments. It's designed to be sourced in your shell for quick operations.

## Use Cases

- **Issue lookup**: Search issues by title
- **Quick operations**: Create, update issues from terminal
- **Automation**: Integrate with shell scripts
- **Dry-run first**: Preview mutations before applying

## Quickstart

### Setup

Add to `~/AGENTS.env`:
```bash
LINEAR_AGENT_TOKEN=lin_oauth_your_token_here
```

### Usage

```bash
# Source the helper
source tools/linear-cli/src/linear.sh

# List teams
li_teams

# Search issues
li_issues_find --title-contains 'bug'

# Create issue (dry-run by default)
li_issue_create --team-id <ID> --title 'Fix login bug'
```

## Examples

### Querying

```bash
# List teams
li_teams

# Get team ID by key
li_team_id ENG

# List labels (optionally by team)
li_labels
li_labels ENG

# Find user ID
li_user_id 'john@example.com'

# Search issues
li_issues_find --title-contains 'authentication' --team ENG
```

### Creating Issues

```bash
# Dry-run (default)
li_issue_create --team-id <TEAM_ID> --title 'New feature' --description 'Details here'

# With labels
li_issue_create --team-id <TEAM_ID> --title 'Bug' --label-ids label1,label2

# Apply (execute mutation)
LI_APPLY=1 li_issue_create --team-id <TEAM_ID> --title 'New feature'

# Or use --apply flag
li_issue_create --team-id <TEAM_ID> --title 'New feature' --apply
```

### Updating Issues

```bash
# Update title (dry-run)
li_issue_update --id <ISSUE_ID> --title 'Updated title'

# Add labels
li_issue_update --id <ISSUE_ID> --add-label-ids label1,label2 --apply

# Remove labels
li_issue_update --id <ISSUE_ID> --remove-label-ids label3 --apply
```

### Comments

```bash
# Add comment (dry-run)
li_comment_create --issue-id <ID> --body 'Thanks for the report!'

# Apply
li_comment_create --issue-id <ID> --body 'Fixed in v1.2' --apply
```

### Raw GraphQL

```bash
# Direct query
li '{"query":"query{ teams(first:5){ nodes{ id key name } } }"}'
```

## Command Reference

| Function | Description |
|----------|-------------|
| `li` | Execute raw GraphQL |
| `li_teams` | List teams |
| `li_team_id <KEY>` | Get team ID |
| `li_labels [KEY]` | List labels |
| `li_user_id <query>` | Find user |
| `li_issues_find` | Search issues |
| `li_issue_create` | Create issue |
| `li_issue_update` | Update issue |
| `li_comment_create` | Add comment |

## Notes

- **Dry-run**: All mutations are dry-run by default. Set `LI_APPLY=1` or use `--apply`
- **Dependencies**: Requires `curl` and `jq`
- **Authentication**: Uses Bearer token in Authorization header

See [CONFIG.md](CONFIG.md) for configuration details.

