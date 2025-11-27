# Google Docs CLI

A command-line interface for Google Docs operations using OAuth authentication.

## Overview

This tool enables you to read documents, append content, insert headings/tables/images, find-replace text, and export documents from the command line.

## Use Cases

- **Document reading**: Extract text content from docs
- **Content insertion**: Append paragraphs, headings, tables
- **Find and replace**: Batch text updates
- **Export**: Download as PDF or plain text
- **Automation**: Integrate with scripts and workflows

## Quickstart

### Installation

```bash
source ~/.venvs/felix-tools/bin/activate
pip install -r ../../tools/shared-requirements.txt
```

### Authentication

```bash
python src/gdocs.py auth
# Copy GOOGLE_OAUTH_REFRESH_TOKEN to ~/AGENTS.env
```

### Basic Usage

```bash
# Read document as text
python src/gdocs.py get --document <DOC_ID> --as text

# List headings
python src/gdocs.py list-headings --document <DOC_ID>

# Append content
python src/gdocs.py append --document <DOC_ID> --text 'New paragraph'
```

## Examples

### Reading

```bash
# Get full text content
python src/gdocs.py get --document <DOC_ID> --as text

# List all headings
python src/gdocs.py list-headings --document <DOC_ID>
```

### Inserting Content

```bash
# Append paragraph
python src/gdocs.py append --document <DOC_ID> --text 'Added content\n'

# Insert heading
python src/gdocs.py insert-heading --document <DOC_ID> --text 'New Section' --level 2

# Insert after specific heading
python src/gdocs.py append --document <DOC_ID> \
  --after-heading 'Introduction' \
  --text 'Content under introduction'

# Insert table
python src/gdocs.py insert-table --document <DOC_ID> --rows 3 --cols 2

# Insert image
python src/gdocs.py insert-image --document <DOC_ID> \
  --uri 'https://example.com/image.png' --width 400 --height 200

# Insert page break
python src/gdocs.py insert-page-break --document <DOC_ID>
```

### Find and Replace

```bash
# Case-insensitive replace
python src/gdocs.py find-replace --document <DOC_ID> --find 'old' --replace 'new'

# Case-sensitive
python src/gdocs.py find-replace --document <DOC_ID> --find 'Old' --replace 'New' --match-case
```

### Creating and Exporting

```bash
# Create new document
python src/gdocs.py create --title 'My New Document'

# Export as PDF
python src/gdocs.py export --document <DOC_ID> --mime application/pdf --out report.pdf

# Export as text
python src/gdocs.py export --document <DOC_ID> --mime text/plain --out report.txt

# Share document
python src/gdocs.py share --file <DOC_ID> --email user@example.com --role writer
```

## Command Reference

| Command | Description |
|---------|-------------|
| `auth` | Run OAuth flow |
| `get` | Read document |
| `list-headings` | List all headings |
| `find-replace` | Find and replace text |
| `append` | Append text |
| `insert-heading` | Insert styled heading |
| `insert-table` | Insert table |
| `insert-image` | Insert image |
| `insert-page-break` | Insert page break |
| `insert-section-break` | Insert section break |
| `create` | Create new document |
| `export` | Export to PDF/text |
| `share` | Share via Drive |

## Notes

- **Document ID**: Found in the URL: `docs.google.com/document/d/<DOC_ID>/edit`
- **Heading targeting**: Use `--after-heading` with `--contains` for substring match
- **Export**: Requires Drive scope in addition to Docs scope

See [CONFIG.md](CONFIG.md) for all configuration options.

