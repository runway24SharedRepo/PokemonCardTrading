# Pokémon Full Card Database and Daily Market Updater

This add-on is designed to be copied into the existing Pokémon Auction
Scanner folder.

It does **not** replace the working eBay scanner.

## What it creates

Every successful run updates:

- **Market Data Import**
  - scanner-ready card/variant price rows in GBP;
- **Full Card Database**
  - one row for every English-language card returned by the Pokémon TCG API;
- **Market Price Changes**
  - movements compared with the previous successful run;
- **Market Update Summary**
  - refresh status, counts and FX rates;
- **Price Import Log**
  - an audit entry for the update.

It also creates:

```text
data/pokemon-card-market.sqlite
data/pokemon-card-database.csv
data/pokemon-card-market.csv
data/pokemon-card-price-changes.csv
data/pokemon-tcg-api-latest.json.gz
backups/
```

## Price sources

The Pokémon TCG API card object provides:

- TCGplayer prices in USD;
- Cardmarket prices in EUR;
- the source price-update date;
- purchase/source URLs.

The updater converts those values into GBP using daily Frankfurter reference
rates.

### Price selection

For the UK workflow:

- Cardmarket `trendPrice` is preferred for Normal cards;
- Cardmarket reverse-holo trend data is preferred for Reverse Holofoil;
- TCGplayer `market` fills Holofoil and first-edition variants;
- fallback fields are used only when the preferred field is missing.

These are market references, not guaranteed sale prices. Always confirm:

- exact set;
- card number;
- normal/holo/reverse variant;
- language;
- condition;
- authenticity;
- postage.

## Scope

The database is the complete **English catalogue covered by the Pokémon TCG
API**. It is not a complete worldwide Japanese/foreign-language database.

Cards without current price data remain visible in **Full Card Database**, but
they are not added to the scanner's active Market Data Import price rows.

## Installation

1. Extract this ZIP.
2. Copy all files and the `market_updater` folder into the existing scanner
   folder—the folder containing:

```text
Pokemon-Auction-Scanner-Dashboard.xlsx
run-sniping-live.bat
scanner.py
.env
.venv
```

3. Run:

```text
install-market-updater.bat
```

4. Run:

```text
test-pokemon-market-connection.bat
```

5. Close Excel and run:

```text
update-pokemon-market-daily.bat
```

## Optional free Pokémon TCG API key

The updater works without a key, but the unauthenticated API limit is slower.

A free key can be created at:

```text
https://dev.pokemontcg.io/
```

Add it to the existing scanner `.env` file:

```text
POKEMON_TCG_API_KEY=YOUR_API_KEY
```

Do not remove or change the existing eBay credential lines.

The updater sends the key only in the `X-Api-Key` request header.

## First run

The first successful run:

- downloads the complete catalogue;
- creates the baseline SQLite database;
- backs up the workbook;
- copies the original Market Data Import rows into
  **Market Data Manual Backup**;
- replaces Market Data Import with the full scanner-ready price database.

The first run normally shows zero price changes because it is creating the
baseline. Later runs compare against that baseline.

## Daily routine

```text
Close Excel
→ run update-pokemon-market-daily.bat
→ wait for Exit code 0
→ open Excel
→ run the eBay sniping scanner
```

The sniping scanner then uses the refreshed Market Data Import values.

## Important limitations

- The prices are source-updated references, not second-by-second live prices.
- Cardmarket values are converted from EUR.
- TCGplayer values are converted from USD.
- Exchange rates are reference rates, not card-payment exchange rates.
- eBay Browse API searches active listings; it is not a complete source of
  historical sold-price data.
- Exact UK eBay sold-price medians would require a separate licensed or
  manually collected sold-sales dataset.

## Troubleshooting

### Workbook cannot be updated

Close all Excel windows and retry.

### API is slow

Add the free `POKEMON_TCG_API_KEY` to `.env`.

### Workbook repair warning

The updater uses ordinary cells and does not add merged cells, macros,
ActiveX controls or Excel table objects.

A timestamped workbook copy is always placed in `backups/` before changes.
