import os
import requests
from dotenv import load_dotenv

def dry_check():
    load_dotenv()
    url = os.getenv("WORDPRESS_URL")
    user = os.getenv("WORDPRESS_USER")
    pw = os.getenv("WORDPRESS_APP_PASSWORD")
    
    print(f"--- Dry Check: Testing WordPress connectivity to {url} ---")
    try:
        # Testing a simple GET to the posts endpoint
        response = requests.get(
            f"{url}/wp-json/wp/v2/posts",
            auth=(user, pw),
            params={"per_page": 1},
            timeout=15
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Status: SUCCESS (WordPress is UP)")
        elif response.status_code == 401:
            print("Status: FAILED (Authentication Error - check credentials)")
        else:
            print(f"Status: FAILED (Status Code {response.status_code})")
            print(f"Response: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print("Status: ERROR (Request Timed Out)")
    except requests.exceptions.ConnectionError as e:
        print(f"Status: ERROR (Connection Error: {e})")
    except Exception as e:
        print(f"Status: ERROR (Unexpected: {e})")

if __name__ == "__main__":
    dry_check()
