# Pokémon Auction Scanner — Phase 2

Phase 2 can be developed and tested before eBay approves the Production keyset.

## Added in Phase 2

- Exact card-number, set, variant and title parsing
- Confidence-based card matching
- Market Data Import worksheet
- Ambiguous-listing Review Queue
- Historical Opportunity Archive
- Consultation Dashboard
- SQLite response cache
- Retry/backoff for temporary API errors
- Safe handling when postage is unavailable
- HoloDex CSV normaliser
- Automated unit tests
- No automatic bidding or purchasing

## First test

1. Extract the ZIP to `C:\PokemonAuctionScanner`.
2. Run `install.bat`.
3. Close the Excel workbook.
4. Run `run-tests.bat`.
5. Run `run-demo.bat`.
6. Open the workbook and inspect **Scanner Dashboard**, **Live Opportunities**, **Review Queue**, and **Scanner Log**.

## Add prices without manual row editing

Run `import-prices.bat` and choose a HoloDex CSV. It creates `data\market-import.csv`.
For now, copy that generated table into the **Market Data Import** tab. The next phase will import it into Excel automatically during every run.

## When eBay approves the account

Rename `.env.example` to `.env`, place the Production Client ID and Client Secret there, close Excel, and run `run-live.bat`.

Never send or publish your Client Secret. The scanner only reads it locally.


## Phase 3 additions

- Automatic CSV market-price import on every run
- Persistent SQLite listing and search history
- Search effectiveness learning and effective-score ranking
- Strong-opportunity Notification Queue
- Automatic HTML consultation report
- Configurable output limits
- Windows Task Scheduler installation script
- Local history retention and cleanup
- Price import audit log

## Automatic operation

After live API validation, run `install-schedule.bat` once. Windows will run the scanner hourly.
The workbook must be closed during scheduled refreshes.

The latest browser-friendly report is written to:

`reports\latest-report.html`


## Phase 3.1 Windows test fix

The original history unit test used `NamedTemporaryFile`. Windows keeps that
temporary file locked, preventing SQLite from reopening it. Phase 3.1 uses a
temporary directory and an unlocked database path.

The message `Could not find platform independent libraries <prefix>` is normally
a Python installation/environment warning. If `python --version` works and the
remaining tests execute, it is separate from the SQLite test failure.

Run:

1. `run-database-test.bat`
2. `run-tests.bat`
3. `run-demo.bat`


## Phase 3.2 search links

- Buy and Sold links use eBay UK.
- Links prefer UK-located items.
- Buy links show auction listings ending soonest.
- Sold links show completed sold results.
- Both links update dynamically from the editable Pokémon-name cell.


## Phase 3.4 — Sniping Search System

New workbook tabs:

- **Sniping Search Library**: 100 ranked dynamic sniping searches with dropdown-based controls.
- **Snipe Queue**: scanner output for ending-soon actionable auctions.

Manual setup is limited to simple cells and dropdown menus. No macros, ActiveX
controls, form buttons, merged cells, or fragile Excel table metadata are used.

Offline test:

1. Close the workbook.
2. Run `run-sniping-demo.bat`.
3. Open the workbook.
4. Review **Snipe Queue** and **Scanner Log**.

After the eBay Production API is approved, use `run-sniping-live.bat`.
