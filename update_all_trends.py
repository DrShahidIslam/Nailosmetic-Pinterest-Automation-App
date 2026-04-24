import os
import json
import requests

TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN")
if not TOKEN:
    print("Error: PINTEREST_ACCESS_TOKEN not set")
    exit(1)

HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Trend types to fetch
trend_types = ["monthly", "growing", "seasonal"]

# Pinterest interests mapping to our niches
# We will filter 'beauty' into 'nails' and 'hair_beauty'
interest_mapping = {
    "beauty": ["nails", "hair_beauty"],
    "home_decor": ["home_garden"],
    "womens_fashion": ["fashion_style"]
}

# Keywords to categorize beauty
nail_words = ["nail", "manicure", "pedicure", "polish", "gel", "acrylic", "french tip", "ombre", "chrome"]
hair_beauty_words = ["hair", "braid", "makeup", "skin", "lip", "bob", "cut", "balayage", "lashes", "brow"]

# Load existing topic bank
bank_file = "shared/topic_bank.json"
try:
    with open(bank_file, "r") as f:
        bank = json.load(f)
except FileNotFoundError:
    bank = {"nails": [], "hair_beauty": [], "home_garden": [], "fashion_style": []}

new_topics_count = {niche: 0 for niche in bank.keys()}
niche_trends = {niche: [] for niche in bank.keys()}

for interest, target_niches in interest_mapping.items():
    for trend_type in trend_types:
        url = f"https://api.pinterest.com/v5/trends/keywords/US/top/{trend_type}"
        params = {"interests": interest, "limit": 50}
        
        print(f"Fetching {trend_type} trends for {interest}...")
        resp = requests.get(url, headers=HEADERS, params=params)
        
        if resp.status_code == 200:
            data = resp.json()
            trends = data.get("trends", [])
            for trend in trends:
                keyword = trend.get("keyword", "").lower()
                metrics = {
                    "keyword": keyword,
                    "growth_mom": trend.get("growth_mom", 0),
                    "growth_yoy": trend.get("growth_yoy", 0),
                    "trend_type": trend_type
                }
                
                # Categorization logic
                assigned_niche = None
                if interest == "beauty":
                    if any(w in keyword for w in nail_words):
                        assigned_niche = "nails"
                    elif any(w in keyword for w in hair_beauty_words):
                        assigned_niche = "hair_beauty"
                elif interest == "home_decor":
                    assigned_niche = "home_garden"
                elif interest == "womens_fashion":
                    assigned_niche = "fashion_style"
                
                if assigned_niche and assigned_niche in bank:
                    # Save metrics for prioritization
                    niche_trends[assigned_niche].append(metrics)
                    
                    # Add to topic bank if not already exists
                    existing_lower = [k.lower() for k in bank[assigned_niche]]
                    if keyword not in existing_lower:
                        bank[assigned_niche].append(keyword)
                        new_topics_count[assigned_niche] += 1
        else:
            print(f"  Failed: {resp.status_code} - {resp.text[:100]}")

print("\n--- Summary of Added Topics ---")
for niche, count in new_topics_count.items():
    print(f"{niche}: +{count} new topics")

# Save updated bank
with open(bank_file, "w") as f:
    json.dump(bank, f, indent=4)

# Save trend metrics for main.py to use
with open("shared/niche_trends.json", "w") as f:
    json.dump(niche_trends, f, indent=4)

print(f"\nSuccessfully updated {bank_file} and shared/niche_trends.json")
