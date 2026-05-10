---
name: dealradar-triage
description: Run a full dealradar Phase A + Phase B cycle — fetch latest listings, triage 200 → shortlist 5 via Qwen 3.6 35B on station IA, produce ACHETER/VÉRIFIER/PASSER verdicts with margin estimates, persist to dealradar API, push Telegram top deals.
version: 0.2.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dealradar, business, flipping, capital-ladder]
    category: business
required_environment_variables:
  - STATION_SUDO_PASSWORD
  - TELEGRAM_BOT_TOKEN
  - TELEGRAM_CHAT_ID
---

# dealradar-triage

End-to-end Phase A + Phase B cycle for the dealradar (firesale-detector) capital-ladder flipping pipeline.

## [HARD CONSTRAINTS — DO NOT VIOLATE]

These rules apply to every step below. A single violation invalidates the entire cycle.

1. **NEVER reimplement sub-skill logic in Python.** ALWAYS invoke the named skill via the Hermes skill mechanism. Sub-skills available: `station-power-management`, `gpu-contention-check`, `dealradar-strategist`, `dealradar-lookup`, `dealradar-analyst`, `dealradar-pricer`, `dealradar-alerter`, `dealradar-learner`. If you find yourself writing `import urllib.request` or `subprocess.run` to do something a sub-skill already does, STOP and invoke the sub-skill instead.

2. **NEVER trust the LLM verdict for ACHETER/VERIFIER/PASSER.** The dealradar API endpoint `POST /api/analyze` validates and downgrades server-side: `margin_net < 30€` or `confidence < 0.7` or `sources < 2` ⇒ ACHETER becomes VERIFIER. Just send the raw LLM verdict, do not "fix" it client-side.

3. **NEVER trust the LLM margin number.** The pipeline recalculates `margin_net` from `(estimated_resale - platform_fees - shipping - purchase_price)` in Python. The LLM value is discarded. Do not "correct" prices in your code — submit the raw analysis and let the backend recompute.

4. **NEVER bypass the capital ladder filter.** The maximum purchase price = `current_capital × 0.8`. Even if Phase A LLM proposes a deal above budget, it must be filtered out by `dealradar-strategist` upstream.

5. **NEVER commit to a real purchase.** This skill emits verdicts only. Telegram alerts are signals for the user to buy manually after review.

6. **NEVER write your own ssh/wakeonlan/curl Python.** Delegate to `station-power-management` (which encapsulates the WoL + shutdown logic). Direct `terminal` curl calls are acceptable for simple HTTP GET/POST against `dealradar API` and `ia-commander` endpoints, but any compound logic (wake → check → switch → run → release) goes through the appropriate skill.

## When to use

- **Scheduled cycle**: every 15 min in active windows `02:00–06:00` and `13:00–17:00` Europe/Paris (off-peak Jellyfin / off-peak user). Configure via `hermes cron`.
- **Manual trigger**: `/dealradar-triage` for an immediate run.

## Inputs

- `since` (ISO 8601 timestamp, optional) — fetch listings scraped after this time. Defaults to last successful cycle from memory.
- `dry_run` (bool, optional, default false) — run the pipeline but skip writing verdicts and skip Telegram push.

## Outputs

- `cycle_id`, `listings_fetched`, `shortlist_size`, `verdicts[]`, `notifications_sent`.

## Procedure (executed in order; each step is a MANDATORY skill call unless flagged direct)

### Step 1 — Acquire station IA  [MANDATORY SKILL CALL]

REQUIRED ACTION: invoke skill `station-power-management` mode `acquire`.
DO NOT reimplement WoL or ssh checks in Python.

Expected output: `{state_before, we_powered_it}`.
On failure (timeout > 120 s after WoL): defer the whole cycle by 60 minutes via Hermes scheduler. Do not retry inline.

### Step 2 — Check GPU contention  [MANDATORY SKILL CALL]

REQUIRED ACTION: invoke skill `gpu-contention-check` with `variant_target = "qwen36"`.
DO NOT query rocm-smi or ComfyUI manually in Python.

Branching on the returned verdict:
- `verdict = "busy"` → log reason, if `we_powered_it=true` invoke `station-power-management` mode `release`, then defer cycle 60 min. Exit.
- `verdict = "free"` → continue to Step 3 (switch).
- `verdict = "already-loaded"` → skip Step 3, jump to Step 4.

### Step 3 — Switch ia-commander to qwen36  [DIRECT HTTP — ONE COMMAND]

REQUIRED ACTION: a single `terminal` call: `curl -sS -m 180 -X POST http://192.168.1.20:8090/switch/qwen36`.
This is the only place a direct curl is justified — ia-commander has no skill wrapper yet.

On non-2xx response: defer cycle 60 min, invoke `station-power-management` mode `release`, exit.

### Step 4 — Fetch fresh listings  [DIRECT HTTP — ONE COMMAND]

