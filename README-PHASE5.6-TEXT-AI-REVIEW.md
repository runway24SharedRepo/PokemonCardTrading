# Phase 5.6 — Text-Only AI Listing Intelligence

## Purpose

Phase 5.6 adds a conservative OpenAI review layer to:

- Random Snipe Results
- Random Snipe Queue
- legacy Snipe Queue
- Live Opportunities
- every `Seller - ...` worksheet
- optionally Random Snipe History and Opportunity Archive

The deterministic matcher remains the authority that initially identifies and
prices the card. AI provides a second opinion and cannot silently replace the
card ID or market value.

## No image cost

Phase 5.6 sends **zero images**. The review uses only:

- eBay title;
- seller short description;
- condition description;
- item specifics;
- buying format;
- seller feedback summary;
- current spreadsheet assignment;
- up to five database candidates.

`Image Review Enabled` is locked to `NO`.

## AI result columns

Every supported result sheet receives:

```text
AI Review Request
AI Review Status
AI Action
AI Identity Verdict
AI Selected Candidate
AI Confidence %
AI Edition Verdict
AI Variant Verdict
AI Listing Risk
AI Risk Flags
AI Condition Summary
AI Long-Term Note
AI Evidence
AI Model
AI Input Tokens
AI Output Tokens
AI Estimated Cost ($)
AI Reviewed At
AI Reviewed Item ID
```

### Review Request

```text
AUTO
YES
NO
```

`YES` forces the row into `runGPTSelectedReview.bat`; `NO` excludes the row;
`AUTO` applies the smart rules.

### AI Action

```text
KEEP
BLOCK
MANUAL REVIEW
```

`KEEP` requires all of the following:

- AI verdict is CONFIRMED;
- selected candidate equals the spreadsheet candidate;
- confidence meets the configured threshold;
- listing risk is not HIGH or BLOCK.

The AI never bids, buys, changes a market value or overwrites card identity.

## New worksheets

### AI Review Settings

Controls model, reasoning effort, per-run limit, monthly budget, minimum card
value, eligible decisions, uncertain-match review, risk/edition review, archive
inclusion, eBay text fetching, urgent queue time and confidence threshold.

Default model:

```text
gpt-5.6-luna
```

### AI Review Log

Permanent audit trail containing the source sheet/row, item ID, current and AI
candidate, verdict, action, confidence, edition/variant result, risk flags,
evidence, token usage, estimated cost, cache status and OpenAI response ID.

## Cost controls

The local cache and usage ledger is:

```text
data\ai-review-cache.sqlite
```

It provides exact review caching, no repeat charge for unchanged listings,
current-month spend tracking, a per-run review cap, a monthly budget stop and a
conservative reserve before each new call.

Supported built-in price tables:

```text
gpt-5.6-luna
gpt-5.6-terra
gpt-5.6-sol
gpt-5.6
```

## BAT files

### configureGPT.bat

Stores `OPENAI_API_KEY` in the local `.env` file using hidden input.

### testGPTConnection.bat

Checks authentication and model access through the Models API without
generating a listing review.

### runGPTSmartReview.bat

Reviews active rows that are GREEN/AMBER above the configured value, uncertain
matches, risk-wording listings, or listings mentioning First Edition,
Unlimited or Shadowless.

### runGPTSelectedReview.bat

Reviews only rows where `AI Review Request = YES`.

### runGPTQueueUrgent.bat

Reviews queue rows ending inside the configured urgent time window.

## Installation

1. Extract the add-on ZIP.
2. Copy all files and folders into the main `PokemonCardTrading` folder.
3. Replace existing files.
4. Close Excel.
5. Run:

```text
install-phase5.6-text-ai-review.bat
```

6. Run:

```text
configureGPT.bat
testGPTConnection.bat
runGPTSmartReview.bat
```

## API design

The implementation uses the OpenAI Responses API, Pydantic Structured Outputs,
`store=False`, restricted candidate keys, no tools, no web search, no image
input, concise structured responses, and a local cache/spend ledger.

The API key is never written into the workbook.
