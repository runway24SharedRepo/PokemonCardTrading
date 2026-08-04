# Phase 4.2 — Bid vs Buy It Now Analysis

## Decision colours

The following cells now receive real Excel fill colours after every scan:

- overall Decision;
- Bid Decision;
- Buy Now Decision;
- Best Decision on Random Range Sniper;
- copied GREEN decisions in the legacy Snipe Queue.

Colour scheme:

- GREEN: pale-green fill and dark-green text;
- AMBER: pale-amber fill and dark-amber text;
- RED: pale-red fill and dark-red text;
- N/A: grey.

## Correct eBay price fields

Phase 4.2 reads:

- `currentBidPrice` for the current auction bid;
- `price` for a FIXED_PRICE / Buy It Now option;
- `buyingOptions` to classify AUCTION, BUY IT NOW, or both.

The previous fallback could display the generic eBay price as Current Bid. That
has been corrected.

## Separate scenarios

Random Snipe Results and Random Snipe Queue now include:

- Listing Type;
- Current Bid;
- Buy It Now Price;
- Bid Delivered Cost;
- Buy Now Delivered Cost;
- Bid / Market;
- Buy Now / Market;
- Maximum Bid;
- Bid Headroom;
- Buy Now Headroom;
- Bid Decision;
- Buy Now Decision;
- Recommended Action.

The overall Decision is the strongest available scenario, while Recommended
Action explains whether to BID / SNIPE, BUY NOW, REVIEW, WATCH, or SKIP.

## Queue behaviour

Random Snipe Queue contains:

- auction scenarios ending inside the configured ending window;
- GREEN or AMBER Buy It Now deals, regardless of ending time, because they can
  be purchased immediately.

The legacy Snipe Queue remains auction-shaped, so only GREEN auction scenarios
are copied there.

## Install

1. Extract the upgrade ZIP.
2. Copy all files and folders into the current scanner folder.
3. Choose Replace when Windows asks.
4. Close Excel.
5. Run `install-phase4.2-upgrade.bat`.
6. Run `run-random-range-sniper.bat`.
