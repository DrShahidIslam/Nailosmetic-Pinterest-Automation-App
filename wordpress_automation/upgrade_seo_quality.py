import os
import sys
import json
import time
import requests
from pathlib import Path

# Add root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from wordpress_automation.wp_client import WordPressClient

def generate_premium_meta_silicon(api_key, title, topic):
    """Use SiliconFlow (DeepSeek) to generate high-conversion SEO meta data."""
    url = "https://api.siliconflow.cn/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
You are an elite SEO copywriter. Create a premium, high-CTR SEO title and meta description.

ARTICLE TITLE: {title}
TOPIC: {topic}

REQUIREMENTS:
1. SEO Title: Max 60 chars. Must be punchy and include the primary keyword.
2. Meta Description: 140-160 chars. Must be a benefit-driven hook that makes people click. 
3. DO NOT use generic filler. Focus on specific value.
4. Language: Elegant and professional.

RETURN ONLY VALID JSON:
{{
  "seo_title": "string",
  "seo_description": "string"
}}
"""
    payload = {
        "model": "deepseek-ai/DeepSeek-V3", # High quality model
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        data = resp.json()
        content = data['choices'][0]['message']['content']
        return json.loads(content)
    except Exception as e:
        print(f"   SiliconFlow error: {e}")
        return None

def main():
    load_dotenv()
    
    wp_url = os.getenv('WORDPRESS_URL', 'https://nailosmetic.com')
    wp_user = os.getenv('WORDPRESS_USER', '')
    wp_pwd = os.getenv('WORDPRESS_APP_PASSWORD', '')
    sf_key = os.getenv('SILICONFLOW_API_KEY', '')
    
    if not all([wp_url, wp_user, wp_pwd, sf_key]):
        print("ERROR: Missing credentials")
        return

    wp = WordPressClient(wp_url, wp_user, wp_pwd)
    
    target_slugs = [
        "color-drenching-bedroom-tips",
        "nail-art-designs-ultimate-guide",
        "best-cucumber-trellis-ideas"
    ]
    
    print(f"UPGRADING SEO meta quality via SiliconFlow for: {target_slugs}")
    
    for slug in target_slugs:
        print(f"\nProcessing: {slug}...")
        try:
            resp = wp.session.get(f"{wp.api_url}/posts?slug={slug}&context=edit", headers=wp.headers)
            if resp.status_code == 200 and resp.json():
                post = resp.json()[0]
                post_id = post["id"]
                title = post["title"]["raw"] if "raw" in post["title"] else post["title"]["rendered"]
                
                premium = generate_premium_meta_silicon(sf_key, title, slug.replace("-", " "))
                
                if premium:
                    print(f"   NEW Title: {premium['seo_title']}")
                    print(f"   NEW Desc: {premium['seo_description']}")
                    
                    payload = {
                        "meta": {
                            "rank_math_title": premium['seo_title'],
                            "rank_math_description": premium['seo_description']
                        }
                    }
                    up_resp = wp.session.post(f"{wp.api_url}/posts/{post_id}", headers=wp.headers, json=payload)
                    if up_resp.status_code == 200:
                        print(f"   SUCCESS: Applied to ID {post_id}")
                    else:
                        print(f"   FAILED: {up_resp.status_code}")
                else:
                    print(f"   ERROR: Could not generate meta data")
            else:
                print(f"   NOT FOUND: {slug}")
        except Exception as e:
            print(f"   ERROR: {e}")
        
        time.sleep(1)

    print("\nDONE: All SEO meta data upgraded.")

if __name__ == "__main__":
    main()
