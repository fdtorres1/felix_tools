# Shopify CLI

A command-line interface for Shopify Admin operations using the GraphQL API.

## Overview

This tool enables you to query and manage products, customers, orders, collections, metafields, and more from the command line.

## Use Cases

- **Product management**: Search, list, export products
- **Order operations**: Query orders, manage fulfillments
- **Content management**: Pages, blogs, articles, collections
- **Metafields**: Get and set custom metafields
- **Data export**: JSONL and CSV exports

## Quickstart

### Installation

```bash
source ~/.venvs/felix-tools/bin/activate
pip install -r ../../tools/shared-requirements.txt
```

### Configuration

Add to `~/AGENTS.env`:
```bash
SHOPIFY_SHOP=myshop.myshopify.com
SHOPIFY_ADMIN_TOKEN=shpat_your_admin_token
SHOPIFY_API_VERSION=2024-07  # optional
```

### Basic Usage

```bash
# Auth check
python src/shopify.py auth

# List products
python src/shopify.py products list --limit 10

# Search products
python src/shopify.py products list --query 'vendor:Acme' --jsonl /tmp/products.jsonl
```

## Examples

### Products

```bash
# List all products (paginated)
python src/shopify.py products list --all --jsonl /tmp/all_products.jsonl

# Search by vendor
python src/shopify.py products list --query 'vendor:Acme' --csv /tmp/acme.csv --fields id,title,vendor

# Export specific fields
python src/shopify.py products list --query 'tag:featured' --fields id,title,handle,vendor,productType,createdAt
```

### Customers

```bash
# List customers
python src/shopify.py customers list --limit 100 --jsonl /tmp/customers.jsonl

# Search by email
python src/shopify.py customers list --query 'email:*@example.com'
```

### Orders

```bash
# List orders
python src/shopify.py orders list --query 'tag:VIP' --jsonl /tmp/vip_orders.jsonl

# List fulfillment orders
python src/shopify.py orders fulfillment-orders --order-name '#1001'

# Set fulfillment deadline
python src/shopify.py orders set-fulfillment-deadline \
  --fo-id 'gid://shopify/FulfillmentOrder/123' \
  --deadline '2025-01-20T17:00:00Z' --dry-run
```

### Collections

```bash
# List collections
python src/shopify.py collections list --csv /tmp/collections.csv

# Search by title
python src/shopify.py collections list --query 'title:Featured'

# Create collection
python src/shopify.py collections create --title 'New Arrivals' --handle 'new-arrivals' --dry-run

# Update collection image
python src/shopify.py collections update --handle 'featured' \
  --image-src 'https://example.com/image.jpg' --image-alt 'Featured collection'
```

### Metafields

```bash
# Get metafield
python src/shopify.py metafield get --owner-id 'gid://shopify/Product/123' --ns custom --key note

# Set metafield (dry-run)
python src/shopify.py metafield set \
  --owner-id 'gid://shopify/Product/123' \
  --ns custom --key note \
  --type single_line_text_field \
  --value 'Custom note' --dry-run
```

### Content

```bash
# List pages
python src/shopify.py pages list --jsonl /tmp/pages.jsonl

# List blogs
python src/shopify.py blogs list

# List articles
python src/shopify.py articles list --blog-id 'gid://shopify/Blog/123'

# Create blog
python src/shopify.py blogs create --title 'News' --handle news --dry-run

# Create article
python src/shopify.py articles create --blog-handle news --title 'Hello World' --body '<p>Welcome</p>' --dry-run
```

### Raw GraphQL

```bash
# Execute custom query
python src/shopify.py query --file queries/custom_query.graphql
```

## Command Reference

| Command | Description |
|---------|-------------|
| `auth` | Verify credentials |
| `query` | Run GraphQL query |
| `products list` | List/search products |
| `customers list` | List/search customers |
| `orders list` | List/search orders |
| `orders fulfillment-orders` | List fulfillment orders |
| `orders set-fulfillment-deadline` | Set deadline |
| `metafield get/set` | Manage metafields |
| `pages list` | List pages |
| `blogs list/create/update` | Manage blogs |
| `articles list/create/update` | Manage articles |
| `collections list/create/update` | Manage collections |

## Notes

- **Dry-run**: Add `--dry-run` for mutations to preview
- **Pagination**: Use `--all` to fetch all pages
- **Export formats**: `--jsonl` for line-delimited JSON, `--csv` for CSV

See [CONFIG.md](CONFIG.md) for all configuration options.

