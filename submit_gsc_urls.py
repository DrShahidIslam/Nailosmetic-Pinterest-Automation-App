"""
Google Search Console & Indexing API Auto-Submitter
===================================================
Automatically submits a batch of published URLs to the Google Indexing API daily.
Rotates and restarts url submissions once all published URLs have been processed.
"""

import os
import json
import requests
from pathlib import Path
from google.oauth2 import service_account
from google.auth.transport.requests import Request

# Reconfigure stdout for UTF-8 compatibility
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PUBLISHED_LINKS_PATH = Path("shared/published_links.json")
SUBMITTED_LINKS_PATH = Path("shared/gsc_submitted_links.json")
GSC_KEY_PATH = Path("nailosmetic-5f067c977cf8.json")
GSC_KEY_FALLBACK = Path("gsc_key.json")

BATCH_SIZE = 10  # Safe daily volume (API limit is 200 per day)

def get_google_credentials():
    """
    Load credentials from environment variable JSON or local secret key file.
    """
    # 1. Try env variable first (preferred in GitHub Actions)
    credentials_json_str = os.getenv("GSC_CREDENTIALS_JSON")
    if credentials_json_str:
        try:
            print("🔑 Loading credentials from GSC_CREDENTIALS_JSON environment variable...")
            info = json.loads(credentials_json_str)
            return service_account.Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/indexing"]
            )
        except Exception as e:
            print(f"⚠️ Failed to parse credentials from environment variable: {e}")

    # 2. Fall back to local key files
    for key_file in [GSC_KEY_PATH, GSC_KEY_FALLBACK]:
        if key_file.exists():
            print(f"🔑 Loading credentials from local key file: {key_file}...")
            return service_account.Credentials.from_service_account_file(
                str(key_file),
                scopes=["https://www.googleapis.com/auth/indexing"]
            )

    return None

def submit_url_to_indexing_api(url: str, credentials) -> bool:
    """
    Submit a single URL to the Google Indexing API.
    """
    print(f"🚀 Submitting URL to GSC Indexing: {url}")
    
    # Refresh token
    credentials.refresh(Request())
    access_token = credentials.token
    
    endpoint = "https://indexing.googleapis.com/v3/urlNotifications:publish"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    payload = {
        "url": url,
        "type": "URL_UPDATED"
    }
    
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            print(f"   ✅ Successfully submitted: {url}")
            return True
        else:
            print(f"   ❌ GSC Indexing API error {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Network error during GSC submission: {e}")
        return False

def main():
    print("============================================================")
    print("🚦 Starting GSC Indexing URL Submitter")
    print("============================================================")
    
    # 1. Load Credentials
    credentials = get_google_credentials()
    if not credentials:
        print("❌ Error: No Google Service Account credentials found. Please set GSC_CREDENTIALS_JSON or place your key file at the root.")
        return
        
    # 2. Load published links
    if not PUBLISHED_LINKS_PATH.exists():
        print(f"❌ Error: {PUBLISHED_LINKS_PATH} does not exist. No URLs to submit.")
        return
        
    try:
        with open(PUBLISHED_LINKS_PATH, "r", encoding="utf-8") as f:
            published_data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading {PUBLISHED_LINKS_PATH}: {e}")
        return
        
    # Extract list of URLs
    all_urls = []
    for item in published_data:
        url = item.get("url") or item.get("link")
        if url and url.startswith("http"):
            # Strip UTM parameters if present to index clean URLs
            clean_url = url.split("?")[0]
            if clean_url not in all_urls:
                all_urls.append(clean_url)
                
    if not all_urls:
        print("❌ No valid URLs found in published links.")
        return
        
    print(f"📋 Total published URLs tracked: {len(all_urls)}")
    
    # 3. Load previously submitted links
    submitted_urls = []
    if SUBMITTED_LINKS_PATH.exists():
        try:
            with open(SUBMITTED_LINKS_PATH, "r", encoding="utf-8") as f:
                submitted_urls = json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading {SUBMITTED_LINKS_PATH}, resetting submitted list: {e}")
            
    print(f"📋 URLs already submitted in current rotation: {len(submitted_urls)}")
    
    # 4. Filter for URLs not yet submitted
    remaining_urls = [u for u in all_urls if u not in submitted_urls]
    print(f"⏳ Remaining URLs to submit: {len(remaining_urls)}")
    
    # 5. Restart rotation if all URLs are submitted
    if not remaining_urls:
        print("🔄 All URLs have been submitted in the current rotation. Restarting submission loop...")
        submitted_urls = []
        remaining_urls = all_urls
        
    # 6. Submit batch
    batch_to_submit = remaining_urls[:BATCH_SIZE]
    print(f"🔥 Preparing to submit batch of {len(batch_to_submit)} URLs...")
    
    successful_submissions = []
    for url in batch_to_submit:
        if submit_url_to_indexing_api(url, credentials):
            successful_submissions.append(url)
            
    # 7. Update and save submission state
    if successful_submissions:
        submitted_urls.extend(successful_submissions)
        try:
            # Ensure the shared directory exists
            SUBMITTED_LINKS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(SUBMITTED_LINKS_PATH, "w", encoding="utf-8") as f:
                json.dump(submitted_urls, f, indent=2, ensure_ascii=False)
            print(f"💾 Updated submission state saved to {SUBMITTED_LINKS_PATH}.")
        except Exception as e:
            print(f"❌ Error saving submission state to {SUBMITTED_LINKS_PATH}: {e}")
            
    print("============================================================")
    print("✨ GSC Indexing URL Submitter Complete!")
    print("============================================================")

if __name__ == "__main__":
    main()
