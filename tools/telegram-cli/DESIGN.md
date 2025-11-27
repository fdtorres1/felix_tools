# Design – telegram-cli

## Problem Statement

Quick reminders during work sessions need a simple, reliable delivery mechanism. Telegram provides instant, cross-device notifications.

## Key Design Decisions

### 1. Pure Bash

No dependencies beyond `curl`:
- Works everywhere
- Fast startup
- Easy to customize

### 2. Background Sleep

Uses `nohup` + `sleep` instead of `at`:
- `at` on macOS requires `atrun` daemon
- Background sleep is reliable in interactive shells
- Survives shell exit (but not logout)

### 3. Duration Parsing

Supports human-friendly durations:
- `30s`, `5m`, `1h`, `1h30m`
- Combined formats parsed correctly

### 4. Session-Scoped

Reminders don't survive logout/reboot. For durable scheduling, use `launchd`.

## Future Enhancements

- LaunchAgent generator for durable reminders
- Recurring reminders
- Multiple chat ID support

