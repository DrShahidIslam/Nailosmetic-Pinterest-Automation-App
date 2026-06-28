import os
import sys
import requests
import json
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
load_dotenv()

TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN", "").strip("'").strip('"')
BASE = "https://api.pinterest.com/v5"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# Read recent_pinterest_stats.json to get top pin IDs
try:
    with open("recent_pinterest_stats.json", "r", encoding="utf-8") as f:
        stats = json.load(f)
except Exception as e:
    print(f"Error loading stats file: {e}")
    sys.exit(1)

top_pins = stats.get("top_pins", {}).get("pins", [])
print(f"Loaded {len(top_pins)} top pins from stats.")

for pin_info in top_pins[:10]:
    pin_id = pin_info.get("pin_id")
    metrics = pin_info.get("metrics", {})
    print(f"\n======================================")
    print(f"Pin ID: {pin_id}")
    print(f"Metrics: Impressions={metrics.get('IMPRESSION')}, Outbound Clicks={metrics.get('OUTBOUND_CLICK')}, Saves={metrics.get('SAVE')}")
    
    # Query Pinterest API for Pin details
    url = f"{BASE}/pins/{pin_id}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 200:
        pin_details = r.json()
        print(f"Title: {pin_details.get('title')}")
        print(f"Link: {pin_details.get('link')}")
        print(f"Board ID: {pin_details.get('board_id')}")
        print(f"Board Section ID: {pin_details.get('board_section_id')}")
        print(f"Description: {pin_details.get('description')}")
        media = pin_details.get("media", {})
        if media:
            print(f"Media Images: {json.dumps(media.get('images', {}).get('736x', {}), indent=2)}")
    else:
        print(f"Error fetching details: {r.status_code} - {r.text}")
