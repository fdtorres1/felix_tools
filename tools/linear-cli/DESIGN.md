# Design – linear-cli

## Problem Statement

Linear's web UI is excellent but lacks CLI access for automation and quick operations from terminal.

## Key Design Decisions

### 1. Pure Bash

No Python dependencies - just `curl` and `jq`:
- Fast startup
- Works anywhere
- Easy to customize

### 2. Sourceable Functions

Designed to be sourced in your shell:
```bash
source linear.sh
li_teams
```

### 3. Dry-Run by Default

All mutations print the request without executing:
- Safe exploration
- Copy/paste to verify
- Set `LI_APPLY=1` to execute

### 4. GraphQL Direct

Raw GraphQL access via `li` function for flexibility.

## Future Enhancements

- Project management
- Cycle tracking
- Webhook integration

