import requests
import base64
import os
from typing import Dict, Any, Optional

class WordPressClient:
    def __init__(self, url: str, username: str, app_password: str):
        """
        Initialize the WordPress REST API client.
        :param url: Base URL of the WordPress site (e.g. https://nailosmetic.com)
        :param username: WordPress username
        :param app_password: WordPress Application Password
        """
        self.api_url = f"{url.rstrip('/')}/wp-json/wp/v2"
        self.auth = base64.b64encode(f"{username}:{app_password}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {self.auth}"
        }

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
            response = requests.post(url, headers=self.headers, files=files)

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
        requests.post(url, headers=self.headers, json=data)

    def create_post(self, title: str, content: str, featured_media_id: Optional[int] = None, categories: Optional[list] = None, status: str = "publish") -> Dict[str, Any]:
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

        response = requests.post(url, headers=self.headers, json=payload)
        
        if response.status_code != 201:
            raise Exception(f"Failed to create post: {response.status_code} - {response.text}")

        return response.json()

    def get_categories(self) -> list:
        """
        Fetch all existing categories.
        """
        url = f"{self.api_url}/categories"
        params = {"per_page": 100}
        response = requests.get(url, headers=self.headers, params=params)
        if response.status_code == 200:
            return response.json()
        return []

    def create_category(self, name: str) -> int:
        """
        Create a new category and return its ID.
        """
        url = f"{self.api_url}/categories"
        payload = {"name": name}
        response = requests.post(url, headers=self.headers, json=payload)
        if response.status_code == 201:
            return response.json()["id"]
        elif response.status_code == 400: # Probably already exists
            # Try to find it
            cats = self.get_categories()
            for cat in cats:
                if cat["name"].lower() == name.lower():
                    return cat["id"]
        raise Exception(f"Failed to create category: {response.text}")
