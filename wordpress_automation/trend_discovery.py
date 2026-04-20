import os
import sys
import json
import random
import re
from typing import List, Dict, Any
from google import genai
from dotenv import load_dotenv

# Fix Unicode output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

class TrendDiscovery:
    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]

    def _get_client(self, api_key):
        return genai.Client(api_key=api_key)

    def discover_opportunity_topics(self, niche: str = "nails beauty") -> List[Dict[str, Any]]:
        """
        Uses Gemini to discover trending topics and evaluate their 'rankability' (SERP Gaps).
        """
        print(f"🔍 Discovering 'Gold Mine' topics for niche: {niche}...")
        
        prompt = f"""
        You are an Elite SEO Strategist for 'Nailosmetic'. 
        Your goal is to find 3 'Gold Mine' blog post topics for the '{niche}' industry.
        
        A 'Gold Mine' topic must meet these criteria:
        1. HIGH INTEREST: People are actively searching for this in 2024-2025.
        2. LOW COMPETITION: High-domain authority sites (Vogue, Byrdie) haven't deeply covered this yet, OR the Top 10 results are currently dominated by forums like Reddit, Quora, or Pinterest.
        3. ENTITY RICH: A topic that allows us to mention specific brands, materials, and techniques.
        
        RETURN ONLY VALID JSON:
        [
          {{
            "topic": "Specific, clickable blog title idea",
            "reasoning": "Explain why this is a low-competition gap",
            "entities": ["list", "of", "relevant", "entities"],
            "target_keywords": ["keyword1", "keyword2"]
          }}
        ]
        """
        
        errors = []
        for key in self.api_keys:
            client = self._get_client(key)
            for model_name in self.models_to_try:
                try:
                    response = client.models.generate_content(model=model_name, contents=prompt)
                    
                    # Robust extraction
                    import re
                    json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
                    if json_match:
                        raw_json = json_match.group(0)
                        opportunities = json.loads(raw_json)
                        if opportunities:
                            print(f"✅ Found {len(opportunities)} topics using {model_name}.")
                            return opportunities
                    
                    dict_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                    if dict_match:
                        item = json.loads(dict_match.group(0))
                        print(f"✅ Found 1 topic using {model_name} (fallback).")
                        return [item]
                except Exception as e:
                    # Filter common quota errors to avoid log spam
                    msg = str(e)
                    if "429" in msg or "quota" in msg.lower():
                        msg = "429 Quota Exceeded"
                    errors.append(f"{model_name}: {msg}")
                    continue
        
        print(f"❌ All trend discovery attempts failed. Last errors: {errors[-2:] if errors else 'No errors recorded'}")
        return []

if __name__ == "__main__":
    load_dotenv()
    gemini_keys_raw = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
    gemini_keys = [k.strip() for k in gemini_keys_raw.split(",") if k.strip()]
    td = TrendDiscovery(gemini_keys)
    topics = td.discover_opportunity_topics()
    print(json.dumps(topics, indent=2))
