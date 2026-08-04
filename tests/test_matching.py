import unittest
from app.models import PriceRecord
from app.price_catalog import PriceCatalog
class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.catalog=PriceCatalog([
          PriceRecord("Dark Jolteon","Team Rocket","38/82","Normal","English","Near Mint",8.59,"test",""),
          PriceRecord("Gardevoir","Legendary Treasures","RC10/RC25","Holo","English","Near Mint",13.56,"test","")
        ])
    def test_exact_number(self):
        m=self.catalog.match("Dark Jolteon 38/82 Team Rocket Pokemon Card")
        self.assertGreaterEqual(m.confidence,.8); self.assertEqual(m.market_value,8.59)
    def test_rc(self):
        m=self.catalog.match("Gardevoir RC10 RC25 Radiant Collection")
        self.assertGreater(m.confidence,.7)
    def test_unmatched(self):
        self.assertEqual(self.catalog.match("Random binder").display_name,"UNMATCHED")
if __name__=="__main__": unittest.main()
