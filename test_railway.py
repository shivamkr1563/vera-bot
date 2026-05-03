import requests

resp = requests.get(
    "https://vera-bot-production-d73c.up.railway.app/v1/healthz"
)
print(resp.json())

# Push one context and tick
resp2 = requests.post(
    "https://vera-bot-production-d73c.up.railway.app/v1/context",
    json={
        "scope": "merchant",
        "context_id": "test_001",
        "version": 99,
        "payload": {
            "merchant_id": "test_001",
            "category_slug": "dentists",
            "identity": {
                "owner_first_name": "Meera",
                "languages": ["hi", "en"]
            },
            "performance": {"ctr": 0.021}
        },
        "delivered_at": "2026-05-02T00:00:00Z"
    }
)
print("Context push:", resp2.json())


import json, requests
from pathlib import Path

BOT_URL = "https://vera-bot-production-d73c.up.railway.app"
DATASET_DIR = Path("dataset")

# Push category
cat = json.loads((DATASET_DIR / "categories" / "dentists.json").read_text())
requests.post(f"{BOT_URL}/v1/context", json={
    "scope": "category",
    "context_id": "dentists",
    "version": 99,
    "payload": cat,
    "delivered_at": "2026-05-03T00:00:00Z"
})

# Push merchant
merchants = json.loads((DATASET_DIR / "merchants_seed.json").read_text())["merchants"]
m = merchants[0]
requests.post(f"{BOT_URL}/v1/context", json={
    "scope": "merchant",
    "context_id": m["merchant_id"],
    "version": 99,
    "payload": m,
    "delivered_at": "2026-05-03T00:00:00Z"
})

# Push trigger
triggers = json.loads((DATASET_DIR / "triggers_seed.json").read_text())["triggers"]
t = triggers[0]
requests.post(f"{BOT_URL}/v1/context", json={
    "scope": "trigger",
    "context_id": t["id"],
    "version": 99,
    "payload": t,
    "delivered_at": "2026-05-03T00:00:00Z"
})

# Run tick
resp = requests.post(f"{BOT_URL}/v1/tick", json={
    "now": "2026-05-03T10:00:00Z",
    "available_triggers": [t["id"]]
})

actions = resp.json().get("actions", [])
print(f"\nMessages generated: {len(actions)}")
for a in actions:
    print(f"Body: {a.get('body')}")
    print(f"CTA: {a.get('cta')}")