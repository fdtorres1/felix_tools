# Google Sheets CLI

A command-line interface for Google Sheets operations using OAuth authentication.

## Overview

This tool enables you to read, append, and update spreadsheet data, create tabs and spreadsheets, and share files from the command line.

## Use Cases

- **Data extraction**: Read ranges from spreadsheets
- **Data entry**: Append rows or update cells
- **Automation**: Integrate with scripts and pipelines
- **Spreadsheet management**: Create sheets and tabs

## Quickstart

### Installation

```bash
source ~/.venvs/felix-tools/bin/activate
pip install -r ../../tools/shared-requirements.txt
```

### Authentication

```bash
python src/gsheets.py auth
# Copy GOOGLE_OAUTH_REFRESH_TOKEN to ~/AGENTS.env
```

### Basic Usage

```bash
# Read range
python src/gsheets.py read --spreadsheet <ID> --range 'Sheet1!A1:D10'

# Append row
python src/gsheets.py append --spreadsheet <ID> --range 'Sheet1!A:Z' --values '["a","b","c"]'

# Update cell
python src/gsheets.py update --spreadsheet <ID> --range 'Sheet1!B2' --values '["new value"]'
```

## Examples

### Reading Data

```bash
# Read specific range
python src/gsheets.py read --spreadsheet <ID> --range 'Sheet1!A1:F20'

# Read entire column
python src/gsheets.py read --spreadsheet <ID> --range 'Sheet1!A:A'
```

### Writing Data

```bash
# Append single row
python src/gsheets.py append --spreadsheet <ID> --range 'Sheet1!A:Z' --values '["a","b","c"]'

# Append multiple rows
python src/gsheets.py append --spreadsheet <ID> --range 'Sheet1!A:Z' \
  --values '[["row1a","row1b"],["row2a","row2b"]]'

# Update specific cell
python src/gsheets.py update --spreadsheet <ID> --range 'Sheet1!B2' --values '["updated"]'
```

### Management

```bash
# Create new tab
python src/gsheets.py create-tab --spreadsheet <ID> --title 'Q1 2025' --rows 1000 --cols 26

# Create new spreadsheet
python src/gsheets.py create-sheet --title 'My New Spreadsheet'

# Share spreadsheet
python src/gsheets.py share --file <ID> --email user@example.com --role writer
```

## Command Reference

| Command | Description |
|---------|-------------|
| `auth` | Run OAuth flow |
| `read` | Read range |
| `append` | Append rows |
| `update` | Update cells |
| `create-tab` | Create new tab |
| `create-sheet` | Create spreadsheet |
| `share` | Share file |

## Notes

- **Spreadsheet ID**: Found in URL: `docs.google.com/spreadsheets/d/<ID>/edit`
- **Range syntax**: `SheetName!A1:Z100` or `SheetName!A:Z`
- **Values format**: JSON array or array of arrays

See [CONFIG.md](CONFIG.md) for all configuration options.

