POKEBID - EBAY SAVED SEARCH TO WATCHLIST AUTOMATION
==================================================

START
-----
Double-click:

    run-ebay-watchlist-automation.bat

On the first run, enter the same two values used by the Automation panel in
PokeBid-UK-Mobile(1)(1).html:

1. Worker HTTPS address
2. Separate PokéBid dashboard key

Do not enter an eBay client secret or eBay refresh token into the BAT.
The eBay Auth'n'Auth token also belongs only in the Cloudflare Worker secret
named EBAY_AUTH_TOKEN.

WHAT IT DOES
------------
- Loads all eligible eBay Saved Searches whose label contains a delivered
  target, for example: Pikachu 58 - target £12.50
- Enables the Worker's two-minute scheduled automation.
- Queues an immediate first scan.
- Displays a status summary every two minutes.
- New listings are deduplicated and added when the title contains the required
  Pokemon name and card number.
- Matches remain grouped under the associated per-card virtual list in
  PokéBid.

The target amount remains in the Saved Search label for compatibility, but it
is not compared with item price or delivery. Matching listings at every price
are added, allowing seller offers and counteroffers. The Worker is the
automation engine, so it continues operating when the BAT window or computer
is closed.

IMPORTANT EBAY LIMITATION
-------------------------
The public eBay API can add an item to the main Watchlist, but it cannot add an
item to an arbitrary named custom eBay List. PokéBid therefore preserves the
card-by-card grouping in its own Automation view.

LOGIN RESET
-----------
To change the Worker address or dashboard key, run:

    reset-ebay-watchlist-automation-login.bat

The dashboard key is stored using Windows user encryption. It can only be
decrypted by the same Windows account on the same PC.

LOG
---
The monitor log is saved at:

    logs\ebay-watchlist-automation.log

OPTIONAL ONE-SHOT TEST
----------------------
From Command Prompt:

    run-ebay-watchlist-automation.bat -Once

This connects, synchronises the saved searches, enables automation, queues one
scan, prints status, and exits. The cloud schedule remains enabled.
