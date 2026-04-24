import os
import sys
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Fix Unicode output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from wordpress_automation.wp_client import WordPressClient
from wordpress_automation.trend_discovery import TrendDiscovery
from wordpress_automation.elite_generator import EliteGenerator
from wordpress_automation.image_manager import ImageManager
from shared_data_manager import SmartJSON

def run_elite_flow():
    print("✨ Nailosmetic — Elite Blog Automation Starting...")
    load_dotenv()
    
    # Config
    wp_url = os.getenv("WORDPRESS_URL", "https://nailosmetic.com")
    wp_user = os.getenv("WORDPRESS_USER", "")
    wp_pass = os.getenv("WORDPRESS_APP_PASSWORD", "")
    gemini_keys_raw = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
    gemini_keys = [k.strip() for k in gemini_keys_raw.split(",") if k.strip()]
    silicon_key = os.getenv("SILICONFLOW_API_KEY")
    # Hugging Face Keys (Support multi-key cycling)
    hf_keys_raw = os.getenv("HUGGINGFACE_API_KEYS", "") or os.getenv("HUGGINGFACE_API_KEY", "")
    hf_keys = [k.strip() for k in hf_keys_raw.split(",") if k.strip()]

    wp = WordPressClient(wp_url, wp_user, wp_pass)
    td = TrendDiscovery(gemini_keys)
    gen = EliteGenerator(gemini_keys)
    img_mgr = ImageManager(hf_api_keys=hf_keys, siliconflow_api_key=silicon_key)

    # 1. Select Niche based on core topics
    import random
    NICHE_WEIGHTS = {
        "nail art and beauty": 0.40,
        "hairstyles and beauty": 0.20,
        "home decor and garden": 0.20,
        "fashion and outfit style": 0.20,
    }
    niches = list(NICHE_WEIGHTS.keys())
    weights = list(NICHE_WEIGHTS.values())
    chosen_niche = random.choices(niches, weights=weights, k=1)[0]
    
    # 2. Discover Topics for the chosen niche
    opportunities = td.discover_opportunity_topics(niche=f"{chosen_niche} trends 2026-2027")
    
    if not opportunities:
        print("⚠️  Discovery hit a quota limit. Using a 'Hand-Picked Gold Mine' fallback topic.")
        topic_data = {
            "topic": "The Ultimate 2026-2027 Guide to 3D Nail Art: Techniques, Tools, and Trend Inspo",
            "entities": ["3D Nail Art", "Builder Gel", "Manicure 2026", "Nail Extensions"],
            "target_keywords": ["3d nail art trends", "sculpted nails 2026", "nail art guide"]
        }
    else:
        # Pick the top one
        topic_data = opportunities[0]
    
    print(f"🎯 Selected Topic: {topic_data['topic']}")

    # 2. Generate Elite Blog Data
    blog_data = gen.generate_elite_blog(topic_data)
    
    # 3. Handle Images and Media
    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"📁 Temp directory: {tmp_dir}")
        import time

        # Featured Image
        feat_media_id = None
        if blog_data.get("featured_image"):
            print("🎨 Generating Elite Featured Image (16:9)...")
            feat_img_path = str(Path(tmp_dir) / "featured.png")
            img_mgr.generate_image(blog_data["featured_image"]["prompt"], "16:9", feat_img_path, prefer_kolors=True)
            
            print("⚡ Converting Featured Image to WebP...")
            feat_webp_path = img_mgr.convert_to_webp(feat_img_path)
            feat_media_id = wp.upload_media(feat_webp_path, blog_data["featured_image"].get("alt_text", blog_data["title"]))
            time.sleep(5) # ⏳ Prevent 429

        html_content = gen.build_elite_html(blog_data)
        
        for section in blog_data["sections"]:
            if section.get("image_prompt") and section["image_prompt"] != "NONE":
                print(f"🎨 Generating Elite In-Content Image for: {section['heading']}...")
                img_path = str(Path(tmp_dir) / f"{section['heading']}.png")
                img_mgr.generate_image(section["image_prompt"], "4:5", img_path, prefer_kolors=True)
                
                print(f"⚡ Converting {section['heading']} to WebP...")
                webp_path = img_mgr.convert_to_webp(img_path)
                
                # Fetch alt text
                alt_text = f"Detailed imagery of {section['heading']} in {blog_data['title']}"
                media_id = wp.upload_media(webp_path, alt_text)
                time.sleep(5) # ⏳ Prevent 429
                
                # Fetch URL
                media_info = wp.session.get(f"{wp.api_url}/media/{media_id}", headers=wp.headers).json()
                img_url = media_info["source_url"]
                img_tag = f'<!-- wp:image {{"id":{media_id},"sizeSlug":"large","linkDestination":"none"}} -->\n<figure class="wp-block-image size-large"><img src="{img_url}" alt="{alt_text}" class="wp-image-{media_id}"/></figure>\n<!-- /wp:image -->'
                html_content = html_content.replace(f"<!-- IMAGE_PLACEHOLDER_{section['heading']} -->", img_tag)

        # 4. Create Post
        print("🚀 Publishing Elite Post to WordPress...")
        
        # Determine category ID for 'blogs'
        wp_cats = wp.get_categories()
        blog_cat_id = 1 # default
        for cat in wp_cats:
            if cat["name"].lower() == "blogs":
                blog_cat_id = cat["id"]
                break
        
        rankmath_meta = {
            "rank_math_title": blog_data["seo"]["title"],
            "rank_math_description": blog_data["seo"]["description"],
            "rank_math_focus_keyword": blog_data["seo"]["focus_keyword"]
        }

        post_result = wp.create_post(
            title=blog_data["title"],
            content=html_content,
            status="publish",
            featured_media_id=feat_media_id,
            categories=[blog_cat_id],
            meta=rankmath_meta,
            slug=blog_data["seo"].get("slug")
        )
        
        if "id" in post_result:
            post_url = post_result["link"]
            post_slug = post_result["slug"]
            print(f"✅ Success! Elite Article Published: {post_url}")
            
            # Update history and banks
            print("📝 Updating history and published links bank...")
            history_path = Path(__file__).parent.parent / "shared" / "history.json"
            SmartJSON.update_file(history_path, [post_slug])
                
            # Map chosen niche to short code for history
            niche_map = {
                "nail art and beauty": "nails",
                "hairstyles and beauty": "hair_beauty",
                "home decor and garden": "home_garden",
                "fashion and outfit style": "fashion_style"
            }
            short_niche = niche_map.get(chosen_niche, "nails")

            published_path = Path(__file__).parent.parent / "shared" / "published_links.json"
            SmartJSON.update_file(published_path, [{
                "url": post_url,
                "category": "blogs",
                "niche": short_niche,
                "topic": topic_data["topic"],
                "slug": post_slug
            }])
        else:
            print(f"❌ Failed to publish: {post_result}")

if __name__ == "__main__":
    run_elite_flow()
