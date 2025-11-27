# Changelog – givebutter-cli

All notable changes to this tool are documented in this file.

## [Unreleased]

- No unreleased changes

## [1.0.0] – 2025-11-27

### Added

- Initial release of `givebutter-cli`
- **Campaigns**: Full CRUD operations (list, get, create, update, delete)
- **Contacts**: Full management including archive/restore
- **Transactions**: List, get, create (record-keeping for offline donations)
- **Transactions Import**: Bulk import from JSONL files
- **Funds**: Full CRUD for designated funds
- **Plans**: List and view recurring donation plans
- **Payouts**: List and view payout details
- **Tickets**: List and view event tickets
- **Members**: Manage campaign peer-to-peer fundraisers
- **Teams**: View campaign fundraising teams
- **Output Formats**: JSON (default), JSONL, CSV
- **Pagination**: `--all-pages` flag for complete data retrieval
- **Dry-Run Mode**: Preview all mutations before execution
- **Notifications**: Optional Telegram and macOS alerts on errors
- Zero external dependencies (Python standard library only)
- Comprehensive documentation (README, CONFIG, DESIGN)

### Payment Methods Supported (for transaction create)

- `cash`
- `check`
- `wire_transfer`
- `donor_advised_fund`
- `stock`
- `cryptocurrency`
- `other`

### API Coverage

- Base URL: `https://api.givebutter.com/v1`
- Authentication: Bearer token
- Full support for Givebutter API v1 endpoints

