import os
import json
import unittest
from main import app, calculate_scores, parse_price, parse_card

class TestNYCHousingConcierge(unittest.TestCase):
    
    def setUp(self):
        self.app = app
        self.client = app.test_client()
        self.fallback_path = os.path.join(os.path.dirname(__file__), "data", "zillow_fallback.json")
        
        # Load sample listings for test isolation
        with open(self.fallback_path, "r", encoding="utf-8") as f:
            self.listings = json.load(f).get("listings", [])

    def test_fallback_file_exists(self):
        self.assertTrue(os.path.exists(self.fallback_path), "Zillow fallback file should exist under data/")

    def test_parse_price(self):
        self.assertEqual(parse_price("$2,450/mo"), 2450)
        self.assertEqual(parse_price("From $1,800"), 1800)
        self.assertEqual(parse_price("Price: $3,000"), 3000)
        self.assertIsNone(parse_price("Contact for Price"))

    def test_scoring_budget(self):
        # Create a profile with strict budget $2000
        profile = {
            "budget": 2000.0,
            "needs_transit": True,
            "lifestyle": "space",
            "has_pets": False,
            "elevator_only": False,
            "borough": "all",
            "work_location": "Midtown Manhattan"
        }
        
        scored = calculate_scores(self.listings, profile)
        
        # All returned listings should be relatively close to the budget
        for listing in scored:
            price = listing.get("price_per_month")
            self.assertIsNotNone(price)
            # Budget score should be 100 for <= 2000, or scaled down if under 2300
            if price <= 2000:
                self.assertEqual(listing["breakdown"]["budget"], 100.0)
            else:
                self.assertLess(listing["breakdown"]["budget"], 100.0)

    def test_scoring_borough_match(self):
        profile = {
            "budget": 2000.0,
            "needs_transit": True,
            "lifestyle": "space",
            "has_pets": False,
            "elevator_only": False,
            "borough": "Queens",
            "work_location": "Midtown Manhattan"
        }
        
        scored = calculate_scores(self.listings, profile)
        
        for listing in scored:
            addr = listing["address"].lower()
            borough_score = listing["breakdown"]["borough"]
            if "queens" in addr or "astoria" in addr or "rego park" in addr or "flushing" in addr or "jamaica" in addr:
                self.assertEqual(borough_score, 100.0)
            else:
                self.assertEqual(borough_score, 15.0)

    def test_scoring_elevator_only(self):
        profile_no_elevator = {
            "budget": 2500.0,
            "needs_transit": True,
            "lifestyle": "space",
            "has_pets": False,
            "elevator_only": False,
            "borough": "all",
            "work_location": "Midtown Manhattan"
        }
        
        profile_elevator = {
            "budget": 2500.0,
            "needs_transit": True,
            "lifestyle": "space",
            "has_pets": False,
            "elevator_only": True,
            "borough": "all",
            "work_location": "Midtown"
        }
        
        scored_no_elevator = calculate_scores(self.listings, profile_no_elevator)
        scored_elevator = calculate_scores(self.listings, profile_elevator)

        # Check elevator score differences
        for listing in scored_no_elevator:
            self.assertEqual(listing["breakdown"]["elevator"], 100.0)
            
        for listing in scored_elevator:
            if listing["is_elevator"]:
                self.assertEqual(listing["breakdown"]["elevator"], 100.0)
            else:
                self.assertEqual(listing["breakdown"]["elevator"], 30.0)

    def test_api_match_endpoint(self):
        payload = {
            "budget": 2000,
            "needs_transit": True,
            "lifestyle": "quiet",
            "has_pets": True,
            "elevator_only": False,
            "borough": "all",
            "work_location": "Rego Park"
        }
        
        response = self.client.post("/api/match", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertTrue("concierge_report" in data)
        self.assertTrue(len(data["matches"]) > 0)
        
        # High scoring listing should be first
        self.assertTrue(data["matches"][0]["overall_score"] >= data["matches"][-1]["overall_score"])

if __name__ == "__main__":
    unittest.main()
