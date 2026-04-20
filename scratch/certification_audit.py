import os
import json
import html
from pathlib import Path
from wordpress_automation.wp_client import WordPressClient
from dotenv import load_dotenv

load_dotenv()

def certification_audit():
    url = os.getenv("WORDPRESS_URL")
    user = os.getenv("WORDPRESS_USER")
    pw = os.getenv("WORDPRESS_APP_PASSWORD")
    wp = WordPressClient(url, user, pw)
    
    print("\n--- [CERTIFICATION AUDIT] Final System Sync Check ---")
    
    # 1. Check WordPress Post Count
    response = wp.session.get(f"{wp.api_url}/posts", headers=wp.headers, params={"per_page": 100})
    wp_posts = response.json()
    wp_count = len(wp_posts)
    print(f"Post Audit: WordPress Live Posts (last 100): Found {wp_count}")
    
    # 2. Check Database Sync
    published_links_path = Path("shared/published_links.json")
    with open(published_links_path, "r", encoding="utf-8") as f:
        db_links = json.load(f)
    db_count = len(db_links)
    print(f"Data Audit: Database Records (links available for Pinterest): {db_count}")
    
    # 3. Check for specific miscategorisation leaks (Health Check)
    leaks = 0
    nail_cats = [6, 4, 3, 12, 5] # Aesthetic, Chrome, Minimalist, Nails Parent, Seasonal
    fashion_cat = 11
    hair_cat = 9
    
    for p in wp_posts:
        title = html.unescape(p["title"]["rendered"]).lower()
        cats = p.get("categories", [])
        
        # Test 1: Fashion article in nail category?
        if any(k in title for k in ["outfit", "leggings", "fashion", "look"]) and not any(k in title for k in ["nail", "mani"]):
            if any(nc in cats for nc in nail_cats) and fashion_cat not in cats:
                print(f"   [ERROR] LEAK DETECTED: Fashion article '{title}' is still in a nail category!")
                leaks += 1
        
        # Test 2: Hair article in nail category?
        if any(k in title for k in ["hair", "updo", "curly"]) and not any(k in title for k in ["nail", "mani"]):
            if any(nc in cats for nc in nail_cats) and hair_cat not in cats:
                print(f"   [ERROR] LEAK DETECTED: Hair article '{title}' is still in a nail category!")
                leaks += 1

    if leaks == 0:
        print("Category Health [PASS]: No leaks found. All checked articles are in their respective authority niches.")
    else:
        print(f"Category Health [FAIL]: {leaks} leaks found. Janitor might need more rules.")

    # 4. Check Data Correspondence
    missing_links = 0
    wp_slugs = {p["slug"] for p in wp_posts}
    db_slugs = {item["slug"] for item in db_links}
    
    for slug in wp_slugs:
        if slug not in db_slugs:
            missing_links += 1
            
    if missing_links == 0:
        print("Database Sync [PASS]: 100% of analyzed WordPress posts are mapped in the Pinterest Link Database.")
    else:
        print(f"Database Sync [FAIL]: {missing_links} WordPress posts are still missing from the database.")

if __name__ == "__main__":
    certification_audit()
