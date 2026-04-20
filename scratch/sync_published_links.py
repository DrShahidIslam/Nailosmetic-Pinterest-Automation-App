import os
import html
from pathlib import Path
from wordpress_automation.wp_client import WordPressClient
from shared_data_manager import SmartJSON
from dotenv import load_dotenv

load_dotenv()

def sync_published_links():
    url = os.getenv("WORDPRESS_URL")
    user = os.getenv("WORDPRESS_USER")
    pw = os.getenv("WORDPRESS_APP_PASSWORD")
    wp = WordPressClient(url, user, pw)
    
    # 1. Map Names to Niches (Inferred from category names)
    niche_map = {
        "hair & beauty": "hair_beauty",
        "styles & fashion": "fashion_style",
        "home & garden": "home_garden",
        "nails and manicure": "nails",
        "aesthetic & art": "nails",
        "chrome & glazed": "nails",
        "minimalist & clean girl": "nails",
        "seasonal trends": "nails"
    }
    
    # 2. Fetch Categories for unescaping
    cats_raw = wp.get_categories()
    cat_id_to_name = {c["id"]: html.unescape(c["name"]).lower() for c in cats_raw}
    
    print("\n[SYNC] Scrapping WordPress to rebuild published_links.json...")
    
    response = wp.session.get(f"{wp.api_url}/posts", headers=wp.headers, params={"per_page": 50})
    if response.status_code != 200:
        print(f"Failed to fetch posts: {response.text}")
        return
        
    wp_posts = response.json()
    new_entries = []
    
    for p in wp_posts:
        post_url = p["link"]
        post_slug = p["slug"]
        post_title = html.unescape(p["title"]["rendered"])
        post_cats = p.get("categories", [])
        
        # Determine Niche
        niche = "nails" # Default
        cat_name = "Nails and Manicure" # Default
        
        for cid in post_cats:
            cname = cat_id_to_name.get(cid)
            if cname in niche_map:
                niche = niche_map[cname]
                cat_name = html.unescape(next((c["name"] for c in cats_raw if c["id"] == cid), cname))
                break
                
        new_entries.append({
            "url": post_url,
            "category": cat_name,
            "niche": niche,
            "topic": post_title, # Fallback topic to title
            "slug": post_slug
        })
        
    # 3. Use SmartJSON to update the file
    published_links_path = Path(__file__).parent.parent / "shared" / "published_links.json"
    if SmartJSON.update_file(published_links_path, new_entries):
        print(f"Success: Synced {len(new_entries)} articles from WordPress to published_links.json.")
    else:
        print("Failed to update published_links.json.")

if __name__ == "__main__":
    sync_published_links()
