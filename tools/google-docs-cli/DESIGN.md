# Design – google-docs-cli

## Problem Statement

Google Docs lacks CLI access for automation. This tool enables programmatic document manipulation, content insertion, and export.

## Key Design Decisions

### 1. Position-Based Insertion

The Docs API works with character indexes. The tool calculates positions automatically when targeting headings.

### 2. Dual Scopes

- `documents` scope for read/write
- `drive` scope for export and sharing

### 3. Retry Logic

Automatic exponential backoff with jitter for 429 and 5xx errors.

## Future Enhancements

- Batch updates
- Style application
- Comments management

