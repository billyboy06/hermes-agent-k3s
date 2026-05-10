---
name: dealradar-lookup
description: Cross-platform comparable lookup for one shortlisted listing. Queries eBay sold + active, Vinted, Wallapop via the dealradar API and returns a structured comparables JSON ready for Phase B pricing.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dealradar, lookup, cross-platform, comparables]
    category: business
---

# dealradar-lookup

Sub-skill of `dealradar-triage` step 6. For one shortlisted item, query 3 alternative marketplaces (excluding its own platform) and return a structured comparables JSON consumed by `dealradar-pricer`.

## [HARD CONSTRAINTS]

1. **NEVER scrape the marketplaces directly.** All queries go through the dealradar API endpoint `POST /api/search` which already implements DataDome bypass, rate-limiting, and result normalization. If you find yourself writing playwright code, STOP — you are at the wrong layer.

2. **NEVER widen the search beyond the recommended platforms.** The platform set is selected by category; do not add platforms "to be safe" — extra noise hurts Phase B more than it helps.

3. **PREFER eBay sold over eBay active.** Sold listings = real transactions = ground truth for resale price. Active listings = asking prices, often optimistic.

4. **NEVER fabricate prices when no comparables are found.** Return empty arrays + empty `summary`. The pricer skill will fall back to its market knowledge with reduced confidence — that is the correct behavior.

## When to use

Always invoked by `dealradar-triage` step 6 — once per shortlist item. Not user-facing.

## Inputs

- `title` (str) — listing title (real, not LLM-paraphrased)
- `original_platform` (str) — `leboncoin` | `vinted` | `wallapop` | `ebay` (the platform of the source listing; will be excluded from the comparables search)
- `category` (str, optional) — Phase A category. Drives platform selection. Recognized values: `fashion`, `shoes`, `bags_accessories`, `watches_jewelry`, `phones`, `computers`, `electronics`, `audio_video`, `video_games`, `furniture`, `instruments`, `collection`, `other`.
- `estimated_resale_eur` (float, optional) — Phase A LLM rough estimate. Used only to size `price_max` for the search.

## Procedure

### Step 1 — Determine target platforms  [DIRECT — pure mapping]

Map `category` to the platform shortlist (excluding `original_platform`):

- `fashion`, `shoes`, `bags_accessories`, `watches_jewelry` → `vinted`, `leboncoin`, `ebay`
- `phones`, `computers`, `electronics`, `audio_video`, `video_games` → `ebay`, `leboncoin`, `wallapop`
- everything else (furniture, instruments, collection, etc.) → `ebay`, `leboncoin`

Default if `category` is missing: `ebay`, `leboncoin`.

### Step 2 — Build the query keywords  [DIRECT]

REQUIRED ACTION: derive `search_keywords` per platform:
- For `wallapop` (Spanish marketplace): keep only the first 3 words longer than 2 chars (brand names travel; French descriptions don't).
- For all other platforms: use the listing title truncated to 50 chars.

REQUIRED ACTION: derive `price_max`:
- if `estimated_resale_eur` is provided: `int(estimated_resale_eur * 2)`
- else: `10000` (effectively unbounded).

### Step 3 — Query dealradar API per platform  [DIRECT HTTP — once per platform]

REQUIRED ACTION: for each target platform, one `terminal` call:

```
curl -sS -X POST "$DEALRADAR_API/api/search" \
     -u "$AUTH" \
     -H "Content-Type: application/json" \
     -d '{"keywords": "<search_keywords>", "platforms": ["<platform>"], "price_max": <price_max>}'
```

Take up to 10 results per platform. Discard the rest.

### Step 4 — Filter out irrelevant results  [DIRECT]

For each result, drop it if **fewer than 2 of the search keywords** appear in the result title (case-insensitive, whole-word match where possible). The dealradar API's full-text search is generous on purpose; the lookup must tighten it.

If after filtering all results are gone for a platform, return that platform with empty arrays (do not retry with looser query).

### Step 5 — Normalize and return  [DIRECT]

Return a JSON object with the exact shape:

```
{
  "ebay_sold": [{"title": "...", "price": 123.0, "url": "...", "sold_at": "ISO date or null"}],
  "ebay_active": [...same shape, sold_at always null...],
  "vinted": [...same shape, sold_at null...],
  "wallapop": [...same shape, sold_at null...],
  "summary": {
    "total_results": N,
    "ebay_sold_count": N,
    "ebay_sold_median_eur": float or null,
    "ebay_active_count": N,
    "vinted_count": N,
    "wallapop_count": N
  }
}
```

A platform that was not queried (e.g. excluded as `original_platform`) is omitted entirely from the output, not returned as an empty array.

## Failure modes

| Symptom | Action |
|---|---|
| `/api/search` returns 503 (scraper down) | Retry once after 5 s. Second failure: drop that platform from the result, continue. |
| `/api/search` returns 0 results across all platforms | Return all empty arrays + `summary` with all zeros. Pricer will fall back to market knowledge. |
| Title contains only stop-words (e.g. `lot divers`) | Return empty results, log a flag. The strategist should not have shortlisted such an item — flag for the learner. |

## Tools used

- `terminal` — for the 1–3 HTTP calls to `/api/search`
- No `execute_code` Python — every step is a single curl + simple text manipulation

## See also

- [[dealradar-triage]] — caller (step 6)
- [[dealradar-pricer]] — consumer of the returned comparables
- Backend : `src/services/llm_pipeline.py` (`_filter_relevant_results`, similar logic in code)
- Endpoint : `POST /api/search` (PRD v2 S33)
