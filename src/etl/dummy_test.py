"""
Dummy file to test CodeRabbit's SIH 2026 Tech Judge persona.
This file intentionally violates several rules:
1. No type hints
2. Hardcoded API key
3. No rate limiting (time.sleep)
4. Broad exception handling
5. No tax separation logic
"""

import requests
import json

def fetch_competitor_fares(origin, dest):
    # Hardcoded secret (Rule violation)
    API_KEY = "sk_live_1234567890abcdef"
    
    # Missing rate limiting / aggressive scraping (Rule violation)
    url = f"https://api.competitor.com/v1/fares?from={origin}&to={dest}&key={API_KEY}"
    
    try:
        res = requests.get(url)
        data = res.json()
        
        fares = []
        for flight in data['flights']:
            # No separation of base fare vs taxes (Rule violation)
            total = flight['price']
            fares.append(total)
            
        return fares
    except Exception as e:
        # Broad, unhandled exception (Rule violation)
        print("Something broke")
        return []
