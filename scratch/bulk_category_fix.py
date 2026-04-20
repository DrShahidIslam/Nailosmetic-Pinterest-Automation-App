import os
import html
from wordpress_automation.wp_client import WordPressClient
from dotenv import load_dotenv

load_dotenv()

def janitor_fix():
    url = os.getenv("WORDPRESS_URL")
    user = os.getenv("WORDPRESS_USER")
    pw = os.getenv("WORDPRESS_APP_PASSWORD")
    wp = WordPressClient(url, user, pw)
    
    # 1. Map Names to IDs
    cats_raw = wp.get_categories()
    cat_map = {html.unescape(c["name"]).lower(): c["id"] for c in cats_raw}
    
    # Target IDs
    ID_FASHION = cat_map.get("styles & fashion")
    ID_HAIR = cat_map.get("hair & beauty")
    ID_HOME = cat_map.get("home & garden")
    
    if not all([ID_FASHION, ID_HAIR, ID_HOME]):
        print(f"Error: Missing target categories. Found: {list(cat_map.keys())}")
        return

    # 2. Define Keywords
    rules = [
        {"keywords": ["outfit", "look", "wear", "leggings", "fashion"], "target_id": ID_FASHION, "target_name": "Styles & Fashion"},
        {"keywords": ["hair", "updo", "curly", "braid", "hairstyles"], "target_id": ID_HAIR, "target_name": "Hair & Beauty"},
        {"keywords": ["decor", "home", "garden", "patio", "living", "interior"], "target_id": ID_HOME, "target_name": "Home & Garden"},
    ]

    print("\n[JANITOR] Starting: Scanning last 100 posts for miscategorization...")
    
    response = wp.session.get(f"{wp.api_url}/posts", headers=wp.headers, params={"per_page": 100})
    if response.status_code != 200:
        print(f"Failed to fetch posts: {response.text}")
        return
        
    posts = response.json()
    fixed_count = 0
    checked_count = 0
    
    for p in posts:
        checked_count += 1
        p_id = p["id"]
        p_title = html.unescape(p["title"]["rendered"]).lower()
        current_cats = p.get("categories", [])
        
        for rule in rules:
            if any(k in p_title for k in rule["keywords"]):
                # If target_id not in current categories, fix it
                if rule["target_id"] not in current_cats:
                    print(f"Warning: Miscategorized: '{p_title}' (ID: {p_id})")
                    print(f"   Current: {current_cats} | Moving to: {rule['target_name']} (ID: {rule['target_id']})")
                    
                    update_resp = wp.session.post(
                        f"{wp.api_url}/posts/{p_id}",
                        headers=wp.headers,
                        json={"categories": [rule["target_id"]]}
                    )
                    if update_resp.status_code == 200:
                        print(f"   Success!")
                        fixed_count += 1
                    else:
                        print(f"   Failed to fix: {update_resp.text}")
                break # Only match one rule per post
                
    print(f"\nJanitor Complete: Checked {checked_count} posts. Fixed {fixed_count} miscategorized articles.")

if __name__ == "__main__":
    janitor_fix()
