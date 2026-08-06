# Phase 5.5.1 — Long-Term Dashboard Merged-Cell Hotfix

## Error corrected

```text
We can't do that to a merged cell.
```

The Phase 5.5 installer had already completed part of the upgrade before Excel
encountered a stale merged cell in a dashboard data-table area.

## Installation

1. Extract this ZIP.
2. Copy all files into the main `PokemonCardTrading` folder.
3. Replace the existing Python files.
4. Close Excel completely.
5. Run:

```text
install-phase5.5.1-dashboard-hotfix.bat
```

The Phase 5.5 installer is idempotent. Existing long-term columns and worksheets
are refreshed rather than duplicated.

There is no need to restore the pre-upgrade workbook backup.

## Safety

Only dashboard table-body ranges are unmerged when Excel reports a conflict.
The intended title and section-header merges are recreated and preserved.
