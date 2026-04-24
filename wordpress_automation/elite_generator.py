import json
import random
import re
from typing import List, Dict, Any, Optional
from google import genai
from dotenv import load_dotenv

load_dotenv()

class EliteGenerator:
    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]

    def _get_client(self, api_key):
        return genai.Client(api_key=api_key)

    def generate_elite_blog(self, topic_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main orchestration for elite long-form content.
        1. Outline
        2. Section-by-section drafting
        3. Humanization pass
        """
        topic = topic_data["topic"]
        print(f"🚀 Generating Elite Blog Article for: {topic}...")
        
        # Step 1: Generate Detailed Outline
        outline = self._generate_outline(topic, topic_data.get("entities", []))
        
        # Step 2: Generate Content for each section
        full_article = []
        for i, section in enumerate(outline["sections"]):
            print(f"   ✍️  Drafting Section {i+1}/{len(outline['sections'])}: {section['heading']}")
            draft = self._generate_section(topic, section, full_article)
            full_article.append({
                "heading": section["heading"],
                "content": draft["text"],
                "image_prompt": draft.get("image_prompt", "")
            })
            
        # Step 3: Meta and Final Wrap
        blog_data = {
            "title": topic,
            "introduction": outline["introduction"],
            "featured_image": outline.get("featured_image"),
            "sections": full_article,
            "conclusion": outline["conclusion"],
            "seo": {
                "title": outline.get("meta_title", f"{topic} | Nailosmetic"),
                "description": outline["seo_description"],
                "focus_keyword": topic_data["target_keywords"][0] if topic_data.get("target_keywords") else topic,
                "slug": outline.get("slug")
            }
        }
        
        return blog_data

    def _generate_outline(self, topic: str, entities: List[str]) -> Dict[str, Any]:
        prompt = f"""
        You are an Elite Content Architect for 'Nailosmetic'. 
        Structure a 1500-word comprehensive, authoritative blog guide about: "{topic}".
        
        GOALS:
        - SEO: High keyword density (natural), optimized H2/H3.
        - AEO (Answer Engine Optimization): Direct answers to likely user questions.
        - GEO (Generative Engine Optimization): Clear entities, semantic richness, and data-backed claims.
        - QUALITY: Provide unique value, pro-tips, and a luxurious brand voice.
        
        ENTITIES TO INCLUDE: {entities}
        
        STRUCTURE:
        - 7-9 distinct H2/H3 sections.
        - Total word count MUST exceed 1500 words.
        - EXACTLY 2 sections must be designated for in-content images.
        
        RETURN ONLY VALID JSON:
        {{
          "introduction": "A compelling 150-word hook that sets the stage",
          "seo_description": "Meta description (max 155 chars)",
          "meta_title": "SEO Title (max 60 chars)",
          "slug": "url-slug-using-3-5-keywords-only",
          "featured_image": {{
            "prompt": "A detailed 16:9 image prompt for the featured image",
            "alt_text": "Descriptive alt text"
          }},
          "sections": [
            {{
              "heading": "Clear heading title",
              "goal": "What this section should cover (Aim for 200-250 words depth)",
              "has_image": boolean,
              "preferred_format": "paragraph | list | table | faq"
            }}
          ],
          "conclusion": "Summary and final takeaway"
        }}
        """
        errors = []
        for key in self.api_keys:
            client = self._get_client(key)
            for model_name in self.models_to_try:
                try:
                    response = client.models.generate_content(model=model_name, contents=prompt)
                    import re
                    json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group(0))
                except Exception as e:
                    errors.append(f"{model_name}: {str(e)}")
                    continue
        raise Exception(f"Could not parse outline JSON. Errors: {errors[:2]}")

    def _generate_section(self, topic: str, section: Dict[str, Any], previous_sections: List[Dict]) -> Dict[str, Any]:
        # Context from previous sections to avoid repetition
        context = "\n".join([f"Previous section: {s['heading']}" for s in previous_sections])
        
        prompt = f"""
        You are a top-tier human author for 'Nailosmetic'. 
        Write a deep-dive, 200-300 word section for the article "{topic}".
        SECTION HEADING: "{section['heading']}"
        SECTION GOAL: "{section['goal']}"
        PREFERRED FORMAT: "{section['preferred_format']}"
        
        STRICT WRITING RULES:
        1. READABILITY: Conversational but premium.
        2. NO DASHES: NEVER use em-dashes (—) or en-dashes (–).
        3. NO AI-ISMS: Avoid 'In the tapestry of', 'delve into', 'unlocking the secrets'.
        4. AEO/GEO: Use clear, factual statements. If the format is 'faq', use Q&A structure.
        5. RICH FORMATTING: If format is 'list', use HTML <ul> or <ol>. If 'table', use HTML <table> with headers.
        6. LENGTH: Be verbose and detailed. Provide specific examples and pro-tips.
        
        CONTEXT (Already written):
        {context}
        
        RETURN ONLY VALID JSON:
        {{
          "text": "The full section content (use HTML for lists/tables if requested)",
          "image_prompt": "{'A detailed 4:5 image prompt for this section' if section.get('has_image') else 'NONE'}"
        }}
        """
        errors = []
        for key in self.api_keys:
            client = self._get_client(key)
            for model_name in self.models_to_try:
                try:
                    response = client.models.generate_content(model=model_name, contents=prompt)
                    import re
                    json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group(0))
                except Exception as e:
                    errors.append(f"{model_name}: {str(e)}")
                    continue
        raise Exception(f"Could not parse section JSON. Errors: {errors[:2]}")

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
        return html
