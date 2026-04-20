import os
import html
from wordpress_automation.wp_client import WordPressClient
from dotenv import load_dotenv

load_dotenv()

def audit_wordpress():
    url = os.getenv("WORDPRESS_URL")
    user = os.getenv("WORDPRESS_USER")
    pw = os.getenv("WORDPRESS_APP_PASSWORD")
    
    wp = WordPressClient(url, user, pw)
    
    # 1. Get Categories
    cats = wp.get_categories()
    cat_map = {c["id"]: html.unescape(c["name"]) for c in cats}
    
    # 2. Get Recent Posts
    response = wp.session.get(f"{wp.api_url}/posts", headers=wp.headers, params={"per_page": 10})
    if response.status_code == 200:
        posts = response.json()
        print(f"\n--- Recent WordPress Posts Audit ---")
        for p in posts:
            p_title = html.unescape(p["title"]["rendered"])
            p_id = p["id"]
            p_cats = [cat_map.get(cid, str(cid)) for cid in p.get("categories", [])]
            print(f"ID: {p_id} | Title: {p_title}")
            print(f"Categories: {', '.join(p_cats)}")
            print("-" * 30)
    else:
        print(f"Failed to fetch posts: {response.text}")

if __name__ == "__main__":
    audit_wordpress()
