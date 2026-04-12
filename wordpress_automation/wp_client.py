import requests
import base64
import os
import time
import socket
from typing import Dict, Any, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Patch to force IPv4 (avoids "Network is unreachable" issues with IPv6 on some runners)
_original_getaddrinfo = socket.getaddrinfo
def _patched_getaddrinfo(*args, **kwargs):
    responses = _original_getaddrinfo(*args, **kwargs)
    return [res for res in responses if res[0] == socket.AF_INET]
socket.getaddrinfo = _patched_getaddrinfo

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
        
        # Configure a robust retry strategy for network glitches
        retry_strategy = Retry(
            total=3,  # 3 retries
            backoff_factor=1,  # Wait 1s, 2s, 4s between attempts
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

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
            response = self.session.post(url, headers=self.headers, files=files)

        if response.status_code != 201:
            raise Exception(f"Failed to upload media: {response.status_code} - {response.text}")

        media_id = response.json()["id"]
        
        # Update Alt Text (WP REST API sometimes needs a separate update for alt text)
        if alt_text:
            self._update_media_alt_text(media_id, alt_text)
            
        return media_id

    def _update_media_alt_text(self, media_id: int, alt_text: str):
        url = f"{self.api_url}/media/{media_id}"
        data = {"alt_text": alt_text}
        self.session.post(url, headers=self.headers, json=data)

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

        response = self.session.post(url, headers=self.headers, json=payload)
        
        if response.status_code != 201:
            raise Exception(f"Failed to create post: {response.status_code} - {response.text}")

        return response.json()

    def get_categories(self) -> list:
        """
        Fetch all existing categories.
        """
        url = f"{self.api_url}/categories"
        params = {"per_page": 100}
        response = self.session.get(url, headers=self.headers, params=params)
        if response.status_code == 200:
            return response.json()
        return []

    def create_category(self, name: str) -> int:
        """
        Create a new category and return its ID.
        """
        url = f"{self.api_url}/categories"
        payload = {"name": name}
        response = self.session.post(url, headers=self.headers, json=payload)
        if response.status_code == 201:
            return response.json()["id"]
        elif response.status_code == 400: # Probably already exists
            # Try to find it
            cats = self.get_categories()
            for cat in cats:
                if cat["name"].lower() == name.lower():
                    return cat["id"]
        raise Exception(f"Failed to create category: {response.text}")
