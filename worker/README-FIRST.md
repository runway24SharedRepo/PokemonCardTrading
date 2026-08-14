# PokéBid Worker — all-price title-match policy

This replacement changes the Worker used by
`run-ebay-watchlist-automation.bat`.

## New rule

- Price, delivery and the old target amount are ignored.
- Auctions, Buy It Now and Best Offer listings are eligible.
- A listing is added only once.
- The required Pokémon name must occur as complete consecutive words in the
  listing title.
- If the Saved Search label ends in a card number, that number must also occur
  as a distinct title token. `58` therefore does not match `158`.
- An overpriced matching listing is still added, allowing seller offers and
  counteroffers.

Example Saved Search label:

```text
Pikachu 58 - target £12.50
```

The target suffix remains accepted for compatibility but is not used. A title
such as `Pokémon Base Set Pikachu 58/102 NM` matches; `Raichu 58` and
`Pikachu 158` do not.

## Update the existing Worker

1. Back up the current Worker folder.
2. Copy this package over that folder.
3. In `wrangler.toml`, keep your existing Worker `name` and paste your existing
   D1 `database_id`.
4. Do not put credentials in source files. Configure the application secrets:

```text
EBAY_CLIENT_ID
EBAY_CLIENT_SECRET
POKEBID_API_KEY
```

For eBay user access, configure **one** of these alternatives:

```text
EBAY_AUTH_TOKEN       preferred for the long-lived Auth'n'Auth token shown by
                      the eBay Developer portal
EBAY_REFRESH_TOKEN    OAuth refresh-token alternative
```

When `EBAY_AUTH_TOKEN` exists, it takes precedence and
`EBAY_REFRESH_TOKEN` is not required. Set it with:

```text
npx wrangler secret put EBAY_AUTH_TOKEN
```

Paste the Production token copied from **User Tokens (eBay Sign-in)** with
**Auth'n'Auth** selected. Do not paste it into the BAT or source files.

5. Run:

```text
npm install
npx wrangler d1 execute pokebid-ebay-automation --remote --file=schema.sql
npm test
npx wrangler deploy
```

Running `schema.sql` is non-destructive. It creates separate `name_match_v2`
tables, leaving the earlier price-filtered records untouched. The new policy
starts its own deduplication history, so the first scan may encounter listings
seen by the old Worker. On that first scan, up to the 50 newest results from
each eligible Saved Search can be evaluated and matching titles can be added;
eBay safely keeps an already-watched item watched.

## Activate and test

Run the existing:

```text
run-ebay-watchlist-automation.bat
```

It synchronises Saved Searches, enables the two-minute schedule and queues an
immediate scan. No change to the BAT login is required.

The `/health` response and `/api/status` now report:

```text
name-and-number; all prices
```

## Important

This Worker is the only eBay Watchlist writer. The spreadsheet Live, Random
and Custom scanners should remain on Phase 5.7.6/5.8 and do not write to the
Watchlist.
