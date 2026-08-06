# Phase 5.6.1 — Market Value Authority

## Root cause

Random, Live, Seller Radar, long-term scoring and AI already read:

```text
Market Data Import → Market Value (£) → column H
```

The error was upstream: the daily market updater preferred Cardmarket
`trendPrice` for Normal cards. A broad trend value could therefore replace the
more specific TCGplayer variant market price.

## Corrected hierarchy

```text
Verified PriceCharting/manual override
        ↓
TCGplayer exact-variant market
        ↓
Cardmarket exact-variant trend fallback
```

Cardmarket is no longer the default Normal-card source.

## Market Data Import

Column H remains authoritative. New audit columns show:

```text
Card ID
Base Imported Value (£)
Base Imported Source
Override Value (£)
Override Source
Price Status
Last Synced
```

Price Status includes:

```text
TCGPLAYER PRIMARY
CARDMARKET FALLBACK
PRICECHARTING OVERRIDE
VERIFIED OVERRIDE
UNVERIFIED
```

## Market Price Controls

A new worksheet stores exact card-ID and variant overrides.

Required fields:

```text
Enabled = YES
Card ID
Variant
Override Market Value (£)
Override Source
```

For a manually checked PriceCharting value:

```text
Override Source = PriceCharting
Source URL = the exact PriceCharting card page
```

Run:

```text
applyMarketPriceControls.bat
```

The override then becomes column H and is used by every analysis mode.

## Official PriceCharting API

PriceCharting's official API is optional and requires its Legendary
subscription.

Setup:

```text
configurePriceCharting.bat
```

For selected control rows, set:

```text
Enabled = YES
Auto Update = YES
```

Then run:

```text
updatePriceChartingControls.bat
applyMarketPriceControls.bat
```

The integration imports `loose-price`, which PriceCharting defines as the
ungraded-card value, and converts it from USD to GBP.

The software does not scrape or bypass PriceCharting's paid API.

## Installation

1. Extract the add-on.
2. Copy all files into the main `PokemonCardTrading` folder.
3. Replace existing files.
4. Close Excel.
5. Run:

```text
install-phase5.6.1-market-value-authority.bat
```

6. Rerun Random, Live and Seller Radar so active opportunities use the
corrected values.

## Daily updates

Future runs of:

```text
update-pokemon-market-daily.bat
```

preserve and apply `Market Price Controls` automatically.
