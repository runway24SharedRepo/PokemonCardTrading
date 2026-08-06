# Phase 5.6.1.1 — Fast Market Repair Hotfix

## Symptom

The Phase 5.6.1 installer displayed:

```text
Could not find platform independent libraries <prefix>
Could not find platform independent libraries <prefix>
```

and then appeared to stop.

Those Python-environment warnings are not the actual failure. The original
repair script produced no progress output and updated many Excel cells one at
a time. Large market tables could therefore take a very long time.

## Correction

The replacement repair:

1. displays eight progress stages;
2. opens Excel without updating external links;
3. reads the Full Card Database in one operation;
4. recalculates the complete Market Data Import table in memory;
5. writes the corrected table back in one bulk operation;
6. saves a timestamped backup before changing the workbook;
7. reports row counts and source status at completion.

## Installation

If the original installer has shown no new output for more than ten minutes:

1. press `Ctrl+C`;
2. use Task Manager to close any leftover hidden `EXCEL.EXE` process;
3. extract this ZIP;
4. copy all files into the main `PokemonCardTrading` folder;
5. replace existing files;
6. close Excel;
7. run:

```text
install-phase5.6.1.1-fast-market-repair.bat
```

A successful run progresses from `[1/8]` through `[8/8]`.

Backups are stored under:

```text
backups\phase5.6.1.1
```
