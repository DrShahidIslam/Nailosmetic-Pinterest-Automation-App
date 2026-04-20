import os
import html
from wordpress_automation.wp_client import WordPressClient
from dotenv import load_dotenv

load_dotenv()

def refine_janitor():
    url = os.getenv("WORDPRESS_URL")
    user = os.getenv("WORDPRESS_USER")
    pw = os.getenv("WORDPRESS_APP_PASSWORD")
    wp = WordPressClient(url, user, pw)
    
    # 1. Map Names to IDs
    cats_raw = wp.get_categories()
    cat_map = {html.unescape(c["name"]).lower(): c["id"] for c in cats_raw}
    
    ID_FASHION = cat_map.get("styles & fashion")
    ID_NAILS_PARENT = cat_map.get("nails and manicure")
    # Sub-cats
    ID_AESTHETIC = cat_map.get("aesthetic & art")
    ID_CLEAN = cat_map.get("minimalist & clean girl")
    
    print("\n[REFINED JANITOR] Fixing accidental over-categorization...")
    
    response = wp.session.get(f"{wp.api_url}/posts", headers=wp.headers, params={"per_page": 100})
    posts = response.json()
    
    back_to_nails = 0
    
    for p in posts:
        p_id = p["id"]
        p_title = html.unescape(p["title"]["rendered"]).lower()
        current_cats = p.get("categories", [])
        
        # If it's in Fashion but contains "Nails" or "Mani", move it back
        if ID_FASHION in current_cats and ("nail" in p_title or "mani" in p_title):
            print(f"Warning: Accidental Move Found: '{p_title}' (ID: {p_id})")
            
            # Determine best nail sub-cat
            target_nail_cat = ID_NAILS_PARENT
            if "aesthetic" in p_title or "art" in p_title: target_nail_cat = ID_AESTHETIC
            elif "clean" in p_title: target_nail_cat = ID_CLEAN
            
            print(f"   Moving back to Nail system category: {target_nail_cat}")
            wp.session.post(
                f"{wp.api_url}/posts/{p_id}",
                headers=wp.headers,
                json={"categories": [target_nail_cat]}
            )
            back_to_nails += 1

    print(f"\nRefinement Complete: Moved {back_to_nails} nail articles back to nail categories.")

if __name__ == "__main__":
    refine_janitor()
