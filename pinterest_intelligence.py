"""
Pinterest Intelligence Module
==============================
Scrapes live Pinterest search autocompletions, search annotation pills,
and top competitor pin metadata to fuel Gemini content generation.
"""

import requests
import json
import sys
import urllib.parse
from typing import List, Dict, Any

# Reconfigure stdout for UTF-8 handling on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PINTEREST_AUTOCOMPLETE_URL = "https://www.pinterest.com/resource/SearchAutocompleteResource/get/"
PINTEREST_SEARCH_URL = "https://www.pinterest.com/resource/BaseSearchResource/get/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

def fetch_pinterest_annotations(query: str) -> List[str]:
    """
    Fetch live Pinterest search autocomplete suggestions and annotation keywords.
    """
    print(f"🔍 Fetching live Pinterest annotations for query: '{query}'...")
    annotations = []
    try:
        data_payload = {
            "options": {
                "term": query,
                "pin_scope": "pins"
            },
            "context": {}
        }
        params = {
            "source_url": f"/search/pins/?q={urllib.parse.quote(query)}",
            "data": json.dumps(data_payload)
        }
        
        response = requests.get(PINTEREST_AUTOCOMPLETE_URL, headers=HEADERS, params=params, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            items = res_json.get("resource_response", {}).get("data", [])
            for item in items:
                if isinstance(item, dict) and "query" in item:
                    annotations.append(item["query"])
                elif isinstance(item, str):
                    annotations.append(item)
    except Exception as e:
        print(f"   ⚠️ Could not fetch live autocompletions: {e}")

    # Fallback/supplemental search guide extraction if autocomplete is sparse
    if len(annotations) < 3:
        fallback_keywords = [
            f"{query} aesthetic",
            f"minimalist {query}",
            f"classy {query}",
            f"{query} ideas",
            f"simple {query}",
            f"trending {query}"
        ]
        for kw in fallback_keywords:
            if kw not in annotations:
                annotations.append(kw)
                
    cleaned_annotations = list(dict.fromkeys([a.strip().lower() for a in annotations if a.strip()]))
    print(f"   ✅ Retrieved {len(cleaned_annotations)} live annotations: {cleaned_annotations[:5]}")
    return cleaned_annotations[:8]


def fetch_competitor_pins(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Scrape top ranking competitor pins for a target search query on Pinterest.
    Returns titles, descriptions, and visual layout blueprints.
    """
    print(f"🏆 Extracting top competitor winning pins for: '{query}'...")
    competitor_pins = []
    try:
        data_payload = {
            "options": {
                "query": query,
                "scope": "pins",
                "page_size": limit
            },
            "context": {}
        }
        params = {
            "source_url": f"/search/pins/?q={urllib.parse.quote(query)}",
            "data": json.dumps(data_payload)
        }
        
        response = requests.get(PINTEREST_SEARCH_URL, headers=HEADERS, params=params, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            results = res_json.get("resource_response", {}).get("data", {}).get("results", [])
            for pin in results:
                if isinstance(pin, dict):
                    title = pin.get("title") or pin.get("grid_title") or ""
                    description = pin.get("description") or ""
                    repins = pin.get("repin_count", 0)
                    images = pin.get("images", {})
                    img_url = images.get("orig", {}).get("url") or images.get("736x", {}).get("url") or ""
                    
                    if title or description:
                        competitor_pins.append({
                            "title": title,
                            "description": description[:150],
                            "repins": repins,
                            "image_url": img_url
                        })
                        if len(competitor_pins) >= limit:
                            break

        # Supplemental HTML search parse if API resource returned restricted results
        if not competitor_pins:
            search_html_url = f"https://www.pinterest.com/search/pins/?q={urllib.parse.quote(query)}"
            h_resp = requests.get(search_html_url, headers=HEADERS, timeout=10)
            if h_resp.status_code == 200:
                import re
                # Extract initial state script data
                match = re.search(r'<script id="__PINTEREST_INITIAL_RESPONSE__" type="application/json">(.*?)</script>', h_resp.text)
                if match:
                    st_json = json.loads(match.group(1))
                    pins_data = st_json.get("resources", {}).get("BaseSearchResource", {})
                    for key, val in pins_data.items():
                        res_list = val.get("data", {}).get("results", [])
                        for pin in res_list:
                            if isinstance(pin, dict):
                                title = pin.get("title") or pin.get("grid_title") or ""
                                desc = pin.get("description") or ""
                                if title or desc:
                                    competitor_pins.append({
                                        "title": title,
                                        "description": desc[:150],
                                        "repins": pin.get("repin_count", 0),
                                        "image_url": ""
                                    })
                                    if len(competitor_pins) >= limit:
                                        break
    except Exception as e:
        print(f"   ⚠️ Could not fetch competitor pins: {e}")
        
    print(f"   ✅ Extracted {len(competitor_pins)} competitor winning pin blueprints.")
    return competitor_pins

if __name__ == "__main__":
    test_q = "clean girl nails"
    annos = fetch_pinterest_annotations(test_q)
    pins = fetch_competitor_pins(test_q)
    print("Annotations:", annos)
    print("Competitor Pins:", pins)
