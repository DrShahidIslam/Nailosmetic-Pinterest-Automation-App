import os
import sys
from pathlib import Path

# Add the parent directory to sys.path to import wp_client
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
    
    content = """<!-- wp:paragraph -->
<p><strong>Last updated: May 2026</strong></p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p>At Nailosmetic, transparency is one of our core values. This page explains how we earn money from our content and how that may affect what we recommend.</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>Affiliate Links</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Some of the links on Nailosmetic.com are affiliate links. This means that if you click on a link and make a purchase, we may earn a small commission at no additional cost to you. These commissions help us keep the blog running, fund our research, and continue creating free content for you.</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p>We participate in affiliate programs including, but not limited to, Amazon Associates, ShareASale, and various brand-direct affiliate programs in the beauty, home decor, and fashion industries.</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>Our Editorial Standards</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Affiliate relationships never influence our editorial recommendations. We only feature products we genuinely believe in. If a product does not meet our quality standards, we do not recommend it regardless of commission potential. Our first obligation is always to our readers.</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>Sponsored Content</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Occasionally, Nailosmetic may publish sponsored posts or work with brands on paid collaborations. Any sponsored content is clearly labeled as such. Sponsored content does not change our honest assessment of the products or services featured.</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>Product Reviews</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Some products featured on Nailosmetic may have been provided to us at no cost for review purposes. Regardless of how we received a product, our reviews reflect our genuine experience and opinion.</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>FTC Compliance</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>This disclosure is provided in accordance with the Federal Trade Commission guidelines on endorsements and testimonials in advertising (16 CFR Part 255). We are committed to full transparency with our audience.</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>Questions?</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>If you have any questions about our affiliate relationships or editorial policies, please <a href="https://nailosmetic.com/contact">contact us</a>. We are always happy to clarify.</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p><em>Thank you for reading and supporting Nailosmetic.</em></p>
<!-- /wp:paragraph -->"""

    meta = {
        'rank_math_title': 'Affiliate Disclosure | Nailosmetic',
        'rank_math_description': 'Learn how Nailosmetic earns from affiliate links and how it affects our recommendations. Full transparency with our readers.',
        'rank_math_focus_keyword': 'affiliate disclosure'
    }

    print(f"Creating Affiliate Disclosure page on {url}...")
    try:
        url_pages = f"{wp.api_url}/pages"
        payload = {
            'title': 'Affiliate Disclosure',
            'slug': 'affiliate-disclosure',
            'content': content,
            'status': 'publish',
            'meta': meta
        }
        
        response = wp.session.post(url_pages, headers=wp.headers, json=payload, timeout=60)
        if response.status_code == 201:
            data = response.json()
            print(f"SUCCESS! Affiliate Disclosure page is live: {data['link']}")
        else:
            print(f"FAILED {response.status_code}: {response.text[:500]}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
