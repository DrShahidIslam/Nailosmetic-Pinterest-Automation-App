import os
from wordpress_automation.wp_client import WordPressClient
from dotenv import load_dotenv

load_dotenv()

def list_categories():
    url = os.getenv("WORDPRESS_URL")
    user = os.getenv("WORDPRESS_USER")
    pw = os.getenv("WORDPRESS_APP_PASSWORD")
    
    if not all([url, user, pw]):
        print("Missing WP credentials")
        return
        
    wp = WordPressClient(url, user, pw)
    cats = wp.get_categories()
    print("Available Categories:")
    for c in cats:
        print(f"- {c['name']} (ID: {c['id']})")

if __name__ == "__main__":
    list_categories()
