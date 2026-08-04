from datetime import datetime,timedelta,timezone
def demo_items():
    now=datetime.now(timezone.utc)
    return [
      {"itemId":"DEMO-1","title":"Dark Jolteon 38/82 Team Rocket Pokemon card NM",
       "currentBidPrice":{"value":"4.20","currency":"GBP"},
       "shippingOptions":[{"shippingCost":{"value":"1.55","currency":"GBP"}}],
       "itemEndDate":(now+timedelta(hours=2)).isoformat().replace("+00:00","Z"),
       "bidCount":2,"condition":"Used",
       "seller":{"username":"demo_seller","feedbackPercentage":"99.8","feedbackScore":1240},
       "itemWebUrl":"https://www.ebay.co.uk/","image":{"imageUrl":""}},
      {"itemId":"DEMO-2","title":"Gardevoir RC10 RC25 Radiant Collection card near mint",
       "currentBidPrice":{"value":"8.50","currency":"GBP"},
       "shippingOptions":[{"shippingCost":{"value":"1.25","currency":"GBP"}}],
       "itemEndDate":(now+timedelta(hours=8)).isoformat().replace("+00:00","Z"),
       "bidCount":5,"condition":"Used",
       "seller":{"username":"demo_cards","feedbackPercentage":"100","feedbackScore":540},
       "itemWebUrl":"https://www.ebay.co.uk/","image":{"imageUrl":""}},
      {"itemId":"DEMO-3","title":"Old shiny Pokemon card no idea what set",
       "currentBidPrice":{"value":"12.00","currency":"GBP"},
       "shippingOptions":[],
       "itemEndDate":(now+timedelta(hours=5)).isoformat().replace("+00:00","Z"),
       "bidCount":1,"condition":"Used",
       "seller":{"username":"casual_demo","feedbackPercentage":"97.5","feedbackScore":12},
       "itemWebUrl":"https://www.ebay.co.uk/","image":{"imageUrl":""}}
    ]
