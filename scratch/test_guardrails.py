def validate_and_fix_category(title: str, current_category: str, chosen_niche: str) -> str:
    """
    Surgically validates and fixes the category based on programmatic rules.
    Prevents 'authority' content (Fashion/Hair/Home) from leaking into Nail categories.
    Ensures 'nail' content explicitly uses nail subcategories.
    """
    title_lower = title.lower()
    
    # Define keywords and exclusions
    nail_exclusion = ["nail", "mani", "polish", "pedi", "acrylic"]
    
    fashion_keywords = ["outfit", "wear", "leggings", "fashion", "style guide", "wardrobe", "chic"]
    hair_keywords = ["hair", "updo", "curly", "braid", "hairstyles", "salon", "style", "blowout"]
    home_keywords = ["decor", "home", "garden", "patio", "living", "interior", "room", "kitchen"]

    # --- 1. Authority Niche Guardrails ---
    
    # Priority A: Check the actual chosen niche first (reduces false positives)
    if chosen_niche == "fashion_style":
        if any(k in title_lower for k in fashion_keywords) and not any(k in title_lower for k in nail_exclusion):
            return "Styles & Fashion"
            
    if chosen_niche == "hair_beauty":
        if any(k in title_lower for k in hair_keywords) and not any(k in title_lower for k in nail_exclusion):
            return "Hair & Beauty"
            
    if chosen_niche == "home_garden":
        if any(k in title_lower for k in home_keywords) and not any(k in title_lower for k in nail_exclusion):
            return "Home & Garden"

    # Priority B: Catch leaks from OTHER niches (the 'Janitor' logic)
    # We use stricter keywords here to avoid cross-niche false matches
    
    # Fashion Leak? (Must have "outfit" or "fashion" - "look" is too risky for general leaks)
    if any(k in title_lower for k in ["outfit", "fashion", "leggings"]) and not any(k in title_lower for k in nail_exclusion):
        print(f"   [GUARDRAIL] Detected Fashion leak in '{title}'. Forcing 'Styles & Fashion'.")
        return "Styles & Fashion"

    # Hair Leak? (Must have "hair" or "hairstyles")
    if any(k in title_lower for k in ["hair", "hairstyles", "updo"]) and not any(k in title_lower for k in nail_exclusion):
        print(f"   [GUARDRAIL] Detected Hair leak in '{title}'. Forcing 'Hair & Beauty'.")
        return "Hair & Beauty"

    # Home Leak?
    if any(k in title_lower for k in ["decor", "interior", "patio"]) and not any(k in title_lower for k in nail_exclusion):
        print(f"   [GUARDRAIL] Detected Home leak in '{title}'. Forcing 'Home & Garden'.")
        return "Home & Garden"

    # --- 2. Nail Subcategory Enforcement ---
    if chosen_niche == "nails":
        if current_category in ["Styles & Fashion", "Hair & Beauty", "Home & Garden", "Uncategorized"]:
            print(f"   [GUARDRAIL] Nail niche content found in '{current_category}'. Forcing 'Aesthetic & Art' fallback.")
            return "Aesthetic & Art"
            
    return current_category

def test_guardrails():
    print("\n--- Testing REFINED Category Guardrails ---")
    
    test_cases = [
        # Authority Leaks
        {
            "title": "25+ Chic Easter Outfit Ideas for Women: Your Ultimate Style Guide",
            "suggested": "Aesthetic & Art",
            "niche": "fashion_style",
            "expected": "Styles & Fashion"
        },
        {
            "title": "15 Stunning Updo hairstyles for a Red Carpet Look",
            "suggested": "Nails and Manicure",
            "niche": "hair_beauty",
            "expected": "Hair & Beauty" # This should PASS now because niche=hair_beauty
        },
        {
            "title": "Modern Minimalist Home Decor Trends for 2026",
            "suggested": "Minimalist & Clean Girl",
            "niche": "home_garden",
            "expected": "Home & Garden"
        },
        # Nail Protection
        {
            "title": "10 Minimalist Clean Girl Nail Looks for Spring",
            "suggested": "Minimalist & Clean Girl",
            "niche": "nails",
            "expected": "Minimalist & Clean Girl"
        },
        {
            "title": "Spring Pearl Mani: A Glossy Finish Look",
            "suggested": "Seasonal Trends",
            "niche": "nails",
            "expected": "Seasonal Trends"
        },
        # Nail Enforcement
        {
            "title": "Deep Velvet Blue Nail Art",
            "suggested": "Styles & Fashion",
            "niche": "nails",
            "expected": "Aesthetic & Art"
        }
    ]
    
    passed = 0
    for i, tc in enumerate(test_cases):
        result = validate_and_fix_category(tc["title"], tc["suggested"], tc["niche"])
        if result == tc["expected"]:
            print(f"PASS Case {i+1}: '{tc['title']}' -> {result}")
            passed += 1
        else:
            print(f"FAIL Case {i+1}: '{tc['title']}' -> GOT {result}, EXPECTED {tc['expected']}")

    print(f"\nAudit Result: {passed}/{len(test_cases)} tests passed.")

if __name__ == "__main__":
    test_guardrails()
