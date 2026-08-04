# Phase 4.3 — GREEN Seller Expansion and Condition Intelligence

## Existing workflow retained

There is no new operating scanner BAT.

Continue using:

```text
run-random-range-sniper.bat
```

The only new BAT is the one-time upgrade installer:

```text
install-phase4.3-upgrade.bat
```

## GREEN seller expansion

After the normal random scan:

1. The scanner finds unique sellers attached to GREEN results.
2. It searches those sellers' other Pokémon listings through the eBay Browse
   API `sellers` filter.
3. It matches individual-card titles against the local full card database.
4. It evaluates prices using the same Bid and Buy It Now rules.
5. GREEN/AMBER discoveries are inserted directly beneath the first GREEN row
   from that seller in Random Snipe Queue.

Seller discoveries are marked:

```text
↳ SAME SELLER
```

They are not recursively expanded.

### Controls

The Random Range Sniper tab contains:

```text
Expand GREEN sellers
Maximum GREEN sellers
Seller listings to inspect
Opportunities per seller
```

Recommended defaults:

```text
YES
5
100
5
```

## Independent condition assessment

The financial and condition decisions are deliberately independent.

Example:

```text
Buy Now Decision: GREEN
Condition Flag: RED
Condition: Ungraded | Heavily Played (Poor)
```

The price remains financially attractive, but the RED condition cell warns that
the card photographs must be inspected before purchase.

### Condition colours

- GREEN: Near Mint/fresh-pack wording
- AMBER: Lightly Played, Moderately Played, wear or ungraded without detail
- RED: Poor, Heavily Played, damaged, crease, bent, water damage and similar
- UNKNOWN: no useful condition information

The actual Condition and Condition Flag cells are filled with the corresponding
Excel colour.

## API behaviour

The ordinary eBay search returns a broad condition label. Phase 4.3 calls the
Browse getItem endpoint for financially GREEN/AMBER matches to retrieve the
seller's detailed condition description and structured trading-card condition
descriptors where available.

This creates additional API calls, shown in Latest Run Summary as:

```text
GREEN sellers inspected
Seller opportunities added
Detailed condition checks
Total eBay API calls
```
