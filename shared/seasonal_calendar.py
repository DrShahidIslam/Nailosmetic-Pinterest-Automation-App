"""
Seasonal & Event Intelligence Engine
====================================
Maps the current date to high-demand seasonal planning windows on Pinterest.
Pinterest pinners plan 30 to 60 days in advance (the T-60 to T-30 lead-time rule).

This module dynamically scores and filters topics based on upcoming holidays,
festivities, and seasonal shifts.
"""

from datetime import datetime
from typing import Dict, List, Tuple, Any

# Definition of Seasonal Windows and their peak calendar targets
SEASONAL_WINDOWS = {
    # Late Summer / Early Fall transition (August - September)
    "fall_transition": {
        "active_months": [8, 9],
        "keywords": [
            "fall transition", "summer to fall", "pre fall", "late summer",
            "august september", "end of august", "back to school", "picture day",
            "fall colors", "fall preview", "transitional"
        ],
        "weight_multiplier": 3.0
    },
    # Fall / Autumn Aesthetics (September - November)
    "fall_autumn": {
        "active_months": [8, 9, 10, 11],
        "keywords": [
            "fall", "autumn", "fall aesthetic", "fall nails", "fall decor",
            "fall outfit", "fall hair", "fall style", "pumpkin spice", "cozy fall",
            "sweater weather", "fall mantle", "fall porch", "fall pedicure",
            "warm tones", "brown chrome", "burgundy", "tortoiseshell", "mocha"
        ],
        "weight_multiplier": 3.5
    },
    # Halloween & Spooky Season (September 1 - October 31)
    "halloween": {
        "active_months": [8, 9, 10],  # Searches surge heavily in late Aug/Sept/Oct
        "keywords": [
            "halloween", "spooky", "spooky season", "ghost", "witch", "pumpkin",
            "vampire", "venom", "goth", "gothic", "dark romance", "horror",
            "costume", "halloween decor", "halloween nails", "halloween makeup",
            "spooky cute", "creepy chic", "jack-o-lantern", "dollar tree halloween"
        ],
        "weight_multiplier": 4.0  # Extremely high search volume in Sept/Oct
    },
    # Thanksgiving & Harvest (September 15 - November 30)
    "thanksgiving": {
        "active_months": [9, 10, 11], # Starts planning in Sept/Oct, peaks in Nov
        "keywords": [
            "thanksgiving", "friendsgiving", "harvest", "turkey", "gratitude",
            "tablescape", "fall table", "dough bowl", "thanksgiving outfit",
            "thanksgiving dinner", "family dinner outfit", "thanksgiving nails",
            "autumn harvest", "fall centerpiece", "warm terracotta"
        ],
        "weight_multiplier": 3.0
    },
    # Winter, Christmas & Holiday Glam (September 25 - December 31)
    "holiday_winter": {
        "active_months": [9, 10, 11, 12], # Pinners start Christmas planning in Sept/Oct
        "keywords": [
            "christmas", "xmas", "holiday", "winter", "festive", "new year",
            "nye", "velvet", "emerald green", "ruby red", "holiday glam",
            "christmas tree", "winter decor", "holiday outfit", "holiday party",
            "cocktail dress", "winter nails", "christmas nails", "snowflake",
            "holiday bedding", "glitter", "winter style", "winter capsule"
        ],
        "weight_multiplier": 2.5 if 9 <= datetime.now().month <= 10 else 4.5
    },
    # Spring (Off-season in Sept/Oct/Nov/Dec)
    "spring": {
        "active_months": [1, 2, 3, 4, 5],
        "keywords": [
            "spring", "easter", "pastel", "bloom", "floral", "spring nails",
            "fresh spring", "spring style", "spring decor", "may nails", "april"
        ],
        "weight_multiplier": 0.1  # Suppressed during Q3/Q4
    },
    # Summer (Off-season in Sept/Oct/Nov/Dec)
    "summer": {
        "active_months": [4, 5, 6, 7, 8],
        "keywords": [
            "summer", "beach", "vacation", "neon", "tropical", "july 4th",
            "4th of july", "fourth of july", "summer nails", "summer outfit",
            "ocean wave", "pool day", "summer dress"
        ],
        "weight_multiplier": 0.1  # Suppressed during Q3/Q4
    }
}


def get_active_seasonal_themes(target_date: datetime = None) -> List[str]:
    """Return a list of currently active seasonal window keys based on month."""
    if target_date is None:
        target_date = datetime.now()
    
    current_month = target_date.month
    active_themes = []
    
    for theme, config in SEASONAL_WINDOWS.items():
        if current_month in config["active_months"] and config["weight_multiplier"] >= 1.0:
            active_themes.append(theme)
            
    return active_themes


def score_topic_seasonality(topic: str, target_date: datetime = None) -> Tuple[float, str]:
    """
    Score a topic based on how well it aligns with active upcoming seasonal events.
    Returns: (score_multiplier, matched_theme)
    """
    if target_date is None:
        target_date = datetime.now()
        
    current_month = target_date.month
    topic_lower = topic.lower()
    
    best_multiplier = 1.0
    matched_theme = "evergreen"
    
    for theme, config in SEASONAL_WINDOWS.items():
        is_month_active = current_month in config["active_months"]
        multiplier = config["weight_multiplier"]
        
        for kw in config["keywords"]:
            if kw in topic_lower:
                if is_month_active:
                    # In-season bonus
                    if multiplier > best_multiplier:
                        best_multiplier = multiplier
                        matched_theme = theme
                else:
                    # Off-season penalty (e.g. spring or summer topics in autumn)
                    if multiplier < best_multiplier:
                        best_multiplier = min(best_multiplier, 0.1)
                        matched_theme = f"off_season_{theme}"
                        
    return best_multiplier, matched_theme


def filter_and_prioritize_topics(
    available_topics: List[str],
    target_date: datetime = None,
    allow_off_season: bool = False
) -> List[Dict[str, Any]]:
    """
    Filter and rank a list of topic strings by their seasonal relevance and momentum.
    """
    scored = []
    for t in available_topics:
        multiplier, theme = score_topic_seasonality(t, target_date)
        if not allow_off_season and multiplier < 0.5:
            # Suppress completely off-season topics
            continue
        scored.append({
            "topic": t,
            "seasonal_multiplier": multiplier,
            "theme": theme
        })
        
    # Sort descending by multiplier
    scored.sort(key=lambda x: x["seasonal_multiplier"], reverse=True)
    return scored
