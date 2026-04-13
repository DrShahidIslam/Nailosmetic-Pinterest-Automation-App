"""
Quick script to fetch trending nail-related keywords from the Pinterest Trends API.
Run this locally to populate your topic bank with real trending data.
"""
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Use PINTEREST_TRENDS_TOKEN if set, otherwise fall back to main token
TOKEN = os.getenv("PINTEREST_TRENDS_TOKEN") or os.getenv("PINTEREST_ACCESS_TOKEN")
headers = {"Authorization": f"Bearer {TOKEN}"}

# Fetch trending beauty keywords
all_keywords = []

for trend_type in ["monthly", "growing"]:
    url = f"https://api.pinterest.com/v5/trends/keywords/US/top/{trend_type}"
    params = {
        "interests": "beauty",
        "limit": 50
    }
    
    print(f"\n[TRENDS] Fetching {trend_type} trends...")
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        trends = data.get("trends", [])
        for trend in trends:
            keyword = trend.get("keyword", "")
            # Filter for nail-related keywords
            nail_words = ["nail", "manicure", "pedicure", "polish", "gel", "acrylic", "french tip", "ombre"]
            if any(w in keyword.lower() for w in nail_words):
                all_keywords.append(keyword.lower())
                print(f"   [NAIL] {keyword}")
    else:
        print(f"   [ERROR] Error {response.status_code}: {response.text[:200]}")

# Remove duplicates
unique_keywords = list(set(all_keywords))
print(f"\n[DONE] Found {len(unique_keywords)} nail-related trending keywords!")
print(json.dumps(unique_keywords, indent=2))
