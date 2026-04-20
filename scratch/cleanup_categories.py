import os
import json
import html
from wordpress_automation.wp_client import WordPressClient
from dotenv import load_dotenv

load_dotenv()

def cleanup_categories():
    url = os.getenv("WORDPRESS_URL")
    user = os.getenv("WORDPRESS_USER")
    pw = os.getenv("WORDPRESS_APP_PASSWORD")
    
    wp = WordPressClient(url, user, pw)
    
    # Target Mappings
    corrections = [
        {"title": "15+ Elegant Updo Hairstyles for Every Occasion", "category": "Hair & Beauty"},
        {"title": "15 Effortless Wash and Go Curly Hair Styles You Need to Try", "category": "Hair & Beauty"},
        {"title": "25+ Stunning San Francisco Outfits for Spring", "category": "Styles & Fashion"}
    ]
    
    cats = wp.get_categories()
    cat_map = {html.unescape(c["name"]).lower(): c["id"] for c in cats}
    
    print("Starting Category Cleanup...")
    
    for item in corrections:
        # Search for post by title
        # Note: WordPress API search is fuzzy, so we'll check the result
        response = wp.session.get(f"{wp.api_url}/posts", headers=wp.headers, params={"search": item["title"]})
        if response.status_code == 200:
            posts = response.json()
            found = False
            for p in posts:
                # Close enough title match
                if item["title"].lower() in p["title"]["rendered"].lower():
                    post_id = p["id"]
                    target_cat_name = item["category"]
                    target_id = cat_map.get(target_cat_name.lower())
                    
                    if target_id:
                        print(f"[FOUND] Post: '{p['title']['rendered']}' (ID: {post_id})")
                        print(f"   Moving to category: {target_cat_name} (ID: {target_id})")
                        
                        update_resp = wp.session.post(
                            f"{wp.api_url}/posts/{post_id}",
                            headers=wp.headers,
                            json={"categories": [target_id]}
                        )
                        if update_resp.status_code == 200:
                            print(f"   [SYNC] Success!")
                        else:
                            print(f"   [ERROR] Failed to update: {update_resp.text}")
                    else:
                        print(f"   [WARN] Category '{target_cat_name}' not found on site.")
                    found = True
                    break
            if not found:
                print(f"   [WARN] Post not found for: '{item['title']}'")
        else:
            print(f"   [ERROR] Search failed for '{item['title']}': {response.text}")

if __name__ == "__main__":
    cleanup_categories()
