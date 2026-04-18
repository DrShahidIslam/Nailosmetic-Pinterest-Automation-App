"""
Pinterest Trend Harvester v2
Fixed: API returns data under "trends" key, not "items".
Also fetches new board IDs for the expanded niche setup.
"""
import requests
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN", "")
BASE = "https://api.pinterest.com/v5"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def api_get(endpoint, params=None):
    url = f"{BASE}{endpoint}"
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    if r.status_code == 200:
        return r.json()
    else:
        print(f"  ERROR [{r.status_code}]: {r.text[:300]}")
        return None

# ---- 1. Fetch all boards (to get new board IDs) ----
print("=" * 60)
print("STEP 1: Fetching all Pinterest Boards")
print("=" * 60)
boards = api_get("/boards", {"page_size": 25})
if boards and "items" in boards:
    for b in boards["items"]:
        print(f"  Board: {b['name']:50s} | ID: {b['id']}")
else:
    print("  Could not fetch boards.")

# ---- 2. Harvest trends for each niche ----
print("\n" + "=" * 60)
print("STEP 2: Harvesting Pinterest Trends (Growing)")
print("=" * 60)

# We query the correct path: /trends/keywords/{region}/top/{trend_type}
NICHES = {
    "nails": {"interest": "beauty", "filter_keywords": ["nail", "mani", "pedicure", "french tip", "acrylic", "gel"]},
    "hair_beauty": {"interest": "beauty", "filter_keywords": ["hair", "hairstyle", "braid", "curl", "wig", "ponytail", "bob", "bangs", "updo", "locs", "blowout", "prom hair"]},
    "home_garden": {"interest": "home_decor", "filter_keywords": None},  # take all
    "fashion_style": {"interest": "womens_fashion", "filter_keywords": None},  # take all
}

# Also pull gardening trends
EXTRA = {"gardening": {"interest": "gardening", "filter_keywords": None}}

all_trends = {}

for niche_name, config in {**NICHES, **EXTRA}.items():
    print(f"\n--- {niche_name} (interest: {config['interest']}) ---")
    data = api_get(f"/trends/keywords/US/top/growing", {"interests": config["interest"]})
    
    if not data:
        print(f"  Failed to fetch trends for {niche_name}")
        continue
    
    # The API returns under "trends" key
    trends_list = data.get("trends", data.get("items", []))
    
    if not trends_list:
        print(f"  No trends found for {niche_name}")
        continue
    
    keywords = []
    for trend in trends_list:
        kw = trend.get("keyword", "")
        growth_mom = trend.get("pct_growth_mom", 0)
        growth_yoy = trend.get("pct_growth_yoy", 0)
        
        # If we have filter keywords, only keep trends that match
        if config["filter_keywords"]:
            if any(fk in kw.lower() for fk in config["filter_keywords"]):
                keywords.append({"keyword": kw, "growth_mom": growth_mom, "growth_yoy": growth_yoy})
        else:
            keywords.append({"keyword": kw, "growth_mom": growth_mom, "growth_yoy": growth_yoy})
    
    # Sort by monthly growth
    keywords.sort(key=lambda x: x["growth_mom"], reverse=True)
    
    all_trends[niche_name] = keywords
    print(f"  Found {len(keywords)} relevant trends:")
    for t in keywords[:10]:
        print(f"    {t['keyword']:40s} | MoM: +{t['growth_mom']}% | YoY: +{t['growth_yoy']}%")

# ---- 3. Save full trend data ----
with open("shared/niche_trends.json", "w", encoding="utf-8") as f:
    json.dump(all_trends, f, indent=4, ensure_ascii=False)

print(f"\n{'=' * 60}")
print(f"Saved {sum(len(v) for v in all_trends.values())} total trends to shared/niche_trends.json")
print(f"{'=' * 60}")

# ---- 4. Build the expanded topic_bank.json ----
print("\nSTEP 3: Building expanded topic_bank.json")

# Load existing topic bank
with open("shared/topic_bank.json", "r") as f:
    existing_topics = json.load(f)

# Build new niche-aware topic bank
topic_bank = {}

# Keep existing nail topics
topic_bank["nails"] = existing_topics  # preserve original list

# Add trend-sourced topics for each niche
for niche_name, trends in all_trends.items():
    if niche_name == "nails":
        # Merge trending nail keywords into existing
        for t in trends:
            if t["keyword"] not in topic_bank["nails"]:
                topic_bank["nails"].append(t["keyword"])
    else:
        topic_bank[niche_name] = [t["keyword"] for t in trends]

with open("shared/topic_bank_v2.json", "w", encoding="utf-8") as f:
    json.dump(topic_bank, f, indent=4, ensure_ascii=False)

print("Expanded topic bank saved to shared/topic_bank_v2.json")
for niche, topics in topic_bank.items():
    print(f"  {niche}: {len(topics)} topics")
