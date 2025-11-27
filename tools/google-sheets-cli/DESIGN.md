# Design – google-sheets-cli

## Problem Statement

Google Sheets is often used as a lightweight database. CLI access enables automation, data pipelines, and integration with other tools.

## Key Design Decisions

### 1. Shared OAuth

Uses same credentials as other Google tools.

### 2. JSON Values

Values are passed as JSON arrays for flexibility:
- Single row: `'["a","b","c"]'`
- Multiple rows: `'[["a","b"],["c","d"]]'`

### 3. Retry Logic

Automatic exponential backoff for rate limits.

## Future Enhancements

- CSV import/export
- Formula support
- Conditional formatting
- Named ranges

