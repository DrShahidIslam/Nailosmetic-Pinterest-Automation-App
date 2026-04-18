"""
Pinterest Strategy Research Script
Saves detailed trend and analytics data for deep analysis.
"""
import requests
import json
import sys
from datetime import datetime, timedelta

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
        return {"error": r.status_code, "text": r.text}

data = {}

# 1. Trends
interests = ["beauty", "home_decor", "womens_fashion", "diy_and_crafts"]
data["trends"] = {}
for interest in interests:
    print(f"Fetching trends for: {interest}")
    data["trends"][interest] = api_get("/trends/keywords/US/top/growing", {"interests": interest})

# 2. Account Overview
data["account"] = api_get("/user_account")

# 3. Analytics (Summary)
end_date = datetime.now().strftime("%Y-%m-%d")
start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
data["analytics_summary"] = api_get("/user_account/analytics", {
    "start_date": start_date,
    "end_date": end_date,
    "metric_types": "IMPRESSION,PIN_CLICK,OUTBOUND_CLICK,SAVE"
})

# 4. Top Pins
data["top_pins"] = api_get("/user_account/analytics/top_pins", {
    "start_date": start_date,
    "end_date": end_date,
    "sort_by": "IMPRESSION",
    "metric_types": "IMPRESSION,OUTBOUND_CLICK,SAVE"
})

with open("pinterest_research_data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Research data saved to pinterest_research_data.json")
