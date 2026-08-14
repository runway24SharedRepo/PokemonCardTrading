# PokéBid all-price Watchlist update

This package updates `run-ebay-watchlist-automation.bat` so that price and
delivery never reject a listing. A newly encountered listing is added to the
main eBay Watchlist when its title contains the saved card name and, when
present, its card number.

## Install in this order

1. Open `worker/README-FIRST.md` and deploy the Worker update. Keep your
   existing Worker name, D1 database ID and secrets.
2. Copy the contents of `windows/` into your existing Windows automation
   folder. Keep its existing `data/` directory so the saved Worker login is
   retained.
3. Replace your dashboard HTML with
   `PokeBid-UK-Mobile-all-price-watchlist.html` if you use the Automation view.
4. Double-click `run-ebay-watchlist-automation.bat`.

The BAT will print this policy after connecting:

```text
policy=name-and-number; all prices
```

If it prints `legacy or unknown`, the new Worker has not yet been deployed.

## Matching example

Saved Search label:

```text
Pikachu 58 - target £12.50
```

`Pokémon Base Set Pikachu 58/102 NM` is accepted at every price. `Raichu 58`
and `Pikachu 158` are rejected. The target suffix remains part of the label for
compatibility and dashboard display only.

## First scan

The replacement uses a separate deduplication history. Its first scan can
evaluate up to the 50 newest results for each eligible Saved Search and add all
matching titles. Later scans process only listings that history has not seen.

The spreadsheet Live, Random and Custom scanners remain read-only for the eBay
Watchlist; this Worker is the sole Watchlist writer.

For the Production eBay user shown under **User Tokens (eBay Sign-in)**, the
long-lived **Auth'n'Auth** token is supported directly as the Cloudflare secret
`EBAY_AUTH_TOKEN`; an OAuth refresh token is not required when that secret is
present.
