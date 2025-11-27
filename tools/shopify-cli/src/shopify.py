#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

import requests
import csv
import unicodedata


def load_agents_env(path: Optional[str] = None) -> None:
    env_path = path or os.environ.get("AGENTS_ENV_PATH", os.path.expanduser("~/AGENTS.env"))
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('export '):
                line = line[len('export '):].lstrip()
            if '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip().strip('"').strip("'")
            v = v.strip().strip('"').strip("'")
            os.environ[k] = v


def get_cfg() -> Dict[str, str]:
    shop = os.environ.get('SHOPIFY_SHOP')
    token = os.environ.get('SHOPIFY_ADMIN_TOKEN') or os.environ.get('SHOPIFY_ACCESS_TOKEN')
    version = os.environ.get('SHOPIFY_API_VERSION', '2024-07')
    if not shop or not token:
        raise SystemExit('Set SHOPIFY_SHOP and SHOPIFY_ADMIN_TOKEN (or SHOPIFY_ACCESS_TOKEN) in ~/AGENTS.env')
    url = f"https://{shop}/admin/api/{version}/graphql.json"
    return {"shop": shop, "token": token, "version": version, "url": url}


def graphql(query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = get_cfg()
    headers = {
        'Content-Type': 'application/json',
        'X-Shopify-Access-Token': cfg['token'],
    }
    payload = {'query': query, 'variables': variables or {}}
    url = cfg['url']
    r = requests.post(url, headers=headers, json=payload, timeout=60, allow_redirects=False)
    # Handle Shopify 301/302 canonical redirect by re-POSTing to Location
    if r.status_code in (301, 302, 303, 307, 308):
        loc = r.headers.get('Location')
        if loc:
            url = loc
            r = requests.post(url, headers=headers, json=payload, timeout=60, allow_redirects=False)
    if r.status_code == 429:
        time.sleep(2)
        r = requests.post(url, headers=headers, json=payload, timeout=60, allow_redirects=False)
    if not r.ok:
        raise SystemExit(f"HTTP {r.status_code}: {r.text[:400]}")
    data = r.json()
    if 'errors' in data and data['errors']:
        raise SystemExit(json.dumps(data['errors'], indent=2))
    return data


def cmd_auth(args) -> int:
    load_agents_env(args.env)
    q = """
    query { shop { name myshopifyDomain } }
    """
    resp = graphql(q)
    print(json.dumps(resp.get('data', {}), indent=2))
    return 0


def cmd_query(args) -> int:
    load_agents_env(args.env)
    if not args.file and not args.query:
        raise SystemExit('--file or --query is required')
    q = args.query or open(os.path.expanduser(args.file), 'r', encoding='utf-8').read()
    vars_obj = {}
    if args.variables:
        vpath = os.path.expanduser(args.variables)
        if os.path.exists(vpath):
            vars_obj = json.load(open(vpath, 'r', encoding='utf-8'))
        else:
            vars_obj = json.loads(args.variables)
    resp = graphql(q, vars_obj)
    print(json.dumps(resp.get('data', {}), indent=2))
    return 0


def write_jsonl(items: List[Dict[str, Any]], out: Optional[str]) -> None:
    if out:
        outp = os.path.expanduser(out)
        os.makedirs(os.path.dirname(outp) or '.', exist_ok=True)
        with open(outp, 'w', encoding='utf-8') as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + '\n')
        print(json.dumps({'ok': True, 'count': len(items), 'out': outp}, indent=2))
    else:
        for it in items:
            sys.stdout.write(json.dumps(it, ensure_ascii=False) + '\n')


