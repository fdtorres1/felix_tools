#!/usr/bin/env python3
"""
Givebutter CLI - Command-line interface for the Givebutter nonprofit fundraising API.

Usage:
    givebutter.py campaigns [list|get|create|update|delete] [options]
    givebutter.py contacts [list|get|create|update|archive|restore] [options]
    givebutter.py transactions [list|get|create] [options]
    givebutter.py funds [list|get|create|update|delete] [options]
    givebutter.py plans [list|get] [options]
    givebutter.py payouts [list|get] [options]
    givebutter.py tickets [list|get] [options]
    givebutter.py members [list|get|delete] [options]
    givebutter.py teams [list|get] [options]

Environment:
    GIVEBUTTER_API_KEY  - Required: Your Givebutter API key
    AGENTS_ENV_PATH     - Optional: Path to env file (default: ~/AGENTS.env)
    TELEGRAM_BOT_TOKEN  - Optional: For error notifications
    TELEGRAM_CHAT_ID    - Optional: For error notifications
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL = "https://api.givebutter.com/v1"


def load_agents_env():
    """Load environment variables from ~/AGENTS.env or specified path."""
    env_path = os.environ.get("AGENTS_ENV_PATH", os.path.expanduser("~/AGENTS.env"))
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    # Handle export VAR=value syntax
                    if line.startswith("export "):
                        line = line[7:]
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value


def get_api_key():
    """Get the Givebutter API key from environment."""
    key = os.environ.get("GIVEBUTTER_API_KEY") or os.environ.get("GIVEBUTTER_TOKEN")
    if not key:
        print("Error: GIVEBUTTER_API_KEY environment variable not set", file=sys.stderr)
        print("Get your API key from Givebutter Dashboard > Settings > API", file=sys.stderr)
        sys.exit(1)
    return key


def headers():
    """Return standard API headers."""
    return {
        "Authorization": f"Bearer {get_api_key()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────────────────────────

def notify_telegram(message: str):
    """Send a notification via Telegram if configured."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def notify_macos(title: str, message: str):
    """Send a macOS notification if terminal-notifier is available."""
    try:
        import subprocess
        subprocess.run(
            ["terminal-notifier", "-title", title, "-message", message, "-sound", "default"],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# HTTP Helpers
# ─────────────────────────────────────────────────────────────────────────────

def http_request(method: str, endpoint: str, data: dict = None, params: dict = None):
    """Make an HTTP request to the Givebutter API."""
    url = f"{BASE_URL}{endpoint}"
    
    # Add query parameters
    if params:
        filtered_params = {k: v for k, v in params.items() if v is not None}
        if filtered_params:
            url += "?" + urllib.parse.urlencode(filtered_params)
    
    body = None
    if data:
        body = json.dumps(data).encode("utf-8")
    
    req = urllib.request.Request(url, data=body, headers=headers(), method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 204:  # No content
                return None
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        try:
            error_json = json.loads(error_body)
            error_msg = error_json.get("message", error_body)
        except json.JSONDecodeError:
            error_msg = error_body or str(e)
        
        msg = f"Givebutter API error ({e.code}): {error_msg}"
        notify_telegram(f"❌ givebutter-cli: {msg}")
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        msg = f"Network error: {e.reason}"
        notify_telegram(f"❌ givebutter-cli: {msg}")
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)


def http_get(endpoint: str, params: dict = None):
    """GET request wrapper."""
    return http_request("GET", endpoint, params=params)


def http_post(endpoint: str, data: dict):
    """POST request wrapper."""
    return http_request("POST", endpoint, data=data)


def http_patch(endpoint: str, data: dict):
    """PATCH request wrapper."""
    return http_request("PATCH", endpoint, data=data)


def http_delete(endpoint: str):
    """DELETE request wrapper."""
    return http_request("DELETE", endpoint)


# ─────────────────────────────────────────────────────────────────────────────
# Output Helpers
# ─────────────────────────────────────────────────────────────────────────────

def output_json(data, pretty: bool = True):
    """Output data as JSON."""
    if pretty:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(json.dumps(data, default=str))


def output_jsonl(items: list):
    """Output items as JSON Lines."""
    for item in items:
        print(json.dumps(item, default=str))


def output_csv(items: list, fields: list = None):
    """Output items as CSV."""
    if not items:
        return
    
    if not fields:
        fields = list(items[0].keys())
    
    # Header
    print(",".join(fields))
    
    # Rows
    for item in items:
        row = []
        for f in fields:
            val = item.get(f, "")
            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            val = str(val).replace('"', '""')
            if "," in val or '"' in val or "\n" in val:
                val = f'"{val}"'
            row.append(val)
        print(",".join(row))


def paginate_all(endpoint: str, params: dict = None, data_key: str = "data"):
    """Fetch all pages of a paginated endpoint."""
    params = params or {}
    all_items = []
    page = 1
    
    while True:
        params["page"] = page
        result = http_get(endpoint, params)
        
        items = result.get(data_key, [])
        if not items:
            break
        
        all_items.extend(items)
        
        # Check for more pages
        meta = result.get("meta", {})
        current_page = meta.get("current_page", page)
        last_page = meta.get("last_page", page)
        
        if current_page >= last_page:
            break
        
        page += 1
    
    return all_items


# ─────────────────────────────────────────────────────────────────────────────
# Campaigns Commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_campaigns_list(args):
    """List all campaigns."""
    params = {}
    if args.limit:
        params["per_page"] = args.limit
    
    if args.all_pages:
        campaigns = paginate_all("/campaigns", params)
    else:
        result = http_get("/campaigns", params)
        campaigns = result.get("data", [])
    
    if args.format == "jsonl":
        output_jsonl(campaigns)
    elif args.format == "csv":
        output_csv(campaigns, ["id", "code", "title", "type", "status", "goal", "total", "created_at"])
    else:
        output_json(campaigns)


def cmd_campaigns_get(args):
    """Get a specific campaign."""
    result = http_get(f"/campaigns/{args.id}")
    output_json(result.get("data", result))


def cmd_campaigns_create(args):
    """Create a new campaign."""
    data = {
        "title": args.title,
        "type": args.type or "standard",
    }
    
    if args.goal:
        data["goal"] = args.goal
    if args.description:
        data["description"] = args.description
    if args.slug:
        data["slug"] = args.slug
    
    if args.dry_run:
        print("Dry run - would create campaign:")
        output_json(data)
        return
    
    result = http_post("/campaigns", data)
    output_json(result.get("data", result))
    
    if args.notify:
        notify_telegram(f"✅ Created Givebutter campaign: {args.title}")
        notify_macos("Givebutter", f"Created campaign: {args.title}")


def cmd_campaigns_update(args):
    """Update an existing campaign."""
    data = {}
    
    if args.title:
        data["title"] = args.title
    if args.goal:
        data["goal"] = args.goal
    if args.description:
        data["description"] = args.description
    if args.status:
        data["status"] = args.status
    
    if not data:
        print("Error: No fields to update specified", file=sys.stderr)
        sys.exit(1)
    
    if args.dry_run:
        print("Dry run - would update campaign:")
        output_json({"id": args.id, "updates": data})
        return
    
    result = http_patch(f"/campaigns/{args.id}", data)
    output_json(result.get("data", result))


def cmd_campaigns_delete(args):
    """Delete a campaign."""
    if args.dry_run:
        print(f"Dry run - would delete campaign: {args.id}")
        return
    
    http_delete(f"/campaigns/{args.id}")
    print(f"Deleted campaign: {args.id}")


# ─────────────────────────────────────────────────────────────────────────────
# Contacts Commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_contacts_list(args):
    """List all contacts."""
    params = {}
    if args.limit:
        params["per_page"] = args.limit
    if args.email:
        params["email"] = args.email
    
    if args.all_pages:
        contacts = paginate_all("/contacts", params)
    else:
        result = http_get("/contacts", params)
        contacts = result.get("data", [])
    
    if args.format == "jsonl":
        output_jsonl(contacts)
    elif args.format == "csv":
        output_csv(contacts, ["id", "first_name", "last_name", "email", "phone", "created_at"])
    else:
        output_json(contacts)


def cmd_contacts_get(args):
    """Get a specific contact."""
    result = http_get(f"/contacts/{args.id}")
    output_json(result.get("data", result))


def cmd_contacts_create(args):
    """Create a new contact."""
    data = {
        "email": args.email,
    }
    
    if args.first_name:
        data["first_name"] = args.first_name
    if args.last_name:
        data["last_name"] = args.last_name
    if args.phone:
        data["phone"] = args.phone
    if args.address:
        data["address"] = args.address
    if args.city:
        data["city"] = args.city
    if args.state:
        data["state"] = args.state
    if args.zip:
        data["zip"] = args.zip
    if args.country:
        data["country"] = args.country
    
    if args.dry_run:
        print("Dry run - would create contact:")
        output_json(data)
        return
    
    result = http_post("/contacts", data)
    output_json(result.get("data", result))


def cmd_contacts_update(args):
    """Update an existing contact."""
    data = {}
    
    if args.first_name:
        data["first_name"] = args.first_name
    if args.last_name:
        data["last_name"] = args.last_name
    if args.email:
        data["email"] = args.email
    if args.phone:
        data["phone"] = args.phone
    if args.address:
        data["address"] = args.address
    if args.city:
        data["city"] = args.city
    if args.state:
        data["state"] = args.state
    if args.zip:
        data["zip"] = args.zip
    if args.country:
        data["country"] = args.country
    
    if not data:
        print("Error: No fields to update specified", file=sys.stderr)
        sys.exit(1)
    
    if args.dry_run:
        print("Dry run - would update contact:")
        output_json({"id": args.id, "updates": data})
        return
    
    result = http_patch(f"/contacts/{args.id}", data)
    output_json(result.get("data", result))


def cmd_contacts_archive(args):
    """Archive a contact."""
    if args.dry_run:
        print(f"Dry run - would archive contact: {args.id}")
        return
    
    http_delete(f"/contacts/{args.id}")
    print(f"Archived contact: {args.id}")


def cmd_contacts_restore(args):
    """Restore an archived contact."""
    if args.dry_run:
        print(f"Dry run - would restore contact: {args.id}")
        return
    
    result = http_patch(f"/contacts/{args.id}/restore", {})
    output_json(result.get("data", result))


# ─────────────────────────────────────────────────────────────────────────────
# Transactions Commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_transactions_list(args):
    """List all transactions."""
    params = {}
    if args.limit:
        params["per_page"] = args.limit
    if args.campaign:
        params["campaign_code"] = args.campaign
    if args.contact:
        params["contact_id"] = args.contact
    if args.status:
        params["status"] = args.status
    
    if args.all_pages:
        transactions = paginate_all("/transactions", params)
    else:
        result = http_get("/transactions", params)
        transactions = result.get("data", [])
    
    if args.format == "jsonl":
        output_jsonl(transactions)
    elif args.format == "csv":
        output_csv(transactions, ["id", "giving_space", "amount", "fee", "status", "method", "captured_at", "first_name", "last_name", "email"])
    else:
        output_json(transactions)


def cmd_transactions_get(args):
    """Get a specific transaction."""
    result = http_get(f"/transactions/{args.id}")
    output_json(result.get("data", result))


def cmd_transactions_create(args):
    """Create a transaction (record-keeping only - does not charge donors)."""
    data = {
        "method": args.method or "donor_advised_fund",
    }
    
    # Campaign association
    if args.campaign:
        data["campaign_code"] = args.campaign
    
    # Donor info
    if args.first_name:
        data["first_name"] = args.first_name
    if args.last_name:
        data["last_name"] = args.last_name
    if args.email:
        data["email"] = args.email
    if args.phone:
        data["phone"] = args.phone
    
    # Address
    if args.address:
        data["address"] = args.address
    if args.city:
        data["city"] = args.city
    if args.state:
        data["state"] = args.state
    if args.zip:
        data["zip"] = args.zip
    if args.country:
        data["country"] = args.country
    
    # Transaction details
    if args.amount:
        data["amount"] = args.amount
    if args.fund:
        data["fund_id"] = args.fund
    if args.captured_at:
        data["captured_at"] = args.captured_at
    if args.dedication:
        data["dedication"] = args.dedication
    if args.note:
        data["note"] = args.note
    if args.anonymous:
        data["anonymous"] = args.anonymous
    
    if args.dry_run:
        print("Dry run - would create transaction:")
        output_json(data)
        return
    
    result = http_post("/transactions", data)
    output_json(result.get("data", result))
    
    if args.notify:
        amount = args.amount or "N/A"
        name = f"{args.first_name or ''} {args.last_name or ''}".strip() or "Anonymous"
        notify_telegram(f"✅ Created Givebutter transaction: ${amount} from {name}")


def cmd_transactions_import(args):
    """Bulk import transactions from a JSONL file."""
    import_file = Path(args.file)
    if not import_file.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    
    created = 0
    errors = 0
    
    with open(import_file) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Line {line_num}: Invalid JSON - {e}", file=sys.stderr)
                errors += 1
                continue
            
            # Set default method if not specified
            if "method" not in data:
                data["method"] = args.default_method or "donor_advised_fund"
            
            # Add campaign if specified and not in data
            if args.campaign and "campaign_code" not in data:
                data["campaign_code"] = args.campaign
            
            if args.dry_run:
                print(f"Line {line_num}: Would create transaction:")
                output_json(data)
                continue
            
            try:
                result = http_post("/transactions", data)
                created += 1
                tx_id = result.get("data", {}).get("id", "unknown")
                print(f"Line {line_num}: Created transaction {tx_id}")
            except SystemExit:
                errors += 1
                continue
    
    print(f"\nImport complete: {created} created, {errors} errors")


# ─────────────────────────────────────────────────────────────────────────────
# Funds Commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_funds_list(args):
    """List all funds."""
    params = {}
    if args.limit:
        params["per_page"] = args.limit
    
    if args.all_pages:
        funds = paginate_all("/funds", params)
    else:
        result = http_get("/funds", params)
        funds = result.get("data", [])
    
    if args.format == "jsonl":
        output_jsonl(funds)
    elif args.format == "csv":
        output_csv(funds, ["id", "title", "code", "total", "created_at"])
    else:
        output_json(funds)


def cmd_funds_get(args):
    """Get a specific fund."""
    result = http_get(f"/funds/{args.id}")
    output_json(result.get("data", result))


def cmd_funds_create(args):
    """Create a new fund."""
    data = {
        "title": args.title,
    }
    
    if args.description:
        data["description"] = args.description
    if args.goal:
        data["goal"] = args.goal
    
    if args.dry_run:
        print("Dry run - would create fund:")
        output_json(data)
        return
    
    result = http_post("/funds", data)
    output_json(result.get("data", result))


def cmd_funds_update(args):
    """Update an existing fund."""
    data = {}
    
    if args.title:
        data["title"] = args.title
    if args.description:
        data["description"] = args.description
    if args.goal:
        data["goal"] = args.goal
    
    if not data:
        print("Error: No fields to update specified", file=sys.stderr)
        sys.exit(1)
    
    if args.dry_run:
        print("Dry run - would update fund:")
        output_json({"id": args.id, "updates": data})
        return
    
    result = http_patch(f"/funds/{args.id}", data)
    output_json(result.get("data", result))


def cmd_funds_delete(args):
    """Delete a fund."""
    if args.dry_run:
        print(f"Dry run - would delete fund: {args.id}")
        return
    
    http_delete(f"/funds/{args.id}")
    print(f"Deleted fund: {args.id}")


# ─────────────────────────────────────────────────────────────────────────────
# Plans Commands (Recurring Donations)
# ─────────────────────────────────────────────────────────────────────────────

def cmd_plans_list(args):
    """List all recurring donation plans."""
    params = {}
    if args.limit:
        params["per_page"] = args.limit
    if args.status:
        params["status"] = args.status
    
    if args.all_pages:
        plans = paginate_all("/plans", params)
    else:
        result = http_get("/plans", params)
        plans = result.get("data", [])
    
    if args.format == "jsonl":
        output_jsonl(plans)
    elif args.format == "csv":
        output_csv(plans, ["id", "amount", "frequency", "status", "next_billing_date", "first_name", "last_name", "email"])
    else:
        output_json(plans)


def cmd_plans_get(args):
    """Get a specific recurring plan."""
    result = http_get(f"/plans/{args.id}")
    output_json(result.get("data", result))


# ─────────────────────────────────────────────────────────────────────────────
# Payouts Commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_payouts_list(args):
    """List all payouts."""
    params = {}
    if args.limit:
        params["per_page"] = args.limit
    
    if args.all_pages:
        payouts = paginate_all("/payouts", params)
    else:
        result = http_get("/payouts", params)
        payouts = result.get("data", [])
    
    if args.format == "jsonl":
        output_jsonl(payouts)
    elif args.format == "csv":
        output_csv(payouts, ["id", "amount", "status", "arrival_date", "created_at"])
    else:
        output_json(payouts)


def cmd_payouts_get(args):
    """Get a specific payout."""
    result = http_get(f"/payouts/{args.id}")
    output_json(result.get("data", result))


# ─────────────────────────────────────────────────────────────────────────────
# Tickets Commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_tickets_list(args):
    """List all tickets."""
    params = {}
    if args.limit:
        params["per_page"] = args.limit
    if args.campaign:
        params["campaign_code"] = args.campaign
    
    if args.all_pages:
        tickets = paginate_all("/tickets", params)
    else:
        result = http_get("/tickets", params)
        tickets = result.get("data", [])
    
    if args.format == "jsonl":
        output_jsonl(tickets)
    elif args.format == "csv":
        output_csv(tickets, ["id", "transaction_id", "campaign_code", "title", "first_name", "last_name", "email", "checked_in"])
    else:
        output_json(tickets)


def cmd_tickets_get(args):
    """Get a specific ticket."""
    result = http_get(f"/tickets/{args.id}")
    output_json(result.get("data", result))


# ─────────────────────────────────────────────────────────────────────────────
# Campaign Members Commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_members_list(args):
    """List all campaign members."""
    if not args.campaign:
        print("Error: --campaign is required for members list", file=sys.stderr)
        sys.exit(1)
    
    params = {}
    if args.limit:
        params["per_page"] = args.limit
    
    if args.all_pages:
        members = paginate_all(f"/campaigns/{args.campaign}/members", params)
    else:
        result = http_get(f"/campaigns/{args.campaign}/members", params)
        members = result.get("data", [])
    
    if args.format == "jsonl":
        output_jsonl(members)
    elif args.format == "csv":
        output_csv(members, ["id", "first_name", "last_name", "email", "total", "created_at"])
    else:
        output_json(members)


def cmd_members_get(args):
    """Get a specific campaign member."""
    if not args.campaign:
        print("Error: --campaign is required for members get", file=sys.stderr)
        sys.exit(1)
    
    result = http_get(f"/campaigns/{args.campaign}/members/{args.id}")
    output_json(result.get("data", result))


def cmd_members_delete(args):
    """Delete a campaign member."""
    if not args.campaign:
        print("Error: --campaign is required for members delete", file=sys.stderr)
        sys.exit(1)
    
    if args.dry_run:
        print(f"Dry run - would delete member {args.id} from campaign {args.campaign}")
        return
    
    http_delete(f"/campaigns/{args.campaign}/members/{args.id}")
    print(f"Deleted member: {args.id}")


# ─────────────────────────────────────────────────────────────────────────────
# Campaign Teams Commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_teams_list(args):
    """List all campaign teams."""
    if not args.campaign:
        print("Error: --campaign is required for teams list", file=sys.stderr)
        sys.exit(1)
    
    params = {}
    if args.limit:
        params["per_page"] = args.limit
    
    if args.all_pages:
        teams = paginate_all(f"/campaigns/{args.campaign}/teams", params)
    else:
        result = http_get(f"/campaigns/{args.campaign}/teams", params)
        teams = result.get("data", [])
    
    if args.format == "jsonl":
        output_jsonl(teams)
    elif args.format == "csv":
        output_csv(teams, ["id", "title", "total", "goal", "created_at"])
    else:
        output_json(teams)


def cmd_teams_get(args):
    """Get a specific campaign team."""
    if not args.campaign:
        print("Error: --campaign is required for teams get", file=sys.stderr)
        sys.exit(1)
    
    result = http_get(f"/campaigns/{args.campaign}/teams/{args.id}")
    output_json(result.get("data", result))


# ─────────────────────────────────────────────────────────────────────────────
# CLI Parser
# ─────────────────────────────────────────────────────────────────────────────

def build_parser():
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Givebutter CLI - Nonprofit fundraising platform API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--env", help="Path to environment file")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # ─── Campaigns ───
    camp_parser = subparsers.add_parser("campaigns", help="Manage campaigns")
    camp_sub = camp_parser.add_subparsers(dest="action", help="Action")
    
    # campaigns list
    camp_list = camp_sub.add_parser("list", help="List campaigns")
    camp_list.add_argument("--limit", type=int, help="Results per page")
    camp_list.add_argument("--all-pages", action="store_true", help="Fetch all pages")
    camp_list.add_argument("--format", choices=["json", "jsonl", "csv"], default="json")
    camp_list.set_defaults(func=cmd_campaigns_list)
    
    # campaigns get
    camp_get = camp_sub.add_parser("get", help="Get a campaign")
    camp_get.add_argument("id", help="Campaign ID or code")
    camp_get.set_defaults(func=cmd_campaigns_get)
    
    # campaigns create
    camp_create = camp_sub.add_parser("create", help="Create a campaign")
    camp_create.add_argument("--title", required=True, help="Campaign title")
    camp_create.add_argument("--type", choices=["standard", "event", "membership"], help="Campaign type")
    camp_create.add_argument("--goal", type=float, help="Fundraising goal")
    camp_create.add_argument("--description", help="Campaign description")
    camp_create.add_argument("--slug", help="URL slug")
    camp_create.add_argument("--dry-run", action="store_true", help="Preview without creating")
    camp_create.add_argument("--notify", action="store_true", help="Send notifications")
    camp_create.set_defaults(func=cmd_campaigns_create)
    
    # campaigns update
    camp_update = camp_sub.add_parser("update", help="Update a campaign")
    camp_update.add_argument("id", help="Campaign ID or code")
    camp_update.add_argument("--title", help="New title")
    camp_update.add_argument("--goal", type=float, help="New goal")
    camp_update.add_argument("--description", help="New description")
    camp_update.add_argument("--status", choices=["draft", "active", "closed"], help="Status")
    camp_update.add_argument("--dry-run", action="store_true", help="Preview without updating")
    camp_update.set_defaults(func=cmd_campaigns_update)
    
    # campaigns delete
    camp_delete = camp_sub.add_parser("delete", help="Delete a campaign")
    camp_delete.add_argument("id", help="Campaign ID or code")
    camp_delete.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    camp_delete.set_defaults(func=cmd_campaigns_delete)
    
    # ─── Contacts ───
    cont_parser = subparsers.add_parser("contacts", help="Manage contacts")
    cont_sub = cont_parser.add_subparsers(dest="action", help="Action")
    
    # contacts list
    cont_list = cont_sub.add_parser("list", help="List contacts")
    cont_list.add_argument("--limit", type=int, help="Results per page")
    cont_list.add_argument("--email", help="Filter by email")
    cont_list.add_argument("--all-pages", action="store_true", help="Fetch all pages")
    cont_list.add_argument("--format", choices=["json", "jsonl", "csv"], default="json")
    cont_list.set_defaults(func=cmd_contacts_list)
    
    # contacts get
    cont_get = cont_sub.add_parser("get", help="Get a contact")
    cont_get.add_argument("id", help="Contact ID")
    cont_get.set_defaults(func=cmd_contacts_get)
    
    # contacts create
    cont_create = cont_sub.add_parser("create", help="Create a contact")
    cont_create.add_argument("--email", required=True, help="Email address")
    cont_create.add_argument("--first-name", help="First name")
    cont_create.add_argument("--last-name", help="Last name")
    cont_create.add_argument("--phone", help="Phone number")
    cont_create.add_argument("--address", help="Street address")
    cont_create.add_argument("--city", help="City")
    cont_create.add_argument("--state", help="State")
    cont_create.add_argument("--zip", help="ZIP code")
    cont_create.add_argument("--country", help="Country code")
    cont_create.add_argument("--dry-run", action="store_true", help="Preview without creating")
    cont_create.set_defaults(func=cmd_contacts_create)
    
    # contacts update
    cont_update = cont_sub.add_parser("update", help="Update a contact")
    cont_update.add_argument("id", help="Contact ID")
    cont_update.add_argument("--email", help="New email")
    cont_update.add_argument("--first-name", help="New first name")
    cont_update.add_argument("--last-name", help="New last name")
    cont_update.add_argument("--phone", help="New phone")
    cont_update.add_argument("--address", help="New address")
    cont_update.add_argument("--city", help="New city")
    cont_update.add_argument("--state", help="New state")
    cont_update.add_argument("--zip", help="New ZIP")
    cont_update.add_argument("--country", help="New country")
    cont_update.add_argument("--dry-run", action="store_true", help="Preview without updating")
    cont_update.set_defaults(func=cmd_contacts_update)
    
    # contacts archive
    cont_archive = cont_sub.add_parser("archive", help="Archive a contact")
    cont_archive.add_argument("id", help="Contact ID")
    cont_archive.add_argument("--dry-run", action="store_true", help="Preview without archiving")
    cont_archive.set_defaults(func=cmd_contacts_archive)
    
    # contacts restore
    cont_restore = cont_sub.add_parser("restore", help="Restore an archived contact")
    cont_restore.add_argument("id", help="Contact ID")
    cont_restore.add_argument("--dry-run", action="store_true", help="Preview without restoring")
    cont_restore.set_defaults(func=cmd_contacts_restore)
    
    # ─── Transactions ───
    tx_parser = subparsers.add_parser("transactions", help="Manage transactions")
    tx_sub = tx_parser.add_subparsers(dest="action", help="Action")
    
    # transactions list
    tx_list = tx_sub.add_parser("list", help="List transactions")
    tx_list.add_argument("--limit", type=int, help="Results per page")
    tx_list.add_argument("--campaign", help="Filter by campaign code")
    tx_list.add_argument("--contact", help="Filter by contact ID")
    tx_list.add_argument("--status", choices=["succeeded", "pending", "failed"], help="Filter by status")
    tx_list.add_argument("--all-pages", action="store_true", help="Fetch all pages")
    tx_list.add_argument("--format", choices=["json", "jsonl", "csv"], default="json")
    tx_list.set_defaults(func=cmd_transactions_list)
    
    # transactions get
    tx_get = tx_sub.add_parser("get", help="Get a transaction")
    tx_get.add_argument("id", help="Transaction ID")
    tx_get.set_defaults(func=cmd_transactions_get)
    
    # transactions create (record-keeping only)
    tx_create = tx_sub.add_parser("create", help="Create a transaction (record-keeping only)")
    tx_create.add_argument("--campaign", help="Campaign code")
    tx_create.add_argument("--method", default="donor_advised_fund", 
                           choices=["cash", "check", "wire_transfer", "donor_advised_fund", 
                                    "stock", "cryptocurrency", "other"],
                           help="Payment method")
    tx_create.add_argument("--amount", type=float, help="Transaction amount")
    tx_create.add_argument("--first-name", help="Donor first name")
    tx_create.add_argument("--last-name", help="Donor last name")
    tx_create.add_argument("--email", help="Donor email")
    tx_create.add_argument("--phone", help="Donor phone")
    tx_create.add_argument("--address", help="Donor address")
    tx_create.add_argument("--city", help="Donor city")
    tx_create.add_argument("--state", help="Donor state")
    tx_create.add_argument("--zip", help="Donor ZIP")
    tx_create.add_argument("--country", help="Donor country")
    tx_create.add_argument("--fund", help="Fund ID")
    tx_create.add_argument("--captured-at", help="Transaction date (ISO 8601)")
    tx_create.add_argument("--dedication", help="Dedication/tribute")
    tx_create.add_argument("--note", help="Internal note")
    tx_create.add_argument("--anonymous", action="store_true", help="Anonymous donation")
    tx_create.add_argument("--dry-run", action="store_true", help="Preview without creating")
    tx_create.add_argument("--notify", action="store_true", help="Send notifications")
    tx_create.set_defaults(func=cmd_transactions_create)
    
    # transactions import (bulk)
    tx_import = tx_sub.add_parser("import", help="Bulk import transactions from JSONL")
    tx_import.add_argument("file", help="JSONL file path")
    tx_import.add_argument("--campaign", help="Default campaign code")
    tx_import.add_argument("--default-method", default="donor_advised_fund", help="Default payment method")
    tx_import.add_argument("--dry-run", action="store_true", help="Preview without importing")
    tx_import.set_defaults(func=cmd_transactions_import)
    
    # ─── Funds ───
    fund_parser = subparsers.add_parser("funds", help="Manage funds")
    fund_sub = fund_parser.add_subparsers(dest="action", help="Action")
    
    # funds list
    fund_list = fund_sub.add_parser("list", help="List funds")
    fund_list.add_argument("--limit", type=int, help="Results per page")
    fund_list.add_argument("--all-pages", action="store_true", help="Fetch all pages")
    fund_list.add_argument("--format", choices=["json", "jsonl", "csv"], default="json")
    fund_list.set_defaults(func=cmd_funds_list)
    
    # funds get
    fund_get = fund_sub.add_parser("get", help="Get a fund")
    fund_get.add_argument("id", help="Fund ID")
    fund_get.set_defaults(func=cmd_funds_get)
    
    # funds create
    fund_create = fund_sub.add_parser("create", help="Create a fund")
    fund_create.add_argument("--title", required=True, help="Fund title")
    fund_create.add_argument("--description", help="Fund description")
    fund_create.add_argument("--goal", type=float, help="Fund goal")
    fund_create.add_argument("--dry-run", action="store_true", help="Preview without creating")
    fund_create.set_defaults(func=cmd_funds_create)
    
    # funds update
    fund_update = fund_sub.add_parser("update", help="Update a fund")
    fund_update.add_argument("id", help="Fund ID")
    fund_update.add_argument("--title", help="New title")
    fund_update.add_argument("--description", help="New description")
    fund_update.add_argument("--goal", type=float, help="New goal")
    fund_update.add_argument("--dry-run", action="store_true", help="Preview without updating")
    fund_update.set_defaults(func=cmd_funds_update)
    
    # funds delete
    fund_delete = fund_sub.add_parser("delete", help="Delete a fund")
    fund_delete.add_argument("id", help="Fund ID")
    fund_delete.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    fund_delete.set_defaults(func=cmd_funds_delete)
    
    # ─── Plans (Recurring) ───
    plan_parser = subparsers.add_parser("plans", help="View recurring donation plans")
    plan_sub = plan_parser.add_subparsers(dest="action", help="Action")
    
    # plans list
    plan_list = plan_sub.add_parser("list", help="List recurring plans")
    plan_list.add_argument("--limit", type=int, help="Results per page")
    plan_list.add_argument("--status", choices=["active", "paused", "cancelled"], help="Filter by status")
    plan_list.add_argument("--all-pages", action="store_true", help="Fetch all pages")
    plan_list.add_argument("--format", choices=["json", "jsonl", "csv"], default="json")
    plan_list.set_defaults(func=cmd_plans_list)
    
    # plans get
    plan_get = plan_sub.add_parser("get", help="Get a recurring plan")
    plan_get.add_argument("id", help="Plan ID")
    plan_get.set_defaults(func=cmd_plans_get)
    
    # ─── Payouts ───
    payout_parser = subparsers.add_parser("payouts", help="View payouts")
    payout_sub = payout_parser.add_subparsers(dest="action", help="Action")
    
    # payouts list
    payout_list = payout_sub.add_parser("list", help="List payouts")
    payout_list.add_argument("--limit", type=int, help="Results per page")
    payout_list.add_argument("--all-pages", action="store_true", help="Fetch all pages")
    payout_list.add_argument("--format", choices=["json", "jsonl", "csv"], default="json")
    payout_list.set_defaults(func=cmd_payouts_list)
    
    # payouts get
    payout_get = payout_sub.add_parser("get", help="Get a payout")
    payout_get.add_argument("id", help="Payout ID")
    payout_get.set_defaults(func=cmd_payouts_get)
    
    # ─── Tickets ───
    ticket_parser = subparsers.add_parser("tickets", help="View event tickets")
    ticket_sub = ticket_parser.add_subparsers(dest="action", help="Action")
    
    # tickets list
    ticket_list = ticket_sub.add_parser("list", help="List tickets")
    ticket_list.add_argument("--limit", type=int, help="Results per page")
    ticket_list.add_argument("--campaign", help="Filter by campaign code")
    ticket_list.add_argument("--all-pages", action="store_true", help="Fetch all pages")
    ticket_list.add_argument("--format", choices=["json", "jsonl", "csv"], default="json")
    ticket_list.set_defaults(func=cmd_tickets_list)
    
    # tickets get
    ticket_get = ticket_sub.add_parser("get", help="Get a ticket")
    ticket_get.add_argument("id", help="Ticket ID")
    ticket_get.set_defaults(func=cmd_tickets_get)
    
    # ─── Members ───
    member_parser = subparsers.add_parser("members", help="Manage campaign members")
    member_sub = member_parser.add_subparsers(dest="action", help="Action")
    
    # members list
    member_list = member_sub.add_parser("list", help="List campaign members")
    member_list.add_argument("--campaign", required=True, help="Campaign ID or code")
    member_list.add_argument("--limit", type=int, help="Results per page")
    member_list.add_argument("--all-pages", action="store_true", help="Fetch all pages")
    member_list.add_argument("--format", choices=["json", "jsonl", "csv"], default="json")
    member_list.set_defaults(func=cmd_members_list)
    
    # members get
    member_get = member_sub.add_parser("get", help="Get a campaign member")
    member_get.add_argument("--campaign", required=True, help="Campaign ID or code")
    member_get.add_argument("id", help="Member ID")
    member_get.set_defaults(func=cmd_members_get)
    
    # members delete
    member_delete = member_sub.add_parser("delete", help="Delete a campaign member")
    member_delete.add_argument("--campaign", required=True, help="Campaign ID or code")
    member_delete.add_argument("id", help="Member ID")
    member_delete.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    member_delete.set_defaults(func=cmd_members_delete)
    
    # ─── Teams ───
    team_parser = subparsers.add_parser("teams", help="View campaign teams")
    team_sub = team_parser.add_subparsers(dest="action", help="Action")
    
    # teams list
    team_list = team_sub.add_parser("list", help="List campaign teams")
    team_list.add_argument("--campaign", required=True, help="Campaign ID or code")
    team_list.add_argument("--limit", type=int, help="Results per page")
    team_list.add_argument("--all-pages", action="store_true", help="Fetch all pages")
    team_list.add_argument("--format", choices=["json", "jsonl", "csv"], default="json")
    team_list.set_defaults(func=cmd_teams_list)
    
    # teams get
    team_get = team_sub.add_parser("get", help="Get a campaign team")
    team_get.add_argument("--campaign", required=True, help="Campaign ID or code")
    team_get.add_argument("id", help="Team ID")
    team_get.set_defaults(func=cmd_teams_get)
    
    return parser


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Main entry point."""
    load_agents_env()
    
    parser = build_parser()
    args = parser.parse_args()
    
    if args.env:
        os.environ["AGENTS_ENV_PATH"] = args.env
        load_agents_env()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if not hasattr(args, "func") or args.func is None:
        # Print subcommand help if no action specified
        parser.parse_args([args.command, "--help"])
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()

