Phase 5.3.1 Seller Radar hotfix

Problem:
  KeyError: 'location_country'

Cause:
  The existing random-sniper-config.json uses:
    item_location_country

  The initial Seller Radar client expected:
    location_country

Installation:
  1. Extract this ZIP.
  2. Copy seller_radar_client.py and install-seller-radar-hotfix.bat
     into the main PokemonCardTrading scanner folder.
  3. Replace seller_radar_client.py when Windows asks.
  4. Run install-seller-radar-hotfix.bat.
  5. Close Excel and run sellerRadar.bat again.

The hotfix accepts both configuration names and defaults to GB.
No spreadsheet data, credentials, market database or settings are changed.
