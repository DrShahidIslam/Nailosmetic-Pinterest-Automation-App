"""
Pinterest Account & Trends Analyzer v2
Corrected endpoints and structured data for strategy planning.
"""
import requests
import json
import sys
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN", "")
BASE = "https://api.pinterest.com/v5"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def api_get(endpoint, params=None):
    url = f"{BASE}{endpoint}"
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    print(f"\n--- GET {endpoint} [{r.status_code}] ---")
    if r.status_code == 200:
        data = r.json()
        return data
    else:
        print(f"Error: {r.text[:500]}")
        return None

results = {}

print("1. ACCOUNT INFO")
results["account"] = api_get("/user_account")
if results["account"]:
    print(f"Username: {results['account'].get('username')}")
    print(f"Business Name: {results['account'].get('business_name')}")

print("\n2. ANALYTICS (30 Days)")
end_date = datetime.now().strftime("%Y-%m-%d")
start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
results["analytics"] = api_get("/user_account/analytics", {
    "start_date": start_date,
    "end_date": end_date,
    "metric_types": "IMPRESSION,PIN_CLICK,OUTBOUND_CLICK,SAVE"
})
if results["analytics"]:
    print(json.dumps(results["analytics"], indent=2))

print("\n3. TRENDS - GENERAL (US/Growing)")
# Path: /v5/trends/keywords/{region}/top/{trend_type}
results["trends_growing"] = api_get("/trends/keywords/US/top/growing", {
    "interests": "beauty,home_decor,fashion"
})
if results["trends_growing"]:
    print("Top Growing Trends sampled:")
    print(json.dumps(results["trends_growing"].get("items", [])[:10], indent=2))

print("\n4. TRENDS - SPECIFIC INTERESTS")
for interest in ["beauty", "home_decor", "fashion"]:
    print(f"Interest: {interest}")
    t = api_get(f"/trends/keywords/US/top/growing", {"interests": interest})
    if t and "items" in t:
        print(f"Found {len(t['items'])} trends for {interest}")

print("\n5. TOP PINS")
results["top_pins"] = api_get("/user_account/analytics/top_pins", {
    "start_date": start_date,
    "end_date": end_date,
    "sort_by": "IMPRESSION",
    "metric_types": "IMPRESSION,OUTBOUND_CLICK,SAVE"
})
if results["top_pins"] and "items" in results["top_pins"]:
     for pin in results["top_pins"]["items"][:5]:
         print(f"Pin ID: {pin.get('pin_id')} | Impr: {pin.get('metrics', {}).get('IMPRESSION')} | Link: {pin.get('link')}")

print("\nDONE")
