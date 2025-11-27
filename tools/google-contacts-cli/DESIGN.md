# Design – google-contacts-cli

## Problem Statement

Managing Google Contacts from CLI enables automation, bulk operations, and integration with other tools like Gmail for recipient resolution.

## Key Design Decisions

### 1. Shared OAuth

Uses same OAuth credentials as other Google tools. One refresh token works across Gmail, Calendar, and Contacts.

### 2. Groups as Labels

Google Contacts UI calls them "labels" but the API uses "contactGroups". This tool accepts both names and resource IDs.

### 3. Automatic etag Handling

Updates require an etag to prevent conflicts. The tool auto-fetches the current contact to get the etag before updating.

### 4. Field Masks

Control which data is returned with `--fields`:
- `names` - Display names
- `emailAddresses` - Email addresses
- `phoneNumbers` - Phone numbers
- `organizations` - Company info

## Future Enhancements

- CSV import/export
- Photo management
- Merge duplicates

