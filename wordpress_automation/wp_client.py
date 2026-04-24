import requests
import base64
import os
import time
import socket
from typing import Dict, Any, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Optional patch to force IPv4 (avoids "Network is unreachable" issues with IPv6 on some runners)
_original_getaddrinfo = socket.getaddrinfo

def force_ipv4_patch():
    """
    Apply a global patch to force socket.getaddrinfo to only return IPv4 addresses.
    This helps in environments where IPv6 is configured but has no route to the internet.
    """
    def _patched_getaddrinfo(*args, **kwargs):
        responses = _original_getaddrinfo(*args, **kwargs)
        ipv4_responses = [res for res in responses if res[0] == socket.AF_INET]
        return ipv4_responses if ipv4_responses else responses
    socket.getaddrinfo = _patched_getaddrinfo
    print("   🔧 [NETWORKING] IPv4-only patch applied.")

def remove_ipv4_patch():
    """Restores original getaddrinfo."""
    socket.getaddrinfo = _original_getaddrinfo

class WordPressClient:
    def __init__(self, url: str, username: str, app_password: str):
        """
        Initialize the WordPress REST API client with a retry mechanism.
        """
        self.api_url = f"{url.rstrip('/')}/wp-json/wp/v2"
        self.auth = base64.b64encode(f"{username}:{app_password}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {self.auth}"
        }
        
        # Default behavior: try standard connection first. 
        # If WORDPRESS_FORCE_IPV4 is set, we apply the patch immediately.
        if os.getenv("WORDPRESS_FORCE_IPV4", "false").lower() == "true":
            force_ipv4_patch()

        # Configure a robust retry strategy for network glitches and rate limits
        retry_strategy = Retry(
            total=10,
            backoff_factor=5,  # 5s, 10s, 20s, 40s, 80s... 
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # Set a default timeout (connect=30s, read=60s) so we don't hang forever
        self.default_timeout = (30, 60)

    def upload_media(self, file_path: str, alt_text: str = "") -> int:
        """
        Upload an image to the WordPress Media Library.
        Returns the media ID.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Image file not found: {file_path}")

        url = f"{self.api_url}/media"
        filename = os.path.basename(file_path)
        
        with open(file_path, "rb") as f:
            files = {
                "file": (filename, f, "image/jpeg")
            }
            # Note: We don't set Content-Type header manually here, 
            # requests will set multipart/form-data with boundary automatically.
            response = self.session.post(url, headers=self.headers, files=files, timeout=self.default_timeout)

        if response.status_code != 201:
            raise Exception(f"Failed to upload media: {response.status_code} - {response.text}")

        media_id = response.json()["id"]
        
        # Update Alt Text (WP REST API sometimes needs a separate update for alt text)
        if alt_text:
            time.sleep(5) # ⏳ Added delay to prevent 429 after initial upload
            self._update_media_alt_text(media_id, alt_text)
            
        return media_id

    def _update_media_alt_text(self, media_id: int, alt_text: str):
        url = f"{self.api_url}/media/{media_id}"
        data = {"alt_text": alt_text}
        self.session.post(url, headers=self.headers, json=data, timeout=self.default_timeout)

    def create_post(self, title: str, content: str, featured_media_id: Optional[int] = None, categories: Optional[list] = None, meta: Optional[dict] = None, slug: Optional[str] = None, status: str = "publish") -> Dict[str, Any]:
        """
        Create a new post in WordPress.
        """
        url = f"{self.api_url}/posts"
        payload = {
            "title": title,
            "content": content,
            "status": status,
        }
        if featured_media_id:
            payload["featured_media"] = featured_media_id
        if categories:
            payload["categories"] = categories
        if meta:
            payload["meta"] = meta
        if slug:
            payload["slug"] = slug

        response = self.session.post(url, headers=self.headers, json=payload, timeout=self.default_timeout)
        
        if response.status_code != 201:
            raise Exception(f"Failed to create post: {response.status_code} - {response.text}")

        return response.json()

    def get_categories(self) -> list:
        """
        Fetch all existing categories.
        """
        url = f"{self.api_url}/categories"
        params = {"per_page": 100}
        response = self.session.get(url, headers=self.headers, params=params, timeout=self.default_timeout)
        response.raise_for_status() # Raise error for 4xx or 5xx
        return response.json()

    def test_connection(self) -> Dict[str, Any]:
        """
        Performs a diagnostic connection test.
        Returns a dict with success status and detailed error message if any.
        """
        domain = self.api_url.split("//")[-1].split("/")[0]
        result = {"success": False, "error": None, "ipv4_forced": False}
        
        try:
            # 1. DNS Check
            socket.gethostbyname(domain)
        except socket.gaierror as e:
            result["error"] = f"DNS Resolution Failed: {e}"
            return result

        try:
            # 2. API Reachability
            self.get_categories()
            result["success"] = True
            return result
        except requests.exceptions.SSLError as e:
            result["error"] = f"SSL/HTTPS Error (possible proxy or firewall issue): {e}"
        except requests.exceptions.ConnectTimeout as e:
            result["error"] = f"Connection Timeout (server didn't respond in time): {e}"
        except requests.exceptions.ConnectionError as e:
            # Check if it's "Network is unreachable"
            err_msg = str(e)
            if "Network is unreachable" in err_msg or "unreachable" in err_msg.lower():
                result["error"] = f"Network Unreachable (IPv6 issue?): {e}"
                # Try to auto-apply IPv4 patch and retry once internally
                print("   ⚠️  Network unreachable detected. Attempting IPv4-only fallback...")
                force_ipv4_patch()
                result["ipv4_forced"] = True
                try:
                    self.get_categories()
                    result["success"] = True
                    return result
                except Exception as e2:
                    result["error"] = f"Retry with IPv4 failed: {e2}"
            else:
                result["error"] = f"Network Connection Error: {e}"
        except Exception as e:
            result["error"] = f"Unexpected Error: {e}"
            
        return result

    def create_category(self, name: str) -> int:
        """
        Create a new category and return its ID.
        """
        url = f"{self.api_url}/categories"
        payload = {"name": name}
        response = self.session.post(url, headers=self.headers, json=payload, timeout=self.default_timeout)
        if response.status_code == 201:
            return response.json()["id"]
        elif response.status_code == 400: # Probably already exists
            # Try to find it
            cats = self.get_categories()
            for cat in cats:
                if cat["name"].lower() == name.lower():
                    return cat["id"]
        raise Exception(f"Failed to create category: {response.text}")
