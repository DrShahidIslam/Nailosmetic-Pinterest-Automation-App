import json
import random
import re
import time
from html import unescape
from typing import List, Dict, Any, Optional
from google import genai
from dotenv import load_dotenv

load_dotenv()

class EliteGenerator:
    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.key_idx = 0
        self.models_to_try = [
            "gemini-3.1-flash-lite",
            "gemini-3.1-flash-lite-preview",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ]

    def _get_client(self, api_key: str):
        return genai.Client(api_key=api_key)

    def _call_gemini_json(self, prompt: str, label: str = "") -> Dict[str, Any]:
        """Robust Gemini caller with active round-robin key cycling, smart rate-limit backoff, and model fallback."""
        errors = []
        num_keys = len(self.api_keys)
        
        # Try every key starting from the current rotating index
        for k_offset in range(num_keys):
            active_idx = (self.key_idx + k_offset) % num_keys
            key = self.api_keys[active_idx]
            key_hint = f"...{key[-4:]}" if len(key) >= 4 else f"key-{active_idx+1}"
            client = self._get_client(key)

            for model_name in self.models_to_try:
                for attempt in range(2):
                    try:
                        response = client.models.generate_content(model=model_name, contents=prompt)
                        cleaned = re.sub(r"```json\s*|\s*```", "", response.text).strip()
                        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
                        if json_match:
                            data = json.loads(json_match.group(0))
                            print(f"   ✅ [{label}] {model_name} ({key_hint})")
                            # Advance rotation index for the next call to distribute quota evenly
                            self.key_idx = (active_idx + 1) % num_keys
                            return data
                    except Exception as e:
                        err = str(e)
                        errors.append(f"{model_name} ({key_hint}): {err[:100]}")
                        
                        if "404" in err or "limit: 0" in err or "no longer" in err or "not found" in err:
                            break  # Skip model if sunset/not found
                        
                        # If 429 quota exhausted on this key, pause briefly and rotate to next key
                        if "429" in err or "RESOURCE_EXHAUSTED" in err:
                            wait = 3.0
                            m = re.search(r"retry in ([\d\.]+)s", err)
                            if m:
                                wait = max(wait, float(m.group(1)) + 1.0)
                            print(f"   🔄 [{label}] Rate limit on {key_hint}. Waiting {wait:.1f}s and rotating to next API key...")
                            time.sleep(wait)
                            break
                        
                        time.sleep(2 * (attempt + 1))

        raise Exception(f"Gemini API permanently failed for [{label}] across all {num_keys} keys. Recent errors: {errors[-3:]}")

    def generate_elite_blog(self, topic: str, previous_slugs: List[str], existing_categories: List[str] = None, niche: str = "nails") -> Dict[str, Any]:
        """
        Main orchestration for elite long-form content with internal linking.
        """
        # Define niche to primary pillar mapping (Hubs)
        niche_primary_pillars = {
            "nails": "nail-art-designs-ultimate-guide",
            "hair_beauty": "hairstyles-for-women-ultimate-guide",
            "home_garden": "home-decor-ideas-ultimate-guide",
            "fashion_style": "spring-outfits-women-guide"
        }
        
        internal_link_slug = niche_primary_pillars.get(niche, "nail-art-designs-ultimate-guide")
        homepage_url = "https://nailosmetic.com/"
        primary_pillar_url = f"https://nailosmetic.com/{internal_link_slug}/"
        
        # 1. Silo Linking Setup: Select 2 sibling posts from previous slugs in same niche
        siblings = []
        for s in reversed(previous_slugs):
            if isinstance(s, dict) and s.get("niche") == niche and s.get("slug") != internal_link_slug:
                siblings.append(f"https://nailosmetic.com/{s['slug']}/")
            elif isinstance(s, str) and s != internal_link_slug:
                siblings.append(f"https://nailosmetic.com/{s}/")
            if len(siblings) >= 2: break
            
        sibling_1 = siblings[0] if len(siblings) > 0 else homepage_url
        sibling_2 = siblings[1] if len(siblings) > 1 else homepage_url
        
        print(f"🚀 Generating Elite Blog Article for: {topic}...")
        
        # Step 1: Generate Detailed Outline
        outline = self._generate_outline(topic, homepage_url)
        
        # Step 2: Generate Content for each section
        full_article = []
        sections = outline.get("sections", [])
        for i, section in enumerate(sections):
            print(f"   ✍️  Drafting Section {i+1}/{len(sections)}: {section['heading']}")
            
            # Pass internal links strategically
            target_link = None
            if i == 2: target_link = primary_pillar_url
            elif i == 5: target_link = sibling_1
            elif i == 8: target_link = sibling_2
            
            draft = self._generate_section(topic, section, full_article, target_link)
            full_article.append({
                "heading": section["heading"],
                "content": draft.get("text", ""),
                "image_prompt": draft.get("image_metadata", {}).get("prompt", ""),
                "alt_text": draft.get("image_metadata", {}).get("alt_text", ""),
                "preferred_format": section.get("preferred_format", "")
            })
            
            # Small pacing delay to avoid hitting burst rate limits
            if i < len(sections) - 1:
                time.sleep(2)
            
        # Step 3: Meta and Final Wrap
        blog_data = {
            "title": topic,
            "introduction": outline.get("introduction", ""),
            "featured_image": outline.get("featured_image"),
            "sections": full_article,
            "conclusion": outline.get("conclusion", ""),
            "seo": {
                "title": outline.get("meta_title", f"{topic.title()} | Nailosmetic"),
                "description": outline.get("seo_description", f"Discover the best guide on {topic}."),
                "focus_keyword": topic,
                "slug": outline.get("slug")
            }
        }
        
        return blog_data

    def _generate_outline(self, topic: str, homepage_url: str) -> Dict[str, Any]:
        prompt = f"""
        You are an Elite Content Architect for 'Nailosmetic'. 
        Structure a 3000-word comprehensive, authoritative blog guide about: "{topic}".
        
        PRIMARY KEYWORD PLACEMENT:
        - PRIMARY KEYWORD is the article topic ("{topic}").
        - Place it: in the H1/title, within the first 50 words of the introduction, in at least one H2 (preferably the first H2), in the conclusion, and in the URL slug (3-5 keywords, no year unless the topic is genuinely year-bound).
        
        E-E-A-T & AUTHORITY:
        - Write with first-hand experience signals: "I tested", "in my experience", "what worked for me". Never generic filler, never throat-clearing.
        - Include 1-2 outbound links to authoritative sources (e.g. aad.org, official brand sites). Use only real, well-known domains — NEVER invent or guess URLs.
        
        INTERNAL LINKING & NAVIGATION:
        - The introduction MUST naturally link to the homepage: {homepage_url}
        - After the introduction, include a Table of Contents with jump links to every H2.
        - SEO & NLP: Include a high density of semantic entities and LSI keywords naturally.
        - AEO (Answer Engine Optimization): Headings must be formatted as user questions where applicable.
        - GEO (Generative Engine Optimization): Clear factual capsules and data-backed claims.
        - DISCOVER: The title and introduction must be highly engaging, clickbait-style curiosity gaps (e.g. "The exact polish to...", "Why everyone is switching to...").
        
        STRUCTURE:
        - Exactly 10 to 12 distinct H2/H3 sections.
        - Total word count target is 3000+ words.
        - EXACTLY 3 sections must be designated for in-content images (has_image: true).
        - FAQ REQUIREMENT: EXACTLY one section must use preferred_format 'faq' and contain 3-5 genuine user questions with concise 40-80 word answers. This powers the FAQPage schema. Never skip the FAQ section.
        
        RETURN ONLY VALID JSON:
        {{
          "introduction": "A compelling 150-word hook that sets the stage and creates a curiosity gap for Google Discover. The primary keyword must appear in the first 50 words. The first paragraph MUST be a 'Direct Answer Capsule' for AI Overviews. Follow with a Table of Contents containing jump links (e.g., <a href='#heading-anchor'>) to every H2.",
          "seo_description": "Meta description (max 155 chars)",
          "meta_title": "SEO Title (max 60 chars)",
          "slug": "url-slug-using-3-5-keywords-only",
          "featured_image": {{
            "prompt": "A detailed 16:9 image prompt for the featured image. Must be vibrant, high-contrast, edge-to-edge photography (Discover optimized).",
            "alt_text": "Descriptive alt text for visually impaired"
          }},
          "sections": [
            {{
              "heading": "Clear heading title (use Question formats for AEO, include primary keyword in at least one H2)",
              "goal": "What this section should cover (Aim for 300+ words depth)",
              "has_image": boolean,
              "preferred_format": "paragraph | list | table | faq"
            }}
          ],
          "conclusion": "Summary and final takeaway (must include primary keyword naturally)"
        }}
        """
        return self._call_gemini_json(prompt, label="Outline")

    def _generate_section(self, topic: str, section: Dict[str, Any], previous_sections: List[Dict], target_link: Optional[str] = None) -> Dict[str, Any]:
        context = "\n".join([f"Previous section: {s['heading']}" for s in previous_sections[-3:]])
        
        link_instruction = ""
        if target_link:
            link_instruction = f"INTERNAL LINKING: You MUST naturally include exactly one internal link to '{target_link}' using an HTML anchor tag with relevant anchor text."

        has_img = section.get("has_image", False)
        alt_text_instruction = (
            "ALT TEXT must be descriptive and entity-rich (colors, technique, style actually depicted). "
            "Never start with 'image of'. Never keyword-stuff the alt text."
            if has_img else "NONE"
        )

        prompt = f"""
        You are a top-tier human author for 'Nailosmetic'. 
        Write a deep-dive, 300+ word section for the article "{topic}".
        SECTION HEADING: "{section['heading']}"
        SECTION GOAL: "{section['goal']}"
        PREFERRED FORMAT: "{section['preferred_format']}"
        {link_instruction}
        
        STRICT WRITING RULES:
        1. READABILITY: Conversational but premium.
        2. NO DASHES: NEVER use em-dashes (—) or en-dashes (–).
        3. AEO/GEO: Use clear, factual statements. If the format is 'faq', use Q&A structure with 3-5 user questions and concise 40-80 word answers.
        4. NLP & SEMANTIC ENTITIES: Naturally weave in highly relevant LSI keywords and semantic entities for this topic to maximize SEO.
        5. RICH FORMATTING: If format is 'list', use HTML <ul> or <ol>. If 'table', use HTML <table> with headers.
        6. LENGTH: Be highly verbose and detailed. Provide specific examples and pro-tips. MINIMUM 300 words.
        7. KEYWORD DENSITY: Use the primary keyword naturally, maximum 6-7 times per 1000 words across the whole article. Prefer LSI synonyms and semantic variants over repeating the exact phrase.
        8. ANTI-FLUFF: Every paragraph must add new information. Do not restate the heading in different words. Do not pad.
        9. OUTBOUND AUTHORITY: If relevant to techniques or health (e.g. nail care, skin/hair safety), include a natural link to an authoritative real domain (e.g. aad.org).
        
        CONTEXT (Already written):
        {context}
        
        RETURN ONLY VALID JSON:
        {{
          "text": "The full section content (DO NOT repeat the heading here. Use HTML for lists/tables if requested)",
          "image_metadata": {{
            "prompt": "{'A detailed 4:5 image prompt. Vibrant, high-contrast, edge-to-edge photography.' if has_img else 'NONE'}",
            "alt_text": "{alt_text_instruction}"
          }}
        }}
        """
        return self._call_gemini_json(prompt, label=f"Section: {section['heading'][:30]}")

    def build_elite_html(self, data: Dict[str, Any]) -> str:
        """Converts elite data to WordPress blocks with rich formatting support."""
        html = f"<!-- wp:paragraph -->\n<p>{data['introduction']}</p>\n<!-- /wp:paragraph -->\n\n"
        
        for section in data["sections"]:
            html += f"<!-- wp:heading -->\n<h2>{section['heading']}</h2>\n<!-- /wp:heading -->\n\n"
            
            # Handle Image Placeholder if it exists
            if section.get("image_prompt") and section["image_prompt"] != "NONE":
                html += f"<!-- IMAGE_PLACEHOLDER_{section['heading']} -->\n\n"
            
            content = section['content']
            # Basic block conversion for lists/tables
            if "<ul" in content or "<ol" in content:
                html += f"<!-- wp:html -->\n{content}\n<!-- /wp:html -->\n\n"
            elif "<table" in content:
                html += f"<!-- wp:html -->\n{content}\n<!-- /wp:html -->\n\n"
            else:
                # Split paragraphs and wrap in wp:paragraph
                paragraphs = content.split('\n\n')
                for p in paragraphs:
                    if p.strip():
                        html += f"<!-- wp:paragraph -->\n<p>{p.strip()}</p>\n<!-- /wp:paragraph -->\n\n"

        html += f"<!-- wp:paragraph -->\n<p>{data['conclusion']}</p>\n<!-- /wp:paragraph -->"

        # FAQPage schema: the outline prompt already designates FAQ-format sections,
        # but no structured data was ever emitted. Build one Question per FAQ section.
        faq_entities = []
        for section in data.get("sections", []):
            if section.get("preferred_format") == "faq":
                answer = unescape(re.sub(r"<[^>]+>", " ", section.get("content", "")))
                answer = re.sub(r"\s+", " ", answer).strip()
                if len(answer) >= 40:
                    faq_entities.append({
                        "@type": "Question",
                        "name": section.get("heading", ""),
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": answer[:2000]
                        }
                    })
        if faq_entities:
            faq_schema = {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": faq_entities
            }
            html += "\n<script type=\"application/ld+json\">" + json.dumps(faq_schema, ensure_ascii=False) + "</script>\n"

        return html
