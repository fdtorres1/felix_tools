# handwrytten-cli

A Python CLI tool for interacting with the [Handwrytten API](https://www.handwrytten.com/api/) – a service that sends AI-written handwritten cards to anyone.

## Summary

This tool allows you to:
- **List available cards** – Browse the card catalog with optional filtering
- **List fonts (handwriting styles)** – View available handwriting styles for your cards
- **List card categories** – Get organized card category listings
- **Send cards** – Create and send handwritten cards with a single command
- **Manage orders** – View order details and cancel pending orders
- **Manage address book** – Store and retrieve recipient addresses

## Use Cases

✅ **Use this tool when you want to:**
- Send personalized handwritten thank-you notes, birthday cards, or business correspondence
- Integrate handwritten card sending into automated workflows
- Browse available card designs and handwriting styles
- Manage a list of recipient addresses for repeated mailings

❌ **Don't use this tool for:**
- Sending digital-only communications (use email instead)
- High-volume bulk mailing without proper rate limiting
- Sending cards to invalid or unverified addresses

## Quickstart

### Prerequisites

- Python 3.9+
- A Handwrytten account with API access
- API key from [app.handwrytten.com](https://app.handwrytten.com) integrations menu

### Installation

```bash
cd tools/handwrytten-cli

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp env.example .env
# Edit .env with your API key
```

### Usage

```bash
# List available cards
python src/handwrytten.py cards list

# List cards with images included
python src/handwrytten.py cards list --with-images

# List available fonts (handwriting styles)
python src/handwrytten.py fonts list

# List card categories
python src/handwrytten.py categories list

# Get details for a specific card
python src/handwrytten.py cards get --card-id 3404

# Send a card (single step order)
python src/handwrytten.py orders send \
    --card-id 3404 \
    --message "Dear John,\n\nThank you for your support!" \
    --wishes "Best regards" \
    --font-label "Chill Charles" \
    --recipient-name "John Doe" \
    --recipient-address1 "123 Main St" \
    --recipient-city "Phoenix" \
    --recipient-state "AZ" \
    --recipient-zip "85001" \
    --recipient-country "United States"

# Get order details
python src/handwrytten.py orders get --order-id 12345

# Cancel an order
python src/handwrytten.py orders cancel --order-id 12345

# List address book entries
python src/handwrytten.py addresses list

# Add an address to address book
python src/handwrytten.py addresses add \
    --name "Jane Smith" \
    --address1 "456 Oak Ave" \
    --city "Los Angeles" \
    --state "CA" \
    --zip "90001" \
    --country "United States"
```

### Output Formats

The CLI supports multiple output formats:

```bash
# Default: JSON output
python src/handwrytten.py cards list

# Table format for human-readable output
python src/handwrytten.py cards list --format table

# Quiet mode (minimal output, useful for scripts)
python src/handwrytten.py orders send ... --quiet
```

## Examples

### Send a Thank You Card

```bash
python src/handwrytten.py orders send \
    --card-id 3404 \
    --message "Dear Sarah,\n\nThank you so much for your generous donation to our program. Your support makes a real difference in our community.\n\nWith gratitude" \
    --wishes "Felix Torres\nCaminos del Inka" \
    --font-label "Chill Charles" \
    --recipient-name "Sarah Johnson" \
    --recipient-address1 "789 Elm Street" \
    --recipient-city "Austin" \
    --recipient-state "TX" \
    --recipient-zip "78701" \
    --recipient-country "United States" \
    --sender-name "Caminos del Inka" \
    --sender-address1 "100 Music Lane" \
    --sender-city "Fort Worth" \
    --sender-state "TX" \
    --sender-zip "76102"
```

### Browse Cards by Category

```bash
# List all categories first
python src/handwrytten.py categories list

# Then list cards in a specific category
python src/handwrytten.py cards list --category-id 5 --with-images
```

## API Reference

This tool wraps the [Handwrytten API v2](https://www.handwrytten.com/api/). Key endpoints used:

| Command | API Endpoint | Description |
|---------|--------------|-------------|
| `cards list` | GET /cards/list | List available cards |
| `cards get` | GET /cards/detail | Get card details |
| `categories list` | GET /cards/categories | List card categories |
| `fonts list` | GET /fonts/list | List handwriting styles |
| `orders send` | POST /orders/singleStepOrder | Send a card |
| `orders get` | GET /orders/detail | Get order details |
| `orders cancel` | POST /orders/cancel | Cancel an order |
| `addresses list` | GET /addressbook/list | List saved addresses |
| `addresses add` | POST /addressbook/add | Add new address |

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for general contribution guidelines.

## License

Internal tool – not for public distribution.