def write_csv(items: List[Dict[str, Any]], fields: List[str], out: str) -> None:
    outp = os.path.expanduser(out)
    os.makedirs(os.path.dirname(outp) or '.', exist_ok=True)
    with open(outp, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for it in items:
            row = {k: it.get(k) for k in fields}
            w.writerow(row)
    print(json.dumps({'ok': True, 'count': len(items), 'csv': outp}, indent=2))


def paginate_connection(conn: Dict[str, Any], node_key: str) -> List[Dict[str, Any]]:
    out = []
    edges = (conn or {}).get('edges', [])
    for e in edges:
        n = e.get('node') or {}
        out.append(n)
    return out


def slugify_handle(s: str) -> str:
    s_norm = unicodedata.normalize('NFKD', s)
    s_ascii = ''.join(c for c in s_norm if not unicodedata.combining(c))
    out = []
    prev_dash = False
    for ch in s_ascii.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        else:
            if not prev_dash:
                out.append('-')
                prev_dash = True
    handle = ''.join(out).strip('-')
    while '--' in handle:
        handle = handle.replace('--', '-')
    return handle


def normalize_name(s: str) -> str:
    s_norm = unicodedata.normalize('NFKD', s)
    s_ascii = ''.join(c for c in s_norm if not unicodedata.combining(c))
    return ' '.join(''.join(ch.lower() if ch.isalnum() else ' ' for ch in s_ascii).split())


def collect_distinct_vendors(page_size: int = 200) -> List[str]:
    items: List[str] = []
    seen = set()
    after = None
    while True:
        q = products_query(after, None, page_size)
        data = graphql(q).get('data', {})
        conn = data.get('products') or {}
        edges = (conn or {}).get('edges', [])
        for e in edges:
            node = e.get('node') or {}
            v = (node.get('vendor') or '').strip()
            if v and v.lower() not in ('unknown','misc','various','n/a','na','-','untagged'):
                if v not in seen:
                    seen.add(v)
                    items.append(v)
        if not conn.get('pageInfo', {}).get('hasNextPage'):
            break
        after = conn.get('pageInfo', {}).get('endCursor')
        if not after:
            break
    items.sort()
    return items


def fetch_all_collections(page_size: int = 200) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    after = None
    while True:
        q = collections_query(after, None, page_size)
        data = graphql(q).get('data', {})
        conn = data.get('collections') or {}
        out.extend(paginate_connection(conn, 'collections'))
        if not conn.get('pageInfo', {}).get('hasNextPage'):
            break
        after = conn.get('pageInfo', {}).get('endCursor')
        if not after:
            break
    return out


def build_vendor_ruleset(vendor: str) -> Dict[str, Any]:
    return {
        "appliedDisjunctively": False,
        "rules": [
            {"column": "VENDOR", "relation": "EQUALS", "condition": vendor}
        ],
    }


def cmd_vendors_list(args) -> int:
    load_agents_env(args.env)
    vendors = collect_distinct_vendors()
    if getattr(args, 'json', False):
        print(json.dumps({"count": len(vendors), "vendors": vendors}, indent=2))
    else:
        for v in vendors:
            print(v)
    return 0


def cmd_vendors_ensure_collections(args) -> int:
    load_agents_env(args.env)
    vendors = collect_distinct_vendors()
    # extend exclusions (normalized)
    exclude = set()
    if args.exclude:
        # support comma or newline separated
        raw = args.exclude.replace('\n', ',')
        for x in raw.split(','):
            x = x.strip()
            if x:
                exclude.add(normalize_name(x))
    vendors = [v for v in vendors if normalize_name(v) not in exclude]

    # renames mapping: support multiple --rename values formatted as "old=new"
    rename_map: Dict[str, str] = {}
    for spec in getattr(args, 'rename', []) or []:
        if '=' in spec:
            old, new = spec.split('=', 1)
            old = old.strip(); new = new.strip()
            if old and new:
                rename_map[normalize_name(old)] = new

    colls = fetch_all_collections()
    existing_handles = set((c.get('handle') or '').lower() for c in colls if c.get('handle'))
    plan: List[Dict[str, Any]] = []
    planned_by_handle: Dict[str, Dict[str, Any]] = {}
    for v in vendors:
        title = rename_map.get(normalize_name(v), v)
        handle = slugify_handle(title)
        if handle in existing_handles:
            continue
        rule = {"column": "VENDOR", "relation": "EQUALS", "condition": v}
        if handle in planned_by_handle:
            # Merge into existing plan item; use disjunctive rules (OR)
            item = planned_by_handle[handle]
            rs = item["ruleSet"]
            rs["appliedDisjunctively"] = True
            rs["rules"].append(rule)
        else:
            item = {
                "title": title,
                "handle": handle,
                "sortOrder": args.sort_order,
                "templateSuffix": args.template_suffix,
                "ruleSet": {"appliedDisjunctively": False, "rules": [rule]},
            }
            planned_by_handle[handle] = item
            plan.append(item)
    summary = {"vendors": len(vendors), "existing_collections": len(colls), "to_create": len(plan)}
    if not getattr(args, 'apply', False):
        if getattr(args, 'full', False):
            out = {"summary": summary, "plan": plan}
        else:
            out = {"summary": summary, "examples": plan[: min(5, len(plan))]}
        print(json.dumps(out, indent=2))
        return 0
    # Apply
    mutation = """
    mutation($input: CollectionInput!) {
      collectionCreate(input: $input) { collection { id handle title } userErrors { field message } }
    }
    """
    created = []
    for item in plan:
        variables = {"input": item}
        data = graphql(mutation, variables).get('data', {})
        payload = data.get('collectionCreate') or {}
        errs = payload.get('userErrors') or []
        if errs:
            print(json.dumps({"error": errs, "input": item}, indent=2))
        else:
            created.append(payload.get('collection'))
            print(json.dumps(payload.get('collection'), indent=2))
    print(json.dumps({"summary": summary, "created": len(created)}, indent=2))
    return 0
def resolve_blog_id_by_handle(handle: str) -> Optional[str]:
    q = f"""
    query {{
      blogs(first: 1, query: {json.dumps('handle:'+handle)}) {{ edges {{ node {{ id handle }} }} }}
    }}
    """
    data = graphql(q).get('data', {})
    edges = (((data.get('blogs') or {}).get('edges')) or [])
    return edges[0]['node']['id'] if edges else None


def resolve_collection_id_by_handle(handle: str) -> Optional[str]:
    q = f"""
    query {{
      collections(first: 1, query: {json.dumps('handle:'+handle)}) {{ edges {{ node {{ id handle }} }} }}
    }}
    """
    data = graphql(q).get('data', {})
    edges = (((data.get('collections') or {}).get('edges')) or [])
    return edges[0]['node']['id'] if edges else None


def resolve_article_id(blog_id: Optional[str], handle: Optional[str]) -> Optional[str]:
    if not handle:
        return None
    # Query globally by handle, then (optionally) filter by blog id
    q = f"""
    query {{
      articles(first: 50, query: {json.dumps('handle:'+handle)}) {{
        edges {{ node {{ id handle blog {{ id }} }} }}
      }}
    }}
    """
    data = graphql(q).get('data', {})
    edges = (((data.get('articles') or {}).get('edges')) or [])
    if not edges:
        return None
    if blog_id:
        for e in edges:
            n = e.get('node') or {}
            if (n.get('blog') or {}).get('id') == blog_id:
                return n.get('id')
        return None
    return edges[0].get('node', {}).get('id')


def products_query(after: Optional[str], query: Optional[str], page_size: int) -> str:
    after_part = f', after: "{after}"' if after else ''
    query_part = f', query: {json.dumps(query)}' if query else ''
    return f"""
    query {{
      products(first: {page_size}{after_part}{query_part}) {{
        edges {{
          cursor
          node {{
            id title handle vendor productType createdAt updatedAt
          }}
        }}
        pageInfo {{ hasNextPage endCursor }}
      }}
    }}
    """


def customers_query(after: Optional[str], query: Optional[str], page_size: int) -> str:
    after_part = f', after: "{after}"' if after else ''
    query_part = f', query: {json.dumps(query)}' if query else ''
    return f"""
    query {{
      customers(first: {page_size}{after_part}{query_part}) {{
        edges {{ cursor node {{ id displayName email tags state createdAt updatedAt }} }}
        pageInfo {{ hasNextPage endCursor }}
      }}
    }}
    """


def orders_query(after: Optional[str], query: Optional[str], page_size: int) -> str:
    after_part = f', after: "{after}"' if after else ''
    query_part = f', query: {json.dumps(query)}' if query else ''
    return f"""
    query {{
      orders(first: {page_size}{after_part}{query_part}) {{
        edges {{ cursor node {{ id name tags financialStatus fulfillmentStatus createdAt updatedAt }} }}
        pageInfo {{ hasNextPage endCursor }}
      }}
    }}
    """


def pages_query(after: Optional[str], query: Optional[str], page_size: int) -> str:
    after_part = f', after: "{after}"' if after else ''
    query_part = f', query: {json.dumps(query)}' if query else ''
    return f"""
    query {{
      pages(first: {page_size}{after_part}{query_part}) {{
        edges {{ cursor node {{ id title handle templateSuffix createdAt updatedAt }} }}
        pageInfo {{ hasNextPage endCursor }}
      }}
    }}
    """


def blogs_query(after: Optional[str], query: Optional[str], page_size: int) -> str:
    after_part = f', after: "{after}"' if after else ''
    query_part = f', query: {json.dumps(query)}' if query else ''
    return f"""
    query {{
      blogs(first: {page_size}{after_part}{query_part}) {{
        edges {{ cursor node {{ id title handle createdAt updatedAt }} }}
        pageInfo {{ hasNextPage endCursor }}
      }}
    }}
    """


def articles_query(after: Optional[str], query: Optional[str], page_size: int, blog_id: Optional[str]) -> str:
    after_part = f', after: "{after}"' if after else ''
    query_part = f', query: {json.dumps(query)}' if query else ''
    if blog_id:
        # Articles scoped to a blog
        return f"""
        query($id: ID!) {{
          blog(id: $id) {{
            id
            articles(first: {page_size}{after_part}{query_part}) {{
              edges {{ cursor node {{ id title handle author {{ name }} publishedAt updatedAt }} }}
              pageInfo {{ hasNextPage endCursor }}
            }}
          }}
        }}
        """
    else:
        # Global articles search
        return f"""
        query {{
          articles(first: {page_size}{after_part}{query_part}) {{
            edges {{ cursor node {{ id title handle author {{ name }} publishedAt updatedAt blog {{ id handle title }} }} }}
            pageInfo {{ hasNextPage endCursor }}
          }}
        }}
        """


def collections_query(after: Optional[str], query: Optional[str], page_size: int) -> str:
    after_part = f', after: "{after}"' if after else ''
    query_part = f', query: {json.dumps(query)}' if query else ''
    return f"""
    query {{
      collections(first: {page_size}{after_part}{query_part}) {{
        edges {{ cursor node {{ id title handle sortOrder templateSuffix updatedAt ruleSet {{ appliedDisjunctively }} }} }}
        pageInfo {{ hasNextPage endCursor }}
      }}
    }}
    """


def cmd_products_list(args) -> int:
    load_agents_env(args.env)
    items: List[Dict[str, Any]] = []
    after = None
    fetched = 0
    while True:
        q = products_query(after, args.query, int(args.page_size))
        data = graphql(q).get('data', {})
        conn = data.get('products') or {}
        nodes = paginate_connection(conn, 'products')
        items.extend(nodes)
        fetched += len(nodes)
        if (not conn.get('pageInfo', {}).get('hasNextPage')) or (not args.all and fetched >= int(args.limit)):
            break
        after = conn.get('pageInfo', {}).get('endCursor')
        if not after:
            break
    if args.csv:
        fields = [s.strip() for s in (args.fields or 'id,title,handle,vendor,productType,createdAt').split(',') if s.strip()]
        write_csv(items, fields, args.csv)
    else:
        write_jsonl(items, args.jsonl)
    return 0


def cmd_pages_list(args) -> int:
    load_agents_env(args.env)
    items: List[Dict[str, Any]] = []
    after = None
    fetched = 0
    while True:
        q = pages_query(after, args.query, int(args.page_size))
        data = graphql(q).get('data', {})
        conn = data.get('pages') or {}
        nodes = paginate_connection(conn, 'pages')
        items.extend(nodes)
        fetched += len(nodes)
        if (not conn.get('pageInfo', {}).get('hasNextPage')) or (not args.all and fetched >= int(args.limit)):
            break
        after = conn.get('pageInfo', {}).get('endCursor')
    if args.csv and args.fields:
        write_csv(items, [f.strip() for f in args.fields.split(',')], args.csv)
    else:
        write_jsonl(items, args.jsonl)
    return 0


def cmd_blogs_list(args) -> int:
    load_agents_env(args.env)
    items: List[Dict[str, Any]] = []
    after = None
    fetched = 0
    while True:
        q = blogs_query(after, args.query, int(args.page_size))
        data = graphql(q).get('data', {})
        conn = data.get('blogs') or {}
        nodes = paginate_connection(conn, 'blogs')
        items.extend(nodes)
        fetched += len(nodes)
        if (not conn.get('pageInfo', {}).get('hasNextPage')) or (not args.all and fetched >= int(args.limit)):
            break
        after = conn.get('pageInfo', {}).get('endCursor')
    if args.csv and args.fields:
        write_csv(items, [f.strip() for f in args.fields.split(',')], args.csv)
    else:
        write_jsonl(items, args.jsonl)
    return 0


def cmd_articles_list(args) -> int:
    load_agents_env(args.env)
    items: List[Dict[str, Any]] = []
    after = None
    fetched = 0
    blog_id = args.blog_id
    while True:
        q = articles_query(after, args.query, int(args.page_size), blog_id)
        variables = {"id": blog_id} if blog_id else None
        data = graphql(q, variables).get('data', {})
        if blog_id:
            conn = (data.get('blog') or {}).get('articles') or {}
        else:
            conn = data.get('articles') or {}
        nodes = paginate_connection(conn, 'articles')
        items.extend(nodes)
        fetched += len(nodes)
        if (not conn.get('pageInfo', {}).get('hasNextPage')) or (not args.all and fetched >= int(args.limit)):
            break
        after = conn.get('pageInfo', {}).get('endCursor')
    if args.csv and args.fields:
        write_csv(items, [f.strip() for f in args.fields.split(',')], args.csv)
    else:
        write_jsonl(items, args.jsonl)
    return 0


def cmd_collections_list(args) -> int:
    load_agents_env(args.env)
    items: List[Dict[str, Any]] = []
    after = None
    fetched = 0
    while True:
        q = collections_query(after, args.query, int(args.page_size))
        data = graphql(q).get('data', {})
        conn = data.get('collections') or {}
        nodes = paginate_connection(conn, 'collections')
        items.extend(nodes)
        fetched += len(nodes)
        if (not conn.get('pageInfo', {}).get('hasNextPage')) or (not args.all and fetched >= int(args.limit)):
            break
        after = conn.get('pageInfo', {}).get('endCursor')
    if args.csv and args.fields:
        write_csv(items, [f.strip() for f in args.fields.split(',')], args.csv)
    else:
        write_jsonl(items, args.jsonl)
    return 0


def cmd_customers_list(args) -> int:
    load_agents_env(args.env)
    items: List[Dict[str, Any]] = []
    after = None
    fetched = 0
    while True:
        q = customers_query(after, args.query, int(args.page_size))
        data = graphql(q).get('data', {})
        conn = data.get('customers') or {}
        nodes = paginate_connection(conn, 'customers')
        items.extend(nodes)
        fetched += len(nodes)
        if (not conn.get('pageInfo', {}).get('hasNextPage')) or (not args.all and fetched >= int(args.limit)):
            break
        after = conn.get('pageInfo', {}).get('endCursor')
        if not after:
            break
    if args.csv:
        fields = [s.strip() for s in (args.fields or 'id,displayName,email,tags,state,createdAt').split(',') if s.strip()]
        write_csv(items, fields, args.csv)
    else:
        write_jsonl(items, args.jsonl)
    return 0


def cmd_orders_list(args) -> int:
    load_agents_env(args.env)
    items: List[Dict[str, Any]] = []
    after = None
    fetched = 0
    while True:
        q = orders_query(after, args.query, int(args.page_size))
        data = graphql(q).get('data', {})
        conn = data.get('orders') or {}
        nodes = paginate_connection(conn, 'orders')
        items.extend(nodes)
        fetched += len(nodes)
        if (not conn.get('pageInfo', {}).get('hasNextPage')) or (not args.all and fetched >= int(args.limit)):
            break
        after = conn.get('pageInfo', {}).get('endCursor')
        if not after:
            break
    if args.csv:
        fields = [s.strip() for s in (args.fields or 'id,name,tags,financialStatus,fulfillmentStatus,createdAt').split(',') if s.strip()]
        write_csv(items, fields, args.csv)
    else:
        write_jsonl(items, args.jsonl)
    return 0


def cmd_metafield_get(args) -> int:
    load_agents_env(args.env)
    q = """
    query($ownerId: ID!, $ns: String!, $key: String!) {
      metafield(ownerId: $ownerId, namespace: $ns, key: $key) { id namespace key type value }
    }
    """
    data = graphql(q, {"ownerId": args.owner_id, "ns": args.ns, "key": args.key}).get('data', {})
    print(json.dumps(data, indent=2))
    return 0


def cmd_metafield_set(args) -> int:
    load_agents_env(args.env)
    mutation = """
    mutation($mf: [MetafieldsSetInput!]!) {
      metafieldsSet(metafields: $mf) {
        metafields { id namespace key type value }
        userErrors { field message }
      }
    }
    """
    mf = [{
        "ownerId": args.owner_id,
        "namespace": args.ns,
        "key": args.key,
        "type": args.type,
        "value": args.value,
    }]
    if args.dry_run:
        print(json.dumps({"dry_run": True, "mutation": mutation, "variables": {"mf": mf}}, indent=2))
        return 0
    data = graphql(mutation, {"mf": mf}).get('data', {})
    print(json.dumps(data, indent=2))
    return 0


def cmd_orders_fos(args) -> int:
    load_agents_env(args.env)
    if not args.order_id and not args.order_name:
        raise SystemExit('--order-id or --order-name is required')
    if args.order_name:
        # find by name
        q = f"""
        query {{
          orders(first: 1, query: {json.dumps('name:'+args.order_name)}) {{
            edges {{ node {{ id name fulfillmentOrders(first: 50) {{ edges {{ node {{ id status requestStatus }} }} }} }} }}
          }}
        }}
        """
        data = graphql(q).get('data', {})
        edges = (((data.get('orders') or {}).get('edges')) or [])
        if not edges:
            print(json.dumps({'orders': []}, indent=2))
            return 0
        order = edges[0]['node']
    else:
        q = """
        query($id: ID!) {
          order(id: $id) { id name fulfillmentOrders(first: 50) { edges { node { id status requestStatus } } } }
        }
        """
        data = graphql(q, {"id": args.order_id}).get('data', {})
        order = data.get('order') or {}
    fos = [e['node'] for e in (((order.get('fulfillmentOrders') or {}).get('edges')) or [])]
    print(json.dumps({'order': {'id': order.get('id'), 'name': order.get('name')}, 'fulfillmentOrders': fos}, indent=2))
    return 0


def cmd_orders_set_deadline(args) -> int:
    load_agents_env(args.env)
    if not args.fo_id and not args.order_id and not args.order_name:
        raise SystemExit('--fo-id or (--order-id|--order-name) is required')
    fo_ids: List[str] = []
    if args.fo_id:
        fo_ids = [args.fo_id]
    else:
        # fetch FOs from order
        holder = argparse.Namespace(order_id=args.order_id, order_name=args.order_name)
        # reuse logic
        if args.order_name:
            q = f"""
            query {{
              orders(first: 1, query: {json.dumps('name:'+args.order_name)}) {{
                edges {{ node {{ id name fulfillmentOrders(first: 50) {{ edges {{ node {{ id }} }} }} }} }}
              }}
            }}
            """
            data = graphql(q).get('data', {})
            edges = (((data.get('orders') or {}).get('edges')) or [])
            if not edges:
                raise SystemExit('Order not found by name')
            order = edges[0]['node']
        else:
            q = """
            query($id: ID!) { order(id: $id) { id fulfillmentOrders(first: 50) { edges { node { id } } } } }
            """
            data = graphql(q, {"id": args.order_id}).get('data', {})
            order = data.get('order') or {}
        fo_ids = [e['node']['id'] for e in (((order.get('fulfillmentOrders') or {}).get('edges')) or [])]
        if not fo_ids:
            raise SystemExit('No fulfillment orders found for order')
        if not args.all:
            fo_ids = fo_ids[:1]
    mutation = """
    mutation($ids: [ID!]!, $deadline: DateTime!) {
      fulfillmentOrdersSetFulfillmentDeadline(fulfillmentOrderIds: $ids, fulfillmentDeadline: $deadline) {
        userErrors { field message }
      }
    }
    """
    vars_obj = {"ids": fo_ids, "deadline": args.deadline}
    if args.dry_run:
        print(json.dumps({"dry_run": True, "mutation": mutation, "variables": vars_obj}, indent=2))
        return 0
    data = graphql(mutation, vars_obj).get('data', {})
    print(json.dumps(data, indent=2))
    return 0


def cmd_articles_create(args) -> int:
    load_agents_env(args.env)
    # Build ArticleCreateInput
    article: Dict[str, Any] = {"title": args.title}
    if args.blog_id:
        article["blogId"] = args.blog_id
    elif args.blog_handle:
        bid = resolve_blog_id_by_handle(args.blog_handle)
        if not bid:
            raise SystemExit("Blog not found by handle")
        article["blogId"] = bid
    if args.handle:
        article["handle"] = args.handle
    if args.body or args.body_file:
        body = args.body or open(os.path.expanduser(args.body_file), 'r', encoding='utf-8').read()
        article["body"] = body
    if args.summary or args.summary_file:
        summary = args.summary or open(os.path.expanduser(args.summary_file), 'r', encoding='utf-8').read()
        article["summary"] = summary
    if args.tags:
        article["tags"] = [t.strip() for t in args.tags.split(',') if t.strip()]
    if args.is_published is not None:
        article["isPublished"] = bool(args.is_published)
    if args.publish_date:
        article["publishDate"] = args.publish_date
    if args.template_suffix is not None:
        article["templateSuffix"] = args.template_suffix

    mutation = """
    mutation($article: ArticleCreateInput!) {
      articleCreate(article: $article) {
        article { id handle title blog { id handle } }
        userErrors { field message }
      }
    }
    """
    variables = {"article": article}
    if args.dry_run:
        print(json.dumps({"dry_run": True, "mutation": mutation, "variables": variables}, indent=2))
        return 0
    data = graphql(mutation, variables).get('data', {})
    print(json.dumps(data, indent=2))
    return 0


def cmd_articles_update(args) -> int:
    load_agents_env(args.env)
    aid = args.id
    if not aid:
        aid = resolve_article_id(args.blog_id or (resolve_blog_id_by_handle(args.blog_handle) if args.blog_handle else None), args.handle)
        if not aid:
            raise SystemExit('Article id required or resolvable via --handle [--blog-id|--blog-handle]')
    article: Dict[str, Any] = {}
    if args.title is not None:
        article["title"] = args.title
    if args.handle is not None and args.update_handle:
        article["handle"] = args.handle
    if args.body or args.body_file:
        body = args.body or open(os.path.expanduser(args.body_file), 'r', encoding='utf-8').read()
        article["body"] = body
    if args.summary or args.summary_file:
        summary = args.summary or open(os.path.expanduser(args.summary_file), 'r', encoding='utf-8').read()
        article["summary"] = summary
    if args.tags is not None:
        article["tags"] = [t.strip() for t in args.tags.split(',')] if args.tags else []
    if args.is_published is not None:
        article["isPublished"] = bool(args.is_published)
    if args.publish_date:
        article["publishDate"] = args.publish_date
    if args.template_suffix is not None:
        article["templateSuffix"] = args.template_suffix

    mutation = """
    mutation($id: ID!, $article: ArticleUpdateInput!) {
      articleUpdate(id: $id, article: $article) {
        article { id handle title blog { id handle } }
        userErrors { field message }
      }
    }
    """
    variables = {"id": aid, "article": article}
    if args.dry_run:
        print(json.dumps({"dry_run": True, "mutation": mutation, "variables": variables}, indent=2))
        return 0
    data = graphql(mutation, variables).get('data', {})
    print(json.dumps(data, indent=2))
    return 0


def cmd_blogs_create(args) -> int:
    load_agents_env(args.env)
    blog: Dict[str, Any] = {"title": args.title}
    if args.handle:
        blog["handle"] = args.handle
    if args.template_suffix is not None:
        blog["templateSuffix"] = args.template_suffix
    if args.comment_policy is not None:
        blog["commentPolicy"] = args.comment_policy
    mutation = """
    mutation($blog: BlogCreateInput!) {
      blogCreate(blog: $blog) {
        blog { id handle title }
        userErrors { field message }
      }
    }
    """
    variables = {"blog": blog}
    if args.dry_run:
        print(json.dumps({"dry_run": True, "mutation": mutation, "variables": variables}, indent=2))
        return 0
    data = graphql(mutation, variables).get('data', {})
    print(json.dumps(data, indent=2))
    return 0


def cmd_blogs_update(args) -> int:
    load_agents_env(args.env)
    bid = args.id
    if not bid and args.handle:
        bid = resolve_blog_id_by_handle(args.handle)
    if not bid:
        raise SystemExit('Blog id is required (or resolvable via --handle)')
    blog: Dict[str, Any] = {}
    if args.title is not None:
        blog["title"] = args.title
    if args.new_handle is not None:
        blog["handle"] = args.new_handle
    if args.template_suffix is not None:
        blog["templateSuffix"] = args.template_suffix
    if args.comment_policy is not None:
        blog["commentPolicy"] = args.comment_policy
    if args.redirect_new_handle is not None:
        blog["redirectNewHandle"] = bool(args.redirect_new_handle)
    mutation = """
    mutation($id: ID!, $blog: BlogUpdateInput!) {
      blogUpdate(id: $id, blog: $blog) {
        blog { id handle title }
        userErrors { field message }
      }
    }
    """
    variables = {"id": bid, "blog": blog}
    if args.dry_run:
        print(json.dumps({"dry_run": True, "mutation": mutation, "variables": variables}, indent=2))
        return 0
    data = graphql(mutation, variables).get('data', {})
    print(json.dumps(data, indent=2))
    return 0


def cmd_collections_create(args) -> int:
    load_agents_env(args.env)
    input_obj: Dict[str, Any] = {"title": args.title}
    if args.handle:
        input_obj["handle"] = args.handle
    if args.description_html is not None:
        input_obj["descriptionHtml"] = args.description_html
    if args.template_suffix is not None:
        input_obj["templateSuffix"] = args.template_suffix
    if args.sort_order is not None:
        input_obj["sortOrder"] = args.sort_order
    if args.products:
        ids = [s.strip() for s in args.products.split(',') if s.strip()]
        input_obj["products"] = ids
    if args.rule_set_json:
        # Accept inline JSON or file path
        val = args.rule_set_json
        p = os.path.expanduser(val)
        if os.path.exists(p):
            input_obj["ruleSet"] = json.load(open(p, 'r', encoding='utf-8'))
        else:
            input_obj["ruleSet"] = json.loads(val)
    mutation = """
    mutation($input: CollectionInput!) {
      collectionCreate(input: $input) {
        collection { id handle title }
        userErrors { field message }
      }
    }
    """
    variables = {"input": input_obj}
    if args.dry_run:
        print(json.dumps({"dry_run": True, "mutation": mutation, "variables": variables}, indent=2))
        return 0
    data = graphql(mutation, variables).get('data', {})
    print(json.dumps(data, indent=2))
    return 0


def cmd_collections_update(args) -> int:
    load_agents_env(args.env)
    cid = args.id
    if not cid and args.handle:
        cid = resolve_collection_id_by_handle(args.handle)
    if not cid:
        raise SystemExit('Collection id required (or resolvable via --handle)')
    input_obj: Dict[str, Any] = {"id": cid}
    if args.new_title is not None:
        input_obj["title"] = args.new_title
    if args.new_handle is not None:
        input_obj["handle"] = args.new_handle
    if args.description_html is not None:
        input_obj["descriptionHtml"] = args.description_html
    if args.template_suffix is not None:
        input_obj["templateSuffix"] = args.template_suffix
    if args.sort_order is not None:
        input_obj["sortOrder"] = args.sort_order
    if args.products is not None:
        ids = [s.strip() for s in args.products.split(',')] if args.products else []
        input_obj["products"] = ids
    # Image support via public URL
    if getattr(args, 'image_src', None):
        img = {"src": args.image_src}
        if getattr(args, 'image_alt', None):
            img["altText"] = args.image_alt
        input_obj["image"] = img
    if args.rule_set_json:
        p = os.path.expanduser(args.rule_set_json)
        if os.path.exists(p):
            input_obj["ruleSet"] = json.load(open(p, 'r', encoding='utf-8'))
        else:
            input_obj["ruleSet"] = json.loads(args.rule_set_json)
    if args.redirect_new_handle is not None:
        input_obj["redirectNewHandle"] = bool(args.redirect_new_handle)
    mutation = """
    mutation($input: CollectionInput!) {
      collectionUpdate(input: $input) {
        collection { id handle title }
        userErrors { field message }
      }
    }
    """
    variables = {"input": input_obj}
    if args.dry_run:
        print(json.dumps({"dry_run": True, "mutation": mutation, "variables": variables}, indent=2))
        return 0
    data = graphql(mutation, variables).get('data', {})
    print(json.dumps(data, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Shopify Admin GraphQL Ops')
    p.add_argument('--env', help='Path to AGENTS.env (default ~/AGENTS.env)')
    sp = p.add_subparsers(dest='cmd', required=True)

    pa = sp.add_parser('auth', help='Auth check: shop { name, myshopifyDomain }')
    pa.set_defaults(func=cmd_auth)

    pq = sp.add_parser('query', help='Run an arbitrary GraphQL query/mutation')
    pq.add_argument('--file', help='Path to .graphql file')
    pq.add_argument('--query', help='Inline query string')
    pq.add_argument('--variables', help='JSON string or path to JSON file')
    pq.set_defaults(func=cmd_query)

    pprod = sp.add_parser('products', help='Product operations')
    spr = pprod.add_subparsers(dest='prod_cmd', required=True)
    ppl = spr.add_parser('list', help='List/search products')
    ppl.add_argument('--query', help='Search query (Shopify search syntax)')
    ppl.add_argument('--page-size', default='100')
    ppl.add_argument('--limit', default='100')
    ppl.add_argument('--all', action='store_true')
    ppl.add_argument('--jsonl', help='Write JSONL to path (default stdout)')
    ppl.add_argument('--csv', help='Write CSV to path')
    ppl.add_argument('--fields', help='CSV fields (comma-separated)')
    ppl.set_defaults(func=cmd_products_list)

    pcus = sp.add_parser('customers', help='Customer operations')
    sc = pcus.add_subparsers(dest='cus_cmd', required=True)
    pcl = sc.add_parser('list', help='List/search customers')
    pcl.add_argument('--query', help='Search query')
    pcl.add_argument('--page-size', default='100')
    pcl.add_argument('--limit', default='100')
    pcl.add_argument('--all', action='store_true')
    pcl.add_argument('--jsonl', help='Write JSONL to path (default stdout)')
    pcl.add_argument('--csv', help='Write CSV to path')
    pcl.add_argument('--fields', help='CSV fields (comma-separated)')
    pcl.set_defaults(func=cmd_customers_list)

    pord = sp.add_parser('orders', help='Order operations')
    so = pord.add_subparsers(dest='ord_cmd', required=True)
    pol = so.add_parser('list', help='List/search orders')
    pol.add_argument('--query', help='Search query')
    pol.add_argument('--page-size', default='100')
    pol.add_argument('--limit', default='100')
    pol.add_argument('--all', action='store_true')
    pol.add_argument('--jsonl', help='Write JSONL to path (default stdout)')
    pol.add_argument('--csv', help='Write CSV to path')
    pol.add_argument('--fields', help='CSV fields (comma-separated)')
    pol.set_defaults(func=cmd_orders_list)

    pfo = so.add_parser('fulfillment-orders', help='List fulfillment orders for an order')
    pfo.add_argument('--order-id', help='Order GID')
    pfo.add_argument('--order-name', help='Order name, e.g., #1001')
    pfo.set_defaults(func=cmd_orders_fos)

    psd = so.add_parser('set-fulfillment-deadline', help='Set fulfillment deadline for one/more fulfillment orders')
    psd.add_argument('--fo-id', help='FulfillmentOrder GID')
    psd.add_argument('--order-id', help='Order GID (sets all FOs unless --all omitted)')
    psd.add_argument('--order-name', help='Order name (sets FOs unless --all omitted)')
    psd.add_argument('--all', action='store_true', help='When using order-id/name, apply to all fulfillment orders')
    psd.add_argument('--deadline', required=True, help='ISO8601 DateTime (e.g., 2025-09-03T17:00:00Z)')
    psd.add_argument('--dry-run', action='store_true')
    psd.set_defaults(func=cmd_orders_set_deadline)

    pmf = sp.add_parser('metafield', help='Metafield operations')
    smf = pmf.add_subparsers(dest='mf_cmd', required=True)
    pmfg = smf.add_parser('get', help='Get a metafield by ownerId/ns/key')
    pmfg.add_argument('--owner-id', required=True)
    pmfg.add_argument('--ns', required=True)
    pmfg.add_argument('--key', required=True)
    pmfg.set_defaults(func=cmd_metafield_get)
    pmfs = smf.add_parser('set', help='Set/update a metafield (dry-run aware)')
    pmfs.add_argument('--owner-id', required=True)
    pmfs.add_argument('--ns', required=True)
    pmfs.add_argument('--key', required=True)
    pmfs.add_argument('--type', required=True, help='Shopify metafield type (e.g., single_line_text_field)')
    pmfs.add_argument('--value', required=True)
    pmfs.add_argument('--dry-run', action='store_true')
    pmfs.set_defaults(func=cmd_metafield_set)

    # Pages
    ppage = sp.add_parser('pages', help='Online Store pages operations')
    spp = ppage.add_subparsers(dest='page_cmd', required=True)
    ppl = spp.add_parser('list', help='List/search pages')
    ppl.add_argument('--query', help='Search query')
    ppl.add_argument('--page-size', default='100')
    ppl.add_argument('--limit', default='100')
    ppl.add_argument('--all', action='store_true')
    ppl.add_argument('--jsonl', help='Write JSONL to path (default stdout)')
    ppl.add_argument('--csv', help='Write CSV to path')
    ppl.add_argument('--fields', help='CSV fields (comma-separated)')
    ppl.set_defaults(func=cmd_pages_list)

    # Blogs and Articles
    pblog = sp.add_parser('blogs', help='Blog operations')
    sbl = pblog.add_subparsers(dest='blog_cmd', required=True)
    bll = sbl.add_parser('list', help='List/search blogs')
    bll.add_argument('--query', help='Search query')
    bll.add_argument('--page-size', default='100')
    bll.add_argument('--limit', default='100')
    bll.add_argument('--all', action='store_true')
    bll.add_argument('--jsonl', help='Write JSONL to path (default stdout)')
    bll.add_argument('--csv', help='Write CSV to path')
    bll.add_argument('--fields', help='CSV fields (comma-separated)')
    bll.set_defaults(func=cmd_blogs_list)

    part = sp.add_parser('articles', help='Article operations')
    sar = part.add_subparsers(dest='art_cmd', required=True)
    arl = sar.add_parser('list', help='List/search articles (optionally scoped to a blog)')
    arl.add_argument('--query', help='Search query')
    arl.add_argument('--blog-id', help='Scope to a specific Blog GID')
    arl.add_argument('--page-size', default='100')
    arl.add_argument('--limit', default='100')
    arl.add_argument('--all', action='store_true')
    arl.add_argument('--jsonl', help='Write JSONL to path (default stdout)')
    arl.add_argument('--csv', help='Write CSV to path')
    arl.add_argument('--fields', help='CSV fields (comma-separated)')
    arl.set_defaults(func=cmd_articles_list)

    # Collections
    pcol = sp.add_parser('collections', help='Collection operations')
    scoll = pcol.add_subparsers(dest='col_cmd', required=True)
    cl = scoll.add_parser('list', help='List/search collections')
    cl.add_argument('--query', help='Search query')
    cl.add_argument('--page-size', default='100')
    cl.add_argument('--limit', default='100')
    cl.add_argument('--all', action='store_true')
    cl.add_argument('--jsonl', help='Write JSONL to path (default stdout)')
    cl.add_argument('--csv', help='Write CSV to path')
    cl.add_argument('--fields', help='CSV fields (comma-separated)')
    cl.set_defaults(func=cmd_collections_list)

    # Blogs create/update
    blc = sbl.add_parser('create', help='Create a blog')
    blc.add_argument('--title', required=True)
    blc.add_argument('--handle')
    blc.add_argument('--template-suffix')
    blc.add_argument('--comment-policy', choices=['NO_COMMENTS', 'MODERATE_COMMENTS', 'ALLOW_COMMENTS'])
    blc.add_argument('--dry-run', action='store_true')
    blc.set_defaults(func=cmd_blogs_create)

    blu = sbl.add_parser('update', help='Update a blog')
    blu.add_argument('--id')
    blu.add_argument('--handle', help='Existing handle to resolve id')
    blu.add_argument('--title')
    blu.add_argument('--new-handle')
    blu.add_argument('--template-suffix')
    blu.add_argument('--comment-policy', choices=['NO_COMMENTS', 'MODERATE_COMMENTS', 'ALLOW_COMMENTS'])
    blu.add_argument('--redirect-new-handle', type=int, choices=[0,1])
    blu.add_argument('--dry-run', action='store_true')
    blu.set_defaults(func=cmd_blogs_update)

    # Articles create/update
    arc = sar.add_parser('create', help='Create an article')
    arc.add_argument('--title', required=True)
    arc.add_argument('--blog-id')
    arc.add_argument('--blog-handle')
    arc.add_argument('--handle')
    arc.add_argument('--body')
    arc.add_argument('--body-file')
    arc.add_argument('--summary')
    arc.add_argument('--summary-file')
    arc.add_argument('--tags')
    arc.add_argument('--is-published', type=int, choices=[0,1])
    arc.add_argument('--publish-date', help='ISO8601 DateTime')
    arc.add_argument('--template-suffix')
    arc.add_argument('--dry-run', action='store_true')
    arc.set_defaults(func=cmd_articles_create)

    aru = sar.add_parser('update', help='Update an article')
    aru.add_argument('--id')
    aru.add_argument('--blog-id')
    aru.add_argument('--blog-handle')
    aru.add_argument('--handle', help='Article handle to resolve id (use with blog for precision)')
    aru.add_argument('--title')
    aru.add_argument('--update-handle', action='store_true', help='Allow updating handle when --handle is supplied')
    aru.add_argument('--body')
    aru.add_argument('--body-file')
    aru.add_argument('--summary')
    aru.add_argument('--summary-file')
    aru.add_argument('--tags')
    aru.add_argument('--is-published', type=int, choices=[0,1])
    aru.add_argument('--publish-date', help='ISO8601 DateTime')
    aru.add_argument('--template-suffix')
    aru.add_argument('--dry-run', action='store_true')
    aru.set_defaults(func=cmd_articles_update)

    # Collections create/update
    cc = scoll.add_parser('create', help='Create a collection')
    cc.add_argument('--title', required=True)
    cc.add_argument('--handle')
    cc.add_argument('--description-html')
    cc.add_argument('--template-suffix')
    cc.add_argument('--sort-order', choices=['MANUAL','BEST_SELLING','ALPHA_ASC','ALPHA_DESC','PRICE_ASC','PRICE_DESC','CREATED_ASC','CREATED_DESC'])
    cc.add_argument('--products', help='Comma-separated product GIDs to include')
    cc.add_argument('--rule-set-json', help='Inline JSON or file path for CollectionRuleSetInput')
    cc.add_argument('--dry-run', action='store_true')
    cc.set_defaults(func=cmd_collections_create)

    cu = scoll.add_parser('update', help='Update a collection')
    cu.add_argument('--id')
    cu.add_argument('--handle', help='Existing handle to resolve id')
    cu.add_argument('--new-title')
    cu.add_argument('--new-handle')
    cu.add_argument('--description-html')
    cu.add_argument('--template-suffix')
    cu.add_argument('--sort-order', choices=['MANUAL','BEST_SELLING','ALPHA_ASC','ALPHA_DESC','PRICE_ASC','PRICE_DESC','CREATED_ASC','CREATED_DESC'])
    cu.add_argument('--products', help='Comma-separated product GIDs to set (overwrites order)')
    cu.add_argument('--rule-set-json', help='Inline JSON or file path for CollectionRuleSetInput')
    cu.add_argument('--redirect-new-handle', type=int, choices=[0,1])
    cu.add_argument('--image-src', help='Public image URL for collection.image.src')
    cu.add_argument('--image-alt', help='Alt text for collection image')
    cu.add_argument('--dry-run', action='store_true')
    cu.set_defaults(func=cmd_collections_update)

    # Vendors tooling
    pven = sp.add_parser('vendors', help='Vendor utilities')
    sv = pven.add_subparsers(dest='ven_cmd', required=True)
    vlist = sv.add_parser('list', help='List distinct product vendors')
    vlist.add_argument('--json', action='store_true')
    vlist.set_defaults(func=cmd_vendors_list)
    venc = sv.add_parser('ensure-collections', help='Ensure a collection exists for each vendor (smart collection: vendor == name)')
    venc.add_argument('--exclude', help='Comma-separated vendor names to exclude (case-insensitive)')
    venc.add_argument('--sort-order', default='BEST_SELLING', choices=['MANUAL','BEST_SELLING','ALPHA_ASC','ALPHA_DESC','PRICE_ASC','PRICE_DESC','CREATED_ASC','CREATED_DESC'])
    venc.add_argument('--template-suffix', default='')
    venc.add_argument('--rename', action='append', help='Rename mapping old=new (repeatable)')
    venc.add_argument('--apply', action='store_true', help='Apply changes (otherwise prints dry-run)')
    venc.add_argument('--full', action='store_true', help='Include full plan in dry-run output')
    venc.set_defaults(func=cmd_vendors_ensure_collections)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except SystemExit as e:
        raise e
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
