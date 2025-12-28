#BEARER_TOKEN="e44888863f6faa21d5ab9b1345dd3f306b3b2d51ce87f48d98464091c2b6c8d4"

import json, os, urllib.request, urllib.error

url = "https://chatgpt-retrieval-plugin.epiphanydev.com/query"
payload = {"queries": [{"query": "BPAS1 discussions summary", "top_k": 5}]}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {os.environ['BEARER_TOKEN']}",
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        print(resp.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode("utf-8", errors="replace"))
except Exception as e:
    print("ERROR:", e)
