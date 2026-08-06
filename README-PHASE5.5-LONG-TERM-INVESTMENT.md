# Phase 5.5 — Long-Term Pokémon Investment Engine

Phase 5.5 changes the scanner from a pure discount finder into a long-term
collection-selection system. Financial GREEN/AMBER/RED decisions remain intact,
but each safely identified card also receives an independent long-term
assessment.

This is a decision-support model, not a promise of profit. Pokémon cards are
illiquid collectibles and can fall in value. The scarcity component is clearly
labelled **Scarcity Proxy** because the current package does not claim to know
the complete worldwide supply of a card.

## Modes upgraded

The long-term block is written to:

- Random Range Sniper selected cards;
- Random Snipe Results;
- Random Snipe Queue;
- Random Snipe History;
- legacy Snipe Queue;
- Live Opportunities;
- Opportunity Archive;
- every existing and future `Seller - ...` worksheet.

Within the same financial decision tier, Random, Live and Seller results now
prioritise stronger long-term scores before the previous short-term listing
score.

## Long-term columns

The following 15 columns are placed immediately after `PriceCharting`:

```text
Long-Term Score
Investment Tier
Long-Term Action
Demand Durability /25
Scarcity Proxy /20
Card Significance /15
Reprint Resistance /15
Condition Investment /10
Price Resilience /10
Acquisition Discount /5
Data Confidence
Portfolio Fit
Minimum Hold (Years)
Investment Thesis
Investment Risks
```

## 100-point model

Default weighting:

| Component | Maximum |
|---|---:|
| Demand durability | 25 |
| Scarcity proxy | 20 |
| Card significance | 15 |
| Reprint resistance | 15 |
| Condition investment quality | 10 |
| Price resilience | 10 |
| Acquisition discount | 5 |
| **Total** | **100** |

Entry price deliberately contributes only five points. A card cannot receive a
high investment rating merely because it is cheap.

## Investment tiers

```text
90–100  CORE ASSET
80–89   STRONG LONG-TERM BUY
70–79   SELECTIVE BUY
60–69   WATCH
45–59   SPECULATIVE
0–44    AVOID FOR LONG-TERM HOLD
```

Financial and long-term conclusions are independent. For example:

```text
Financial Decision: GREEN
Investment Tier: SPECULATIVE
```

means that the listing is cheap relative to the current reference market, but
the card's long-term evidence is weaker.

## New worksheets

### Investment Settings

Contains editable assumptions, thresholds and the iconic-Pokémon list used as
one demand-durability signal. Blue cells are user inputs. The weight total is
shown and should remain 100.

### Long-Term Targets

Card-specific manual research and overrides:

- component-score overrides;
- total-score override;
- desired maximum purchase ratio;
- target quantity;
- minimum holding period;
- investment thesis;
- risks;
- priority and notes.

A Card ID is the strongest matching key. Card name, set, number and variant are
also supported.

### Portfolio Vault

Records completed purchases and calculates:

- total acquisition cost;
- cost per copy;
- current reference value;
- unrealised gain;
- return percentage;
- long-term score and tier;
- review date based on the minimum hold period;
- portfolio action, thesis and risks;
- storage location and seller provenance.

The system does not generate automatic sell instructions merely because the
price rises.

### Price History

Each scanner mode stores one daily market snapshot per card and mode. It also
stores the best observed delivered price, ratio, condition flag, listing count,
seller and Item ID.

The Price Resilience score initially reports limited evidence. It becomes more
meaningful after at least three snapshots covering 30 days.

### Long-Term Dashboard

Shows:

- portfolio cost and current value;
- unrealised gain and return;
- holding and quantity counts;
- number of Core Assets and Strong Long-Term Buys;
- review/risk flags;
- top Pokémon and set concentrations;
- highest long-term scores seen in recent price history.

## Portfolio controls

The automatic `Portfolio Fit` warning checks:

- target quantity for the exact card;
- default maximum quantity per exact card;
- percentage of portfolio value concentrated in one Pokémon.

Possible outputs include:

```text
GOOD FIT / NEW POSITION
ADDS TO EXISTING POSITION
HOLDING TARGET REACHED
POKÉMON CONCENTRATION RISK
```

## Automatic refresh

Every successful Random, Live or Seller scan now:

1. assesses all matched cards;
2. ranks comparable financial opportunities using the long-term score;
3. writes long-term fields to the relevant result sheets;
4. appends daily Price History snapshots;
5. refreshes Portfolio Vault reference values and ratings;
6. refreshes the Long-Term Dashboard.

A separate launcher is included for refreshing the portfolio without using
eBay:

```text
refreshLongTermPortfolio.bat
```

## Installation

1. Close Excel completely.
2. Extract the Phase 5.5 add-on.
3. Copy all extracted files and folders into the main scanner folder.
4. Replace existing files when Windows asks.
5. Run:

```text
install-phase5.5-long-term-investment.bat
```

The installer creates a timestamped workbook backup, adds the five new
worksheets, inserts the 15-column investment block in all supported modes and
assesses existing rows.

Continue using the normal launchers:

```text
run-random-range-sniper.bat
run-live.bat
sellerRadar.bat
```

## Important interpretation notes

- `Scarcity Proxy` is based on age, rarity wording, promo/edition signals and
  similar metadata. It is not a complete population count.
- `Data Confidence` falls when release date, condition or price-history evidence
  is missing.
- Manual overrides in `Long-Term Targets` should be used when you have stronger
  external research.
- Near Mint wording and listing photographs do not guarantee a professional
  grading result.
- Market reference values are estimates, not guaranteed future sale prices.
