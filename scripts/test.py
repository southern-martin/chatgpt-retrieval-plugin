
import json
import os
import urllib.request
import urllib.error
from collections import defaultdict

url = os.environ.get("PLUGIN_URL", "https://chatgpt-retrieval-plugin.epiphanydev.com")
query = os.environ.get("QUERY", "Second Life Project")
top_k = int(os.environ.get("TOP_K", "1000"))
token = os.environ.get("BEARER_TOKEN")
show_details = os.environ.get("SHOW_DETAILS", "1").lower() not in {"0", "false", "no"}
filter_json = os.environ.get("FILTER_JSON")

if not token:
    raise SystemExit("BEARER_TOKEN is not set in the environment")

query_obj = {"query": query, "top_k": top_k}
if filter_json:
    try:
        query_obj["filter"] = json.loads(filter_json)
    except json.JSONDecodeError as e:
        raise SystemExit(f"FILTER_JSON is not valid JSON: {e}")

payload = {"queries": [query_obj]}

req = urllib.request.Request(
    f"{url}/query",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    results = data["results"][0]["results"]
    unique = {r["metadata"]["source_id"] for r in results if r.get("metadata")}
    print("records returned:", len(results))
    print("unique conversations:", len(unique))

    grouped = defaultdict(list)
    for r in results:
        meta = r.get("metadata") or {}
        source_id = meta.get("source_id") or "unknown"
        grouped[source_id].append(r)

    def sort_key(item):
        meta = item.get("metadata") or {}
        created = meta.get("created_at")
        try:
            return float(created)
        except (TypeError, ValueError):
            return 0.0

    for source_id, items in grouped.items():
        print(f"conversation {source_id}: {len(items)} records")

    if show_details:
        for source_id, items in grouped.items():
            print(f"\nConversation {source_id} ({len(items)} messages)")
            for item in sorted(items, key=sort_key):
                meta = item.get("metadata") or {}
                author = meta.get("author") or "unknown"
                created = meta.get("created_at") or "unknown"
                score = item.get("score")
                text = item.get("text") or ""
                print(f"- [{created}] {author} (score={score})")
                print(text)
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode("utf-8", errors="replace"))
except Exception as e:
    print("ERROR:", e)
