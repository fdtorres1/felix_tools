# Design – shopify-cli

## Problem Statement

Shopify's Admin UI is comprehensive but lacks CLI access for automation, bulk exports, and integration with other systems.

## Key Design Decisions

### 1. GraphQL API

Uses Admin GraphQL API (not REST) for:
- Efficient data fetching
- Single endpoint
- Strong typing

### 2. Cursor Pagination

Implements cursor-based pagination for large datasets:
- Consistent results
- No skipped/duplicated items
- Memory efficient

### 3. Multiple Export Formats

Supports both JSONL and CSV:
- JSONL for programmatic processing
- CSV for spreadsheets/humans

### 4. Dry-Run First

All mutations support `--dry-run` for safe exploration.

## Future Enhancements

- Bulk operations via staged uploads
- Inventory management
- Theme operations
- Webhook management