REQUIRED ACTION: a single `terminal` call: `curl -sS -u "$AUTH" "$DEALRADAR_API/api/listings/recent?since=<since>&limit=200"`.

If the response array is empty: invoke `station-power-management` mode `release`, exit cleanly.

### Step 5 — Phase A triage  [MANDATORY SKILL CALL]

REQUIRED ACTION:
1. Invoke skill `dealradar-strategist` to get the active strategies and capital ladder. The skill returns the search constraints and category whitelist/bans.
2. Invoke skill `dealradar-analyst` mode `triage` with the 200 listings and the constraints from step 5.1. The skill returns a JSON shortlist of up to 5 items.

DO NOT compose the Phase A prompt manually. The system prompt lives inside the `dealradar-analyst` skill — using it ensures the FAST mode prefix and JSON contract.

If the shortlist is empty: invoke `station-power-management` mode `release`, exit cleanly.

### Step 6 — Cross-platform comparable lookup  [MANDATORY SKILL CALL — once per shortlist item]

REQUIRED ACTION: for each shortlist item, invoke skill `dealradar-lookup` with the item title and category. Returns comparable prices on eBay sold / Vinted / Wallapop.

DO NOT call `/api/search` manually with hand-crafted keyword variants — `dealradar-lookup` knows how to widen/narrow per platform.

### Step 7 — Phase B verdict  [MANDATORY SKILL CALL — once per shortlist item]

REQUIRED ACTION:
1. Invoke skill `dealradar-pricer` with the item + comparables → returns `estimated_resale + confidence + recommended_platform`.
2. Invoke skill `dealradar-analyst` mode `verdict` with the item + pricer output → returns `verdict + margin_breakdown + reasoning + red_flags`.

DO NOT compose the Phase B prompt manually. The DEEP mode prefix and threshold logic live inside `dealradar-analyst`.

### Step 8 — Persist verdicts  [DIRECT HTTP — ONE COMMAND]

REQUIRED ACTION: `curl -sS -X POST $DEALRADAR_API/api/analyze` with the verdicts array.

The backend validates server-side (margin ≥ 30€, conf ≥ 0.7 for ACHETER) and downgrades automatically. Do not pre-validate in Hermes.

### Step 9 — Notify  [MANDATORY SKILL CALL]

REQUIRED ACTION: invoke skill `dealradar-alerter` mode `instant` with the persisted verdicts. The skill enforces the top-5% rule (`verdict=ACHETER ∧ margin_net ≥ 50 ∧ velocity ≤ 7 ∧ confidence ≥ 0.8`) and pushes Telegram for matching items only. Other ACHETER/VERIFIER are queued for the digest run (3×/day).

DO NOT call the Telegram Bot API directly here — `dealradar-alerter` formats the cards and de-duplicates against the `alerts` table.

### Step 10 — Release station  [MANDATORY SKILL CALL]

REQUIRED ACTION: invoke skill `station-power-management` mode `release` with the `we_powered_it` flag from Step 1.

### Step 11 — Memory update  [DIRECT — Hermes memory tool]

REQUIRED ACTION: append to Hermes agent memory: `cycle_id, timestamp, shortlist_count, verdict_counts (ACHETER/VERIFIER/PASSER), cumulative_margin_today`. The learning loop uses this for cross-cycle scoring refinement.

## Failure modes & defer signals

| Symptom | Action |
|---|---|
| Station IA WoL timeout | defer 60 min, log infra alert |
| GPU busy (ComfyUI active) | defer 60 min, release station if we powered it |
| ia-commander `/switch` HTTP non-2xx | defer 60 min |
| Phase A JSON parse error | retry once with stricter prompt; second failure → cycle aborted |
| Phase B JSON parse error per item | skip that item, continue with siblings |
| dealradar API unreachable | abort cycle, listings will be re-scraped next cycle |
| Telegram push fails | continue (verdicts already persisted) |

## Tools used (Hermes runtime)

- `terminal` — for the 3 direct HTTP calls (Step 3, 4, 8)
- Skill invocation — for Steps 1, 2, 5, 6, 7, 9, 10
- Hermes memory tool — for Step 11

`execute_code` Python is NOT to be used in this skill. If you need to compose a complex prompt, that means a sub-skill is missing — flag it to the user, do not work around it.

## See also

- [[station-power-management]]
- [[gpu-contention-check]]
- [[dealradar-strategist]] [[dealradar-lookup]] [[dealradar-analyst]] [[dealradar-pricer]] [[dealradar-alerter]] [[dealradar-learner]]
- Memory: `flywheel-master-plan.md`, `ia-commander-http-api.md`, `dealradar-thinking-policy.md`, `dealradar-hermes-test-2026-05-10.md`
- Source: `~/projects/firesale-detector/src/services/{prompts,llm_parser,llm_pipeline}.py` (PRD v2 + P0/P1 fixes)
