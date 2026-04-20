import os
import html
from wordpress_automation.wp_client import WordPressClient
from dotenv import load_dotenv

load_dotenv()

def find_easter():
    url = os.getenv("WORDPRESS_URL")
    user = os.getenv("WORDPRESS_USER")
    pw = os.getenv("WORDPRESS_APP_PASSWORD")
    wp = WordPressClient(url, user, pw)
    
    cats_raw = wp.get_categories()
    cat_map = {c["id"]: html.unescape(c["name"]) for c in cats_raw}
    
    print("\n--- Searching for 'Easter' articles ---")
    response = wp.session.get(f"{wp.api_url}/posts", headers=wp.headers, params={"search": "Easter"})
    posts = response.json()
    for p in posts:
        p_id = p["id"]
        p_title = html.unescape(p["title"]["rendered"])
        p_cats = [cat_map.get(cid) for cid in p.get("categories", [])]
        print(f"ID: {p_id} | Title: {p_title} | Categories: {p_cats}")

if __name__ == "__main__":
    find_easter()
