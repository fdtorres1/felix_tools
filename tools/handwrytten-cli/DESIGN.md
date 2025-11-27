# Design – handwrytten-cli

## Problem Statement

We need a command-line interface to interact with the Handwrytten API for sending AI-written handwritten cards. This enables:
1. Quick card sending without using the web interface
2. Integration with automated workflows (e.g., donor thank-you cards)
3. Batch operations and scripting capabilities
4. Easy lookup of cards, fonts, and categories

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CLI Interface                         │
│  (argparse-based command parser)                        │
├─────────────────────────────────────────────────────────┤
│                   Command Handlers                       │
│  cards | fonts | categories | orders | addresses        │
├─────────────────────────────────────────────────────────┤
│                 Handwrytten API Client                  │
│  (HTTP client with auth, error handling, retry logic)   │
├─────────────────────────────────────────────────────────┤
│                  Configuration Layer                     │
│  (Environment variables, .env file loading)             │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Handwrytten API     │
              │  api.handwrytten.com  │
              └───────────────────────┘
```

## Key Components

### 1. CLI Interface (`handwrytten.py`)

Single-file Python CLI using `argparse` for command parsing. Commands organized hierarchically:

```
handwrytten
├── cards
│   ├── list [--category-id] [--with-images] [--page]
│   └── get --card-id
├── fonts
│   └── list
├── categories
│   └── list
├── orders
│   ├── send --card-id --message [many options]
│   ├── get --order-id
│   └── cancel --order-id
└── addresses
    ├── list
    └── add --name --address1 --city --state --zip [--country]
```

### 2. API Client

Embedded in the main file for simplicity. Key features:
- **Authentication**: API key passed via Authorization header
- **Error handling**: HTTP errors mapped to meaningful CLI errors
- **Response parsing**: JSON response handling with status checking
- **Retry logic**: Optional retry for transient failures

### 3. Output Formatting

Two output modes:
- **JSON** (default): Raw API responses for programmatic use
- **Table**: Human-readable tabular format using `tabulate`

## API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/cards/list` | GET | List available cards |
| `/cards/detail` | GET | Get single card details |
| `/cards/categories` | GET | List card categories |
| `/fonts/list` | GET | List handwriting fonts |
| `/orders/singleStepOrder` | POST | Create and send a card |
| `/orders/detail` | GET | Get order details |
| `/orders/cancel` | POST | Cancel pending order |
| `/addressbook/list` | GET | List saved addresses |
| `/addressbook/add` | POST | Add new address |

## Data Flows

### Send Card Flow

```
1. User runs: handwrytten orders send --card-id 3404 --message "..." ...
2. CLI validates required parameters
3. CLI builds JSON payload:
   {
     "card_id": 3404,
     "message": "...",
     "wishes": "...",
     "font_label": "...",
     "recipient_first_name": "...",
     "recipient_last_name": "...",
     "recipient_address1": "...",
     ...
   }
4. POST to /orders/singleStepOrder
5. Parse response, display order ID and status
```

### List Cards Flow

```
1. User runs: handwrytten cards list --category-id 5 --with-images
2. CLI builds query params: ?category_id=5&with_images=true
3. GET /cards/list
4. Parse response, format as JSON or table
5. Display cards with id, name, description, image URLs
```

## Error Handling

| Error Type | Handling |
|------------|----------|
| Missing API key | Exit with clear message about configuration |
| Invalid API key | Display authentication error from API |
| Invalid card_id | Display API error message |
| Network timeout | Retry up to 3 times, then fail with message |
| Invalid address | Display validation error from API |
| Rate limiting | Display rate limit message, suggest waiting |

## Security Considerations

1. **API Key Storage**: Keys stored in `.env` file, never committed to git
2. **No Secrets in Code**: All credentials via environment variables
3. **HTTPS Only**: All API calls over TLS
4. **Input Validation**: Basic validation before API calls

## Trade-offs and Decisions

### Single File vs. Module Structure
**Decision**: Single file (`handwrytten.py`)
**Rationale**: Simpler for a focused CLI tool, easier to understand and maintain, follows patterns of other tools in this repo.

### Direct API Calls vs. SDK
**Decision**: Direct HTTP calls using `requests`
**Rationale**: Handwrytten doesn't provide an official Python SDK. Direct calls give us full control and transparency.

### Output Format
**Decision**: JSON default with optional table format
**Rationale**: JSON is machine-readable for scripting; table format aids human exploration.

## Future Enhancements

- [ ] Batch sending from CSV file
- [ ] Template support for common messages
- [ ] Webhook registration for order status updates
- [ ] Address book import/export
- [ ] Custom card creation workflow

