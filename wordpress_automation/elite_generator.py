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
        Structure a 1500-word comprehensive blog guide about: "{topic}".
        
        ENTITIES TO INCLUDE: {entities}
        
        Plan 8-10 distinct H2/H3 sections that cover the topic from beginner to advanced.
        
        RETURN ONLY VALID JSON:
        {{
          "introduction": "A summary of the article's hook",
          "seo_description": "Meta description (max 155 chars)",
          "meta_title": "SEO Title (max 60 chars)",
          "slug": "url-slug-using-3-5-keywords-only",
          "sections": [
            {{
              "heading": "Clear heading title",
              "goal": "What this section should cover (150-200 words worth of depth)",
              "visual_idea": "Describe a relevant image idea"
            }}
          ],
          "conclusion": "Summary goal"
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
        Write a 150-250 word section for the article "{topic}".
        SECTION HEADING: "{section['heading']}"
        SECTION GOAL: "{section['goal']}"
        
        STRICT HUMAN-WRITING RULES:
        1. READABILITY: Use an 8th-grade reading level. Direct, conversational, clear.
        2. NO DASHES: NEVER use em-dashes (—) or en-dashes (–).
        3. NO AI-ISMS: Avoid 'In the tapestry of', 'delve into', 'it is important to note', 'ever-evolving'.
        4. AEO: If there is a direct question or clear concept, answer it directly in the first 2 sentences.
        5. SENTENCE VARIETY: Use short and long sentences.
        
        CONTEXT (Already written):
        {context}
        
        RETURN ONLY VALID JSON:
        {{
          "text": "The full section text",
          "image_prompt": "A detailed 4:5 image prompt for this section showing a realistic subject related to the heading."
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
        """Converts elite data to WordPress blocks."""
        # Simplified for now, we can add Kadence blocks later if needed
        html = f"<!-- wp:paragraph -->\n<p>{data['introduction']}</p>\n<!-- /wp:paragraph -->\n\n"
        
        for section in data["sections"]:
            html += f"<!-- wp:heading -->\n<h2>{section['heading']}</h2>\n<!-- /wp:heading -->\n\n"
            # Placeholder for Image
            html += f"<!-- IMAGE_PLACEHOLDER_{section['heading']} -->\n\n"
            html += f"<!-- wp:paragraph -->\n<p>{section['content']}</p>\n<!-- /wp:paragraph -->\n\n"

        html += f"<!-- wp:paragraph -->\n<p>{data['conclusion']}</p>\n<!-- /wp:paragraph -->"
        return html
