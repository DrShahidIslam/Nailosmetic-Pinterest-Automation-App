import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

def mock_classification_test():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEYS").split(",")[0]
    client = genai.Client(api_key=api_key)
    
    test_cases = [
        {"topic": "elegant updo hairstyles", "niche": "hair_beauty", "expected": ["hair_aesthetics", "beauty_skincare"]},
        {"topic": "spring bar outfit ideas", "niche": "fashion_style", "expected": ["fashion_style"]},
        {"topic": "japanese nail designs", "niche": "nails", "expected": ["aesthetic_nail_art", "chrome_glazed", "minimalist_clean", "spring_trends", "summer_vacation"]}
    ]
    
    print("\n--- Pinterest Board Allotment (Gemini Mock Test) ---")
    
    for case in test_cases:
        prompt = f"""You are a Pinterest expert. Classify the following topic into one of these categories: {', '.join(case['expected'])}. 
        Topic: {case['topic']}
        Return ONLY the category name."""
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        result = response.text.strip().lower()
        print(f"Topic: {case['topic']} | Bot Choice: {result} | Result: {'✅' if any(ex in result for ex in case['expected']) else '❌'}")

if __name__ == "__main__":
    mock_classification_test()
