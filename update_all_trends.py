import os
import sys
import json
import requests
import base64
from dotenv import load_dotenv

# Fix Unicode output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (AttributeError, io.UnsupportedOperation):
        pass

load_dotenv()

# Read Pinterest Credentials
PINTEREST_ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN", "").strip("'").strip('"')
PINTEREST_REFRESH_TOKEN = os.getenv("PINTEREST_REFRESH_TOKEN", "").strip("'").strip('"')
PINTEREST_APP_ID = os.getenv("PINTEREST_APP_ID", "").strip("'").strip('"')
PINTEREST_APP_SECRET = os.getenv("PINTEREST_APP_SECRET", "").strip("'").strip('"')

def refresh_pinterest_token() -> str:
    global PINTEREST_ACCESS_TOKEN, PINTEREST_REFRESH_TOKEN
    
    if not all([PINTEREST_REFRESH_TOKEN, PINTEREST_APP_ID, PINTEREST_APP_SECRET]):
        print("   ℹ️ Missing refresh token, App ID, or App Secret. Using current access token.")
        return PINTEREST_ACCESS_TOKEN
        
    print("   🔄 Refreshing Pinterest access token...")
    credentials = base64.b64encode(
        f"{PINTEREST_APP_ID}:{PINTEREST_APP_SECRET}".encode()
    ).decode()

    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "grant_type": "refresh_token",
        "refresh_token": PINTEREST_REFRESH_TOKEN,
    }

    try:
        url = "https://api.pinterest.com/v5/oauth/token"
        response = requests.post(url, headers=headers, data=data, timeout=30)
        
        if response.status_code == 200:
            tokens = response.json()
            new_access_token = tokens.get("access_token")
            new_refresh_token = tokens.get("refresh_token")
            
            if new_access_token:
                PINTEREST_ACCESS_TOKEN = new_access_token
                print("   ✅ Access token refreshed successfully!")
                
                # Expose new refresh token to GitHub Actions if present
                if new_refresh_token:
                    PINTEREST_REFRESH_TOKEN = new_refresh_token
                    github_env = os.getenv("GITHUB_ENV")
                    if github_env:
                        try:
                            with open(github_env, "a", encoding="utf-8") as f:
                                f.write(f"NEW_PINTEREST_REFRESH_TOKEN={new_refresh_token}\n")
                            print("   ✅ Exported new refresh token to GITHUB_ENV.")
                        except Exception as e:
                            print(f"   ⚠️ Failed to write to GITHUB_ENV: {e}")
                
                # Update local .env file
                if os.path.exists(".env"):
                    try:
                        with open(".env", "r", encoding="utf-8") as f:
                            env_lines = f.readlines()
                        
                        updated_access = False
                        updated_refresh = False
                        
                        for idx, line in enumerate(env_lines):
                            if line.startswith("PINTEREST_ACCESS_TOKEN="):
                                env_lines[idx] = f"PINTEREST_ACCESS_TOKEN='{new_access_token}'\n"
                                updated_access = True
                            if new_refresh_token and line.startswith("PINTEREST_REFRESH_TOKEN="):
                                env_lines[idx] = f"PINTEREST_REFRESH_TOKEN='{new_refresh_token}'\n"
                                updated_refresh = True
                                
                        if not updated_access:
                            env_lines.append(f"\nPINTEREST_ACCESS_TOKEN='{new_access_token}'\n")
                        if new_refresh_token and not updated_refresh:
                            env_lines.append(f"PINTEREST_REFRESH_TOKEN='{new_refresh_token}'\n")
                            
                        with open(".env", "w", encoding="utf-8") as f:
                            f.writelines(env_lines)
                        print("   💾 Saved updated tokens to local .env file.")
                    except Exception as e:
                        print(f"   ⚠️ Failed to update .env: {e}")
                
                return new_access_token
        else:
            print(f"   ⚠️ Token refresh failed ({response.status_code}): {response.text[:200]}")
    except Exception as e:
        print(f"   ⚠️ Exception during token refresh: {e}")
        
    return PINTEREST_ACCESS_TOKEN

# Refresh the token
TOKEN = refresh_pinterest_token()
if not TOKEN:
    print("Error: PINTEREST_ACCESS_TOKEN not set or expired")
    exit(1)

HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Trend types to fetch
trend_types = ["monthly", "growing", "seasonal"]

# Pinterest interests mapping to our niches
# We will filter 'beauty' into 'nails' and 'hair_beauty'
interest_mapping = {
    "beauty": ["nails", "hair_beauty"],
    "home_decor": ["home_garden"],
    "womens_fashion": ["fashion_style"],
    "gardening": ["home_garden"]
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
                    "growth_mom": trend.get("pct_growth_mom", 0),
                    "growth_yoy": trend.get("pct_growth_yoy", 0),
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
