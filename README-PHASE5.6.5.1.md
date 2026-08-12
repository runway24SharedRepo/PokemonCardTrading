# Phase 5.6.5.1 — Daily updater BAT fix

This launcher-only patch corrects the PowerShell parser error:

```text
The ampersand (&) character is not allowed.
```

## Install

1. Close the daily updater window and Excel.
2. Copy this package's contents into the main `PokemonCardTrading` folder.
3. Run `install-phase5.6.5.1-daily-bat-fix.bat`.
4. Run `update-pokemon-market-daily.bat`.

The updater's output will appear live and will also be saved to
`pokemon-market-daily.log`.

This patch changes only `update-pokemon-market-daily.bat`. It does not alter
the Phase 5.6.5 exact-variant TCGplayer pricing implementation.
