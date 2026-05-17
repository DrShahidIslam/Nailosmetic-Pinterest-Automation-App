import os
import sys
import base64
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Ensure stdout handles unicode
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

PINTEREST_ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN", "").strip("'").strip('"')
PINTEREST_REFRESH_TOKEN = os.getenv("PINTEREST_REFRESH_TOKEN", "").strip("'").strip('"')
PINTEREST_APP_ID = os.getenv("PINTEREST_APP_ID", "").strip("'").strip('"')
PINTEREST_APP_SECRET = os.getenv("PINTEREST_APP_SECRET", "").strip("'").strip('"')

def refresh_token():
    global PINTEREST_ACCESS_TOKEN, PINTEREST_REFRESH_TOKEN
    print("🔄 Attempting to refresh Pinterest access token...")
    
    if not all([PINTEREST_REFRESH_TOKEN, PINTEREST_APP_ID, PINTEREST_APP_SECRET]):
        print("❌ Missing refresh token, App ID, or App Secret in .env!")
        return False
        
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
        "scope": "boards:read,boards:write,pins:read,pins:write,user_accounts:read"
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
                print("✅ Access token refreshed successfully!")
                
                # Read original .env content
                with open(".env", "r", encoding="utf-8") as f:
                    env_lines = f.readlines()
                
                # Update PINTEREST_ACCESS_TOKEN and potentially PINTEREST_REFRESH_TOKEN
                updated = False
                for idx, line in enumerate(env_lines):
                    if line.startswith("PINTEREST_ACCESS_TOKEN="):
                        env_lines[idx] = f"PINTEREST_ACCESS_TOKEN='{new_access_token}'\n"
                        updated = True
                    if new_refresh_token and line.startswith("PINTEREST_REFRESH_TOKEN="):
                        env_lines[idx] = f"PINTEREST_REFRESH_TOKEN='{new_refresh_token}'\n"
                        PINTEREST_REFRESH_TOKEN = new_refresh_token
                        print("⚠️ Received new refresh token. Updated in memory and .env.")
                
                if not updated:
                    env_lines.append(f"\nPINTEREST_ACCESS_TOKEN='{new_access_token}'\n")
                    
                with open(".env", "w", encoding="utf-8") as f:
                    f.writelines(env_lines)
                print("💾 Saved updated tokens to .env")
                return True
        else:
            print(f"❌ Token refresh failed with code {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception during token refresh: {e}")
        return False

def api_get(endpoint, params=None):
    url = f"https://api.pinterest.com/v5{endpoint}"
    headers = {"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}", "Content-Type": "application/json"}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    print(f"\n--- GET {endpoint} [{r.status_code}] ---")
    if r.status_code == 200:
        return r.json()
    else:
        print(f"Error details: {r.text}")
        return None

def main():
    if not refresh_token():
        print("⚠️ Proceeding with existing access token (may fail if expired)...")
        
    results = {}
    
    print("\n1. USER ACCOUNT INFO")
    results["account"] = api_get("/user_account")
    if results["account"]:
        print(json.dumps(results["account"], indent=2))
        
    print("\n2. USER BOARDS")
    results["boards"] = api_get("/boards")
    if results["boards"]:
        print(f"Found {len(results['boards'].get('items', []))} boards.")
        for b in results["boards"].get("items", []):
            print(f"- {b.get('name')} (ID: {b.get('id')}) | URL: {b.get('pin_thumbnail_urls')}")
            
    print("\n3. ANALYTICS (Last 30 Days)")
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    results["analytics"] = api_get("/user_account/analytics", {
        "start_date": start_date,
        "end_date": end_date,
        "metric_types": "IMPRESSION,PIN_CLICK,OUTBOUND_CLICK,SAVE"
    })
    if results["analytics"]:
        print(json.dumps(results["analytics"], indent=2))
        
    print("\n4. TOP PINS (Last 30 Days)")
    results["top_pins"] = api_get("/user_account/analytics/top_pins", {
        "start_date": start_date,
        "end_date": end_date,
        "sort_by": "IMPRESSION",
        "metric_types": "IMPRESSION,OUTBOUND_CLICK,SAVE"
    })
    if results["top_pins"]:
        print(json.dumps(results["top_pins"], indent=2))
        
    # Save the fetched data to a JSON file for analysis
    with open("recent_pinterest_stats.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\n📊 Saved recent stats to recent_pinterest_stats.json")

if __name__ == "__main__":
    main()
