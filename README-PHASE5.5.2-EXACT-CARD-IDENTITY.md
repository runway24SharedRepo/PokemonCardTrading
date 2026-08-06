# Phase 5.5.2 — Exact Pokémon Card Identity Matching

## Errors corrected

The previous substring comparison could treat any occurrence of a digit as the
candidate collector number.

```text
Candidate: Luxray 8
Listing:   Luxray 028/88
Old:       accepted
New:       collector-number conflict
```

```text
Candidate: Mawile 9
Listing:   Mawile VSTAR 071/195
Old:       accepted because 9 occurs in 195
New:       collector-number and card-form conflict
```

## New identity requirements

### Collector number

- the numerator in `028/88` identifies the card;
- the denominator is never used as the card number;
- leading zeroes are normalised, so `28` and `028` agree;
- `8` does not match `028/88`;
- `88` does not match the denominator;
- alphanumeric identifiers such as `XY41`, `TG06`, `GG70` and `SWSH020`
  require an exact token.

### Card name and form

Distinct forms are no longer interchangeable:

```text
Mawile
Mawile V
Mawile VSTAR
Mawile EX
Mawile GX
```

The same rule covers VMAX, BREAK, Prime, LV.X, V-UNION and Mega forms.

### Variant and edition

Explicit Reverse Holo, regular Holo, 1st Edition and Unlimited conflicts are
rejected.

### Set ambiguity

Set-name evidence is used to resolve cards with the same Pokémon and collector
number. When multiple sets or variants remain equally plausible, the listing
is discarded instead of guessed.

## Random-mode protection

Every result returned by an eBay Random search is now checked against the
complete card database before the selected candidate's market value is used.
A loosely related eBay search result cannot enter Random Results or Snipe Queue
under the wrong card identity.

## Installation

1. Extract the add-on.
2. Copy all files and folders into the main `PokemonCardTrading` directory.
3. Replace existing files.
4. Run:

```text
install-phase5.5.2-exact-card-identity.bat
```

5. Run the normal scanner again to refresh active results and queue rows.

No workbook upgrade is needed. Older archive/history rows are not rewritten
automatically.
