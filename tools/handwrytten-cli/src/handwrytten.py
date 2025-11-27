#!/usr/bin/env python3
"""
handwrytten-cli - CLI tool for the Handwrytten API

Send AI-written handwritten cards via the Handwrytten service.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv
from tabulate import tabulate

# Load environment from .env file in tool directory
TOOL_DIR = Path(__file__).parent.parent
load_dotenv(TOOL_DIR / ".env")

# Configuration
API_BASE_URL = os.getenv("HANDWRYTTEN_API_URL", "https://api.handwrytten.com/v2")
API_KEY = os.getenv("HANDWRYTTEN_API_KEY", "")
TEST_MODE = os.getenv("HANDWRYTTEN_TEST_MODE", "false").lower() == "true"

# Default sender info from environment
DEFAULT_SENDER = {
    "name": os.getenv("HANDWRYTTEN_SENDER_NAME", ""),
    "address1": os.getenv("HANDWRYTTEN_SENDER_ADDRESS1", ""),
    "address2": os.getenv("HANDWRYTTEN_SENDER_ADDRESS2", ""),
    "city": os.getenv("HANDWRYTTEN_SENDER_CITY", ""),
    "state": os.getenv("HANDWRYTTEN_SENDER_STATE", ""),
    "zip": os.getenv("HANDWRYTTEN_SENDER_ZIP", ""),
    "country": os.getenv("HANDWRYTTEN_SENDER_COUNTRY", "United States"),
}


class HandwryttenError(Exception):
    """Custom exception for Handwrytten API errors."""
    pass


class HandwryttenClient:
    """Client for the Handwrytten API."""

    def __init__(self, api_key: str, base_url: str = API_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
    ) -> dict:
        """Make an API request."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            
            # Check for API-level errors
            if result.get("status") == "error":
                raise HandwryttenError(result.get("message", "Unknown API error"))
            
            return result
            
        except requests.exceptions.HTTPError as e:
            error_msg = str(e)
            try:
                error_data = e.response.json()
                error_msg = error_data.get("message", error_msg)
            except (ValueError, AttributeError):
                pass
            raise HandwryttenError(f"API error: {error_msg}")
        except requests.exceptions.RequestException as e:
            raise HandwryttenError(f"Network error: {e}")

    def get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make a GET request."""
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, data: Optional[dict] = None) -> dict:
        """Make a POST request."""
        return self._request("POST", endpoint, data=data)

    # Cards
    def list_cards(
        self,
        category_id: Optional[int] = None,
        with_images: bool = False,
        with_detailed_images: bool = False,
        page: int = 0,
        lowres: bool = False,
    ) -> dict:
        """List available cards."""
        params = {"page": page}
        if category_id is not None:
            params["category_id"] = category_id
        if with_images:
            params["with_images"] = "true"
        if with_detailed_images:
            params["with_detailed_images"] = "true"
        if lowres:
            params["lowres"] = "true"
        return self.get("/cards/list", params)

    def get_card(self, card_id: int) -> dict:
        """Get card details."""
        return self.get("/cards/detail", {"card_id": card_id})

    def list_categories(self) -> dict:
        """List card categories."""
        return self.get("/cards/categories")

    def list_signatures(self) -> dict:
        """List available signatures."""
        return self.get("/cards/signatures")

    # Fonts
    def list_fonts(self) -> dict:
        """List available fonts (handwriting styles)."""
        return self.get("/fonts/list")

    # Orders
    def send_card(
        self,
        card_id: int,
        message: str,
        recipient_first_name: str,
        recipient_last_name: str,
        recipient_address1: str,
        recipient_city: str,
        recipient_state: str,
        recipient_zip: str,
        recipient_country: str = "United States",
        recipient_address2: str = "",
        wishes: str = "",
        font_label: str = "",
        sender_first_name: str = "",
        sender_last_name: str = "",
        sender_address1: str = "",
        sender_address2: str = "",
        sender_city: str = "",
        sender_state: str = "",
        sender_zip: str = "",
        sender_country: str = "United States",
        date_send: str = "",
        validate_address: bool = True,
        denomination_id: Optional[int] = None,
        insert_id: Optional[int] = None,
        coupon_code: str = "",
    ) -> dict:
        """Send a card using single step order."""
        data = {
            "card_id": card_id,
            "message": message,
            "recipient_first_name": recipient_first_name,
            "recipient_last_name": recipient_last_name,
            "recipient_address1": recipient_address1,
            "recipient_city": recipient_city,
            "recipient_state": recipient_state,
            "recipient_zip": recipient_zip,
            "recipient_country_id": self._country_to_id(recipient_country),
            "validate_address": validate_address,
        }

        if recipient_address2:
            data["recipient_address2"] = recipient_address2
        if wishes:
            data["wishes"] = wishes
        if font_label:
            data["font_label"] = font_label
        if sender_first_name:
            data["sender_first_name"] = sender_first_name
        if sender_last_name:
            data["sender_last_name"] = sender_last_name
        if sender_address1:
            data["sender_address1"] = sender_address1
        if sender_address2:
            data["sender_address2"] = sender_address2
        if sender_city:
            data["sender_city"] = sender_city
        if sender_state:
            data["sender_state"] = sender_state
        if sender_zip:
            data["sender_zip"] = sender_zip
        if sender_country:
            data["sender_country_id"] = self._country_to_id(sender_country)
        if date_send:
            data["date_send"] = date_send
        if denomination_id is not None:
            data["denomination_id"] = denomination_id
        if insert_id is not None:
            data["insert_id"] = insert_id
        if coupon_code:
            data["couponCode"] = coupon_code

        return self.post("/orders/singleStepOrder", data)

    def get_order(self, order_id: int) -> dict:
        """Get order details."""
        return self.get("/orders/detail", {"order_id": order_id})

    def cancel_order(self, order_id: int) -> dict:
        """Cancel an order."""
        return self.post("/orders/cancel", {"order_id": order_id})

    # Address Book
    def list_addresses(self, page: int = 0) -> dict:
        """List address book entries."""
        return self.get("/addressbook/list", {"page": page})

    def add_address(
        self,
        first_name: str,
        last_name: str,
        address1: str,
        city: str,
        state: str,
        zip_code: str,
        country: str = "United States",
        address2: str = "",
        company: str = "",
    ) -> dict:
        """Add an address to the address book."""
        data = {
            "first_name": first_name,
            "last_name": last_name,
            "address1": address1,
            "city": city,
            "state": state,
            "zip": zip_code,
            "country_id": self._country_to_id(country),
        }
        if address2:
            data["address2"] = address2
        if company:
            data["company"] = company
        return self.post("/addressbook/add", data)

    @staticmethod
    def _country_to_id(country: str) -> int:
        """Convert country name to Handwrytten country ID."""
        # Common country mappings - US is 1
        countries = {
            "united states": 1,
            "usa": 1,
            "us": 1,
            "canada": 2,
            "united kingdom": 3,
            "uk": 3,
            "australia": 4,
        }
        return countries.get(country.lower(), 1)


def format_output(data: Any, fmt: str = "json") -> str:
    """Format output data."""
    if fmt == "json":
        return json.dumps(data, indent=2)
    elif fmt == "table":
        if isinstance(data, dict):
            # Handle API response with nested data
            if "cards" in data:
                items = data["cards"]
                if items:
                    headers = ["ID", "Name", "Description", "Price"]
                    rows = [
                        [
                            c.get("id", ""),
                            c.get("card_name", c.get("name", ""))[:40],
                            (c.get("description", "") or "")[:50],
                            c.get("price", ""),
                        ]
                        for c in items
                    ]
                    return tabulate(rows, headers=headers, tablefmt="grid")
            elif "fonts" in data:
                items = data["fonts"]
                if items:
                    headers = ["ID", "Label", "Line Spacing"]
                    rows = [
                        [f.get("id", ""), f.get("label", ""), f.get("line_spacing", "")]
                        for f in items
                    ]
                    return tabulate(rows, headers=headers, tablefmt="grid")
            elif "categories" in data:
                items = data["categories"]
                if items:
                    headers = ["ID", "Name"]
                    rows = [[c.get("id", ""), c.get("name", "")] for c in items]
                    return tabulate(rows, headers=headers, tablefmt="grid")
            elif "addresses" in data:
                items = data["addresses"]
                if items:
                    headers = ["ID", "Name", "Address", "City", "State", "ZIP"]
                    rows = [
                        [
                            a.get("id", ""),
                            f"{a.get('first_name', '')} {a.get('last_name', '')}",
                            a.get("address1", ""),
                            a.get("city", ""),
                            a.get("state", ""),
                            a.get("zip", ""),
                        ]
                        for a in items
                    ]
                    return tabulate(rows, headers=headers, tablefmt="grid")
            # Default dict formatting
            rows = [[k, str(v)[:80]] for k, v in data.items()]
            return tabulate(rows, headers=["Key", "Value"], tablefmt="grid")
        return str(data)
    return str(data)


def split_name(full_name: str) -> tuple[str, str]:
    """Split a full name into first and last name."""
    parts = full_name.strip().split(None, 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    elif len(parts) == 1:
        return parts[0], ""
    return "", ""


# Command handlers
def cmd_cards_list(client: HandwryttenClient, args: argparse.Namespace) -> dict:
    """List available cards."""
    return client.list_cards(
        category_id=args.category_id,
        with_images=args.with_images,
        with_detailed_images=args.with_detailed_images,
        page=args.page,
        lowres=args.lowres,
    )


def cmd_cards_get(client: HandwryttenClient, args: argparse.Namespace) -> dict:
    """Get card details."""
    return client.get_card(args.card_id)


def cmd_fonts_list(client: HandwryttenClient, args: argparse.Namespace) -> dict:
    """List available fonts."""
    return client.list_fonts()


def cmd_categories_list(client: HandwryttenClient, args: argparse.Namespace) -> dict:
    """List card categories."""
    return client.list_categories()


def cmd_signatures_list(client: HandwryttenClient, args: argparse.Namespace) -> dict:
    """List available signatures."""
    return client.list_signatures()


def cmd_orders_send(client: HandwryttenClient, args: argparse.Namespace) -> dict:
    """Send a card."""
    # Parse recipient name
    r_first, r_last = split_name(args.recipient_name)
    
    # Parse sender name (use defaults if not provided)
    if args.sender_name:
        s_first, s_last = split_name(args.sender_name)
    else:
        s_first, s_last = split_name(DEFAULT_SENDER["name"])
    
    return client.send_card(
        card_id=args.card_id,
        message=args.message,
        recipient_first_name=r_first,
        recipient_last_name=r_last,
        recipient_address1=args.recipient_address1,
        recipient_address2=args.recipient_address2 or "",
        recipient_city=args.recipient_city,
        recipient_state=args.recipient_state,
        recipient_zip=args.recipient_zip,
        recipient_country=args.recipient_country,
        wishes=args.wishes or "",
        font_label=args.font_label or "",
        sender_first_name=s_first,
        sender_last_name=s_last,
        sender_address1=args.sender_address1 or DEFAULT_SENDER["address1"],
        sender_address2=args.sender_address2 or DEFAULT_SENDER["address2"],
        sender_city=args.sender_city or DEFAULT_SENDER["city"],
        sender_state=args.sender_state or DEFAULT_SENDER["state"],
        sender_zip=args.sender_zip or DEFAULT_SENDER["zip"],
        sender_country=args.sender_country or DEFAULT_SENDER["country"],
        date_send=args.date_send or "",
        validate_address=not args.skip_validation,
        denomination_id=args.denomination_id,
        insert_id=args.insert_id,
        coupon_code=args.coupon_code or "",
    )


def cmd_orders_get(client: HandwryttenClient, args: argparse.Namespace) -> dict:
    """Get order details."""
    return client.get_order(args.order_id)


def cmd_orders_cancel(client: HandwryttenClient, args: argparse.Namespace) -> dict:
    """Cancel an order."""
    return client.cancel_order(args.order_id)


def cmd_addresses_list(client: HandwryttenClient, args: argparse.Namespace) -> dict:
    """List address book entries."""
    return client.list_addresses(page=args.page)


def cmd_addresses_add(client: HandwryttenClient, args: argparse.Namespace) -> dict:
    """Add an address to the address book."""
    first, last = split_name(args.name)
    return client.add_address(
        first_name=first,
        last_name=last,
        address1=args.address1,
        address2=args.address2 or "",
        city=args.city,
        state=args.state,
        zip_code=args.zip,
        country=args.country,
        company=args.company or "",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="CLI tool for the Handwrytten API - send handwritten cards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "table"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress non-essential output",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Cards commands
    cards_parser = subparsers.add_parser("cards", help="Card operations")
    cards_sub = cards_parser.add_subparsers(dest="subcommand")

    # cards list
    cards_list = cards_sub.add_parser("list", help="List available cards")
    cards_list.add_argument("--category-id", type=int, help="Filter by category ID")
    cards_list.add_argument("--with-images", action="store_true", help="Include image URLs")
    cards_list.add_argument("--with-detailed-images", action="store_true", help="Include detailed image URLs")
    cards_list.add_argument("--page", type=int, default=0, help="Page number (starts at 0)")
    cards_list.add_argument("--lowres", action="store_true", help="Use low resolution images")
    cards_list.set_defaults(func=cmd_cards_list)

    # cards get
    cards_get = cards_sub.add_parser("get", help="Get card details")
    cards_get.add_argument("--card-id", type=int, required=True, help="Card ID")
    cards_get.set_defaults(func=cmd_cards_get)

    # Fonts commands
    fonts_parser = subparsers.add_parser("fonts", help="Font (handwriting style) operations")
    fonts_sub = fonts_parser.add_subparsers(dest="subcommand")

    # fonts list
    fonts_list = fonts_sub.add_parser("list", help="List available fonts")
    fonts_list.set_defaults(func=cmd_fonts_list)

    # Categories commands
    cat_parser = subparsers.add_parser("categories", help="Card category operations")
    cat_sub = cat_parser.add_subparsers(dest="subcommand")

    # categories list
    cat_list = cat_sub.add_parser("list", help="List card categories")
    cat_list.set_defaults(func=cmd_categories_list)

    # Signatures commands
    sig_parser = subparsers.add_parser("signatures", help="Signature operations")
    sig_sub = sig_parser.add_subparsers(dest="subcommand")

    # signatures list
    sig_list = sig_sub.add_parser("list", help="List available signatures")
    sig_list.set_defaults(func=cmd_signatures_list)

    # Orders commands
    orders_parser = subparsers.add_parser("orders", help="Order operations")
    orders_sub = orders_parser.add_subparsers(dest="subcommand")

    # orders send
    orders_send = orders_sub.add_parser("send", help="Send a card")
    orders_send.add_argument("--card-id", type=int, required=True, help="Card ID to send")
    orders_send.add_argument("--message", required=True, help="Card message (use \\n for newlines)")
    orders_send.add_argument("--wishes", help="Closing/wishes text (right-aligned)")
    orders_send.add_argument("--font-label", help="Font/handwriting style label")
    # Recipient
    orders_send.add_argument("--recipient-name", required=True, help="Recipient full name")
    orders_send.add_argument("--recipient-address1", required=True, help="Recipient address line 1")
    orders_send.add_argument("--recipient-address2", help="Recipient address line 2")
    orders_send.add_argument("--recipient-city", required=True, help="Recipient city")
    orders_send.add_argument("--recipient-state", required=True, help="Recipient state")
    orders_send.add_argument("--recipient-zip", required=True, help="Recipient ZIP code")
    orders_send.add_argument("--recipient-country", default="United States", help="Recipient country")
    # Sender
    orders_send.add_argument("--sender-name", help="Sender full name")
    orders_send.add_argument("--sender-address1", help="Sender address line 1")
    orders_send.add_argument("--sender-address2", help="Sender address line 2")
    orders_send.add_argument("--sender-city", help="Sender city")
    orders_send.add_argument("--sender-state", help="Sender state")
    orders_send.add_argument("--sender-zip", help="Sender ZIP code")
    orders_send.add_argument("--sender-country", help="Sender country")
    # Options
    orders_send.add_argument("--date-send", help="Scheduled send date (ISO format)")
    orders_send.add_argument("--skip-validation", action="store_true", help="Skip address validation")
    orders_send.add_argument("--denomination-id", type=int, help="Gift card denomination ID")
    orders_send.add_argument("--insert-id", type=int, help="Insert ID to include")
    orders_send.add_argument("--coupon-code", help="Coupon code to apply")
    orders_send.set_defaults(func=cmd_orders_send)

    # orders get
    orders_get = orders_sub.add_parser("get", help="Get order details")
    orders_get.add_argument("--order-id", type=int, required=True, help="Order ID")
    orders_get.set_defaults(func=cmd_orders_get)

    # orders cancel
    orders_cancel = orders_sub.add_parser("cancel", help="Cancel an order")
    orders_cancel.add_argument("--order-id", type=int, required=True, help="Order ID to cancel")
    orders_cancel.set_defaults(func=cmd_orders_cancel)

    # Addresses commands
    addr_parser = subparsers.add_parser("addresses", help="Address book operations")
    addr_sub = addr_parser.add_subparsers(dest="subcommand")

    # addresses list
    addr_list = addr_sub.add_parser("list", help="List address book entries")
    addr_list.add_argument("--page", type=int, default=0, help="Page number (starts at 0)")
    addr_list.set_defaults(func=cmd_addresses_list)

    # addresses add
    addr_add = addr_sub.add_parser("add", help="Add an address")
    addr_add.add_argument("--name", required=True, help="Full name")
    addr_add.add_argument("--address1", required=True, help="Address line 1")
    addr_add.add_argument("--address2", help="Address line 2")
    addr_add.add_argument("--city", required=True, help="City")
    addr_add.add_argument("--state", required=True, help="State")
    addr_add.add_argument("--zip", required=True, help="ZIP code")
    addr_add.add_argument("--country", default="United States", help="Country")
    addr_add.add_argument("--company", help="Company name")
    addr_add.set_defaults(func=cmd_addresses_add)

    return parser


def main():
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    # Check for command
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Check for subcommand
    if not hasattr(args, "func"):
        # Print help for the command
        parser.parse_args([args.command, "--help"])
        sys.exit(1)

    # Check for API key
    if not API_KEY:
        print("Error: HANDWRYTTEN_API_KEY environment variable not set.", file=sys.stderr)
        print("Please set it in your .env file or environment.", file=sys.stderr)
        sys.exit(1)

    # Create client and execute command
    client = HandwryttenClient(API_KEY)

    try:
        result = args.func(client, args)
        output = format_output(result, args.format)
        if not args.quiet or args.format == "json":
            print(output)
    except HandwryttenError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()

