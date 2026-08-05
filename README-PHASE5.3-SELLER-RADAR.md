# Phase 5.3 — eBay Seller Radar

## Launcher

```text
sellerRadar.bat
```

The BAT file prompts for:

```text
Exact eBay seller username
Maximum active listings to scan [50]
```

The default listing cap is 50. The supported range is 1–1,000.

## What it does

1. Searches the named seller's active eBay listings using a broad `pokemon`
   search and the official seller filter.
2. Includes auctions and Buy It Now listings.
3. Pages through results when more than 200 listings are requested.
4. Matches listing titles against the priced local Pokémon card database.
5. Requires high-confidence card-name and card-number evidence.
6. Evaluates auction and Buy It Now scenarios separately.
7. Calculates delivered cost, market ratios, target cost and maximum bid.
8. Retrieves detailed condition data for actionable listings.
9. Colour-codes financial decisions and condition warnings independently.
10. Adds GREEN listings to the existing personal eBay Watchlist integration.
11. Creates or refreshes a seller-specific worksheet.
12. Shows unmatched/excluded listings in a manual-review section on the same
    worksheet.

## Seller worksheet

The sheet is named approximately:

```text
Seller - username
```

Excel's 31-character worksheet limit is handled automatically. Long usernames
receive a stable short hash so repeat scans refresh the same tab.

The result table includes:

- GREEN / AMBER / RED financial decision;
- separate Bid and Buy It Now decisions;
- current bid and fixed price;
- postage and delivered prices;
- market value and market percentages;
- direct listing, reference card image, active searches and sold comparisons;
- target delivered price;
- maximum bid and bid headroom;
- seller feedback;
- detailed condition and actual condition-cell colour;
- match confidence;
- status dropdown and notes.

The link columns are positioned immediately after the market-ratio columns.

## Unmatched section

The bottom of the same seller worksheet lists fetched listings that could not be
safely priced, including:

- lots, bundles, graded cards and excluded product types;
- vague listings without a reliable card number;
- listings that do not map to a priced English card variant.

The system does not guess when identification is ambiguous.

## Existing settings reused

Seller Radar reads the current Random Range Sniper controls for:

- target purchase ratio;
- seller feedback threshold;
- sniping window used for auction recommendations.

The Random Sniper's maximum-postage filter is deliberately ignored so that the
seller worksheet displays all safely identified listings.

## Re-running a seller

Running the same username again refreshes that seller's existing worksheet.

Manual `Status` selections are preserved by eBay Item ID where possible.

## Installation

1. Extract the add-on ZIP.
2. Copy all extracted files into the existing scanner folder.
3. Run:

```text
install-seller-radar-addon.bat
```

4. Close Excel and run:

```text
sellerRadar.bat
```

## Optional environment controls

```text
SELLER_RADAR_QUERY=pokemon
SELLER_RADAR_MAX_CONDITION_CHECKS=50
```

The normal `.env` eBay Production credentials, marketplace settings and
Watchlist settings are reused.
