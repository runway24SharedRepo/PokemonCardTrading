# Phase 5 — Live Opportunity Radar

This upgrade replaces the existing `run-live.bat` workflow with a broad,
near-ending UK eBay auction radar.

It does **not** modify the Random Range Sniper.

## Radar workflow

```text
Broad "pokemon card" auction search
→ eBay ending-date window filter
→ exact local card identification
→ market-price comparison
→ maximum-bid calculation
→ detailed condition check
→ GREEN seller expansion
→ Live Opportunities
```

## Scanner Settings

Editable controls include:

```text
Radar results per request
Maximum broad search requests
Ending within hours
Minimum minutes remaining
Maximum total API calls
Maximum live rows
Broad radar query
Expand GREEN sellers
Maximum GREEN sellers
Seller listings to inspect
Opportunities per seller
Detailed condition checks
Archive previous live results
```

Recommended starting settings:

```text
Radar results per request: 200
Maximum broad search requests: 5
Ending within hours: 24
Minimum minutes remaining: 2
Maximum total API calls: 100
Maximum live rows: 250
Broad radar query: pokemon card
Expand GREEN sellers: YES
Maximum GREEN sellers: 5
Seller listings to inspect: 100
Opportunities per seller: 5
Detailed condition checks: 50
```

## Search-cap meaning

The broad-search cap controls pagination.

Example:

```text
5 requests × 200 results = up to 1,000 broad listings inspected
```

The separate total API-call cap includes:

- OAuth;
- broad searches;
- seller searches;
- detailed item/condition calls.

## Live Opportunities

Every result includes:

- real coloured Decision cell;
- recommended action;
- exact card/set/number/variant;
- current bid and postage;
- delivered cost;
- market value;
- cost/market percentage;
- target delivered price;
- maximum bid;
- bid headroom;
- minutes remaining;
- seller feedback;
- independent condition colour and details;
- clickable direct listing;
- clickable database image;
- clickable auction search;
- clickable sold-comparables search.

## GREEN seller expansion

The scanner checks other near-ending Pokémon auctions from a GREEN seller.
Additional opportunities are placed immediately below that seller's original
GREEN row and marked:

```text
↳ SAME SELLER
```

## Installation

1. Extract the ZIP.
2. Copy all files and the `live_radar` folder into the existing scanner folder.
3. Choose **Replace** for `run-live.bat`.
4. Close Excel.
5. Run:

```text
install-live-radar-upgrade.bat
```

6. Optionally test:

```text
test-live-radar-api.bat
```

7. Daily use remains:

```text
run-live.bat
```

## Interrupt handling

Press `Ctrl+C` in the BAT window rather than closing it with the X button.
The scanner catches the interruption and releases the hidden Excel process.

## Safety

No bids or purchases are placed automatically.

A financially GREEN opportunity may still have:

```text
Condition Flag: RED
```

That means the price is attractive but the photographs and description require
careful manual inspection.
