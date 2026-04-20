import os
import html
from wordpress_automation.wp_client import WordPressClient
from dotenv import load_dotenv

load_dotenv()

def deep_audit():
    url = os.getenv("WORDPRESS_URL")
    user = os.getenv("WORDPRESS_USER")
    pw = os.getenv("WORDPRESS_APP_PASSWORD")
    wp = WordPressClient(url, user, pw)
    
    # 1. Fetch Categories
    cats_raw = wp.get_categories()
    cat_map = {c["id"]: html.unescape(c["name"]) for c in cats_raw}
    print("--- Available Categories ---")
    for cid, cname in cat_map.items():
        print(f"ID: {cid} | Name: {cname}")
    
    # 2. Search for the specific articles the user mentioned
    search_queries = ["Leggings Look", "Spring Bar Outfits"]
    print("\n--- Targeted Post Audit ---")
    for query in search_queries:
        response = wp.session.get(f"{wp.api_url}/posts", headers=wp.headers, params={"search": query, "per_page": 5})
        if response.status_code == 200:
            posts = response.json()
            for p in posts:
                p_id = p["id"]
                p_title = html.unescape(p["title"]["rendered"])
                p_cat_ids = p.get("categories", [])
                p_cat_names = [cat_map.get(cid, "Unknown") for cid in p_cat_ids]
                print(f"ID: {p_id} | Title: {p_title}")
                print(f"Current Categories: {p_cat_names}")
        else:
            print(f"Search failed for '{query}': {response.status_code}")

if __name__ == "__main__":
    deep_audit()
