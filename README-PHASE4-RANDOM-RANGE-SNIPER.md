# Phase 4 — Random Range Sniper

This package adds a practical random-card discovery workflow to the existing
Pokémon Auction Scanner.

## New workbook sheets

### Random Range Sniper

Control panel and selected-card table.

Normal inputs:

- minimum market value;
- maximum market value;
- number of cards.

Advanced dropdowns include:

- Smart/Pure/Never-Scanned/Successful/Rising/Vintage/Modern selection;
- category and variant filters;
- one variant per card;
- repeat cooldown;
- replacement of cards with no auctions;
- Fast/Balanced/Deep search depth;
- target purchase ratio;
- auction ending window;
- seller-feedback threshold;
- postage ceiling;
- optional copying of GREEN results into the existing Snipe Queue.

### Random Snipe Results

One row per matched live eBay auction, including native clickable links for:

- the exact eBay listing;
- the active eBay UK auction search;
- completed/sold comparisons;
- the database card image.

### Random Snipe History

Append-only history used for:

- 14-day or other repeat avoidance;
- Never Scanned First;
- Previously Successful;
- run performance and zero-result analysis.

## Installation

Extract the ZIP and copy all files/folders into the scanner directory that
already contains:

```text
Pokemon-Auction-Scanner-Dashboard.xlsx
.env
.venv
run-sniping-live.bat
```

Close Excel and run:

```text
install-random-range-sniper.bat
```

The installer creates a timestamped workbook backup in `backups/`.

Then run:

```text
test-random-range-sniper-api.bat
```

## First live run

1. Open Excel.
2. Open **Random Range Sniper**.
3. Set:
   - Minimum market value;
   - Maximum market value;
   - Number of cards.
4. Save and close Excel.
5. Run:

```text
run-random-range-sniper.bat
```

6. Reopen Excel and review the new sheets.

## Reroll without using eBay calls

Use:

```text
reroll-random-cards-only.bat
```

This creates a fresh random card selection and clickable Active/Sold links but
does not call the Browse API.

## Default behaviour

The default profile is:

```text
£5–£40
20 cards
Smart Random
Pokémon only
Any variant
One variant per exact card
14-day cooldown
Replace no-result cards
Balanced search depth
75% target
Ends within 24 hours
98% feedback
Copy GREEN to Snipe Queue
```

## Search depth

- **Fast:** exact card query only.
- **Balanced:** exact plus simplified query.
- **Deep:** exact, simplified and broad-set query.

## Safety

The market values originate from the daily Cardmarket/TCGplayer reference
database. They are not guaranteed eBay sale values.

Before bidding, always confirm:

- exact set and card number;
- normal/holo/reverse/first-edition variant;
- language;
- front and back condition;
- authenticity;
- seller feedback;
- postage;
- Maximum Bid and bid headroom.

Never bid above the calculated Maximum Bid.
