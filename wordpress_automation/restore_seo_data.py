import os
import sys
import json
import time
from pathlib import Path

# Add root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from wordpress_automation.wp_client import WordPressClient

def main():
    load_dotenv()
    
    url = os.getenv('WORDPRESS_URL', 'https://nailosmetic.com')
    user = os.getenv('WORDPRESS_USER', '')
    pwd = os.getenv('WORDPRESS_APP_PASSWORD', '')
    
    if not all([url, user, pwd]):
        print("ERROR: Missing WordPress credentials in .env")
        return

    wp = WordPressClient(url, user, pwd)
    
    # 1. Load published links
    links_path = Path(__file__).parent.parent / "shared" / "published_links.json"
    if not links_path.exists():
        print("ERROR: published_links.json not found")
        return
        
    with open(links_path, "r") as f:
        published = json.load(f)
        
    # 2. Focus on recent posts (last 20)
    recent_posts = published[-20:]
    print(f"Restoring SEO data for the {len(recent_posts)} most recent posts...")
    
    for item in recent_posts:
        slug = item.get("slug")
        topic = item.get("topic")
        
        if not slug:
            continue
            
        print(f"Processing: {slug}...")
        
        # Search for post by slug to get ID
        try:
            search_url = f"{wp.api_url}/posts?slug={slug}&context=edit"
            resp = wp.session.get(search_url, headers=wp.headers)
            if resp.status_code == 200 and resp.json():
                post = resp.json()[0]
                post_id = post["id"]
                
                # Determine focus keyword (either from topic or slug)
                # If topic exists and is short, use it. Otherwise use slug words.
                focus_kw = topic if topic and len(topic.split()) <= 4 else slug.replace("-", " ")
                
                print(f"   Found ID {post_id}. Setting focus keyword: '{focus_kw}'")
                
                # Update meta
                update_url = f"{wp.api_url}/posts/{post_id}"
                payload = {
                    "meta": {
                        "rank_math_focus_keyword": focus_kw,
                        "rank_math_title": post.get("title", {}).get("raw", post.get("title", {}).get("rendered", "")),
                        "rank_math_description": focus_kw.title() + " - Discover the latest trends and tips on Nailosmetic."
                    }
                }
                
                up_resp = wp.session.post(update_url, headers=wp.headers, json=payload)
                if up_resp.status_code == 200:
                    print(f"   SUCCESS! Rank Math data restored.")
                else:
                    print(f"   FAILED to update: {up_resp.status_code}")
            else:
                print(f"   Post not found or API error for slug: {slug}")
        except Exception as e:
            print(f"   Error: {e}")
            
        time.sleep(2) # Prevent rate limiting

    print("\nRestoration complete!")

if __name__ == "__main__":
    main()
