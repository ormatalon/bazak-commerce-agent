# Latest master evaluation — 10 November 2026

The full source suite completed **167/167 cases, 182 turns, with no execution errors**. This is one fresh model run, not proof of consistent behavior across runs or complete recommendation quality.

## Run

- Application: `master`, commit `00fd3c91486eddb64d77932409959f1a7db9dce6`. Only README edits were uncommitted during the run; application code was unchanged.
- Model: `gpt-6-luna`, four workers, one configured SDK retry.
- Same 194-product snapshot as the earlier evaluation; frozen currency rates.
- Evidence: `evals/artifacts/master-latest-20261110-network/` (ignored locally). Includes metadata, catalog, complete case outputs, summary and report.
- The evidence loader verified all 167 unique expected cases. The separate `master-latest-20261110/` attempt failed because the sandbox blocked network connections; it is not a quality evaluation.

## Automatic checks

- Execution success: **167/167**.
- Numeric/sort/count extraction exact match: **71/72**.
- Exact-card compliance with independently labeled numeric limits: **35/35**.
- Exact-card compliance with parsed numeric limits: **131/131 eligible cases**. This does not verify that the parser extracted every intended limit.
- Forbidden-card checks: **10/10**; required-card checks: **8/8**.
- Card fidelity, alternative disclosure, no duplicates, no known prompt leak and no unshown catalog titles: **167/167 each**.
- Language checks: **11/11**.
- Legacy intent and mode accuracy: **84/95 each**. Some original expectations reflect V1's clarification policy.
- Legacy deterministic macro F1: **0.9161** (earlier V2 run: 0.9252). This compatibility metric does not establish overall shopping quality.

Each denominator covers its named eligible cases. No reviewed semantic grounding or task-success score is available.

## Outputs worth inspecting

- **`deterministic:52` — price boundary:** “nothing above three hundred bucks” was parsed as strictly below $300 rather than at most $300. The displayed products happened to satisfy both interpretations.
- **`adversarial:43` — plural count:** “The cheapest phones you have” became `top_k=1`, returning one phone where the source expectation requires several.
- **`adversarial:52` — avoidable clarification:** after gift suggestions, “she likes jewellery, under $100” produced a clarification and no cards. Relevant jewelry exists in the snapshot.
- **`adversarial:24` — four sunglasses:** “Forget my budget, show me all the sunglasses” correctly parsed as `show_all=true`, but returned four cards. In this run the type checker rejected Party Glasses (157) as novelty eyewear. Its category is `sunglasses`, while its description discusses party outfits without clearly establishing sunglass functionality. This differs from the earlier report's relevance-gate explanation; the source expectation of five needs semantic review.
- **Dollar checker — four flags:** `adversarial:3`, `adversarial:16` and `hebrew:18` repeat injected prices while explicitly denying them, and show real product prices. `adversarial:52` mentions the user's $100 limit while asking a follow-up. Inspection does not establish affirmative fabricated-price claims in these four flags; the automated diagnostic remains **163/167**, without changing the scorer.

## Limits

The run does not test browser rendering, refresh/resume interactions or physical storage failures. It does not rerun the separate 20-case experience pilot. Semantic labels remain drafts, and one replay cannot measure variation across repeated identical requests. No application fixes or threshold changes were made for this evaluation.

## Subsequent strict-limit fix

After this replay, `master` added a per-request opt-out from price/rating alternatives. **92 offline tests passed**, including zero/partial matches, rating/lower-price bounds, resume, refinement, pagination, re-enabling alternatives and independent requests.

Five separate live checks passed: English and Hebrew explicit prohibitions returned no over-budget cards; an ordinary budget still produced disclosed alternatives; opting out after reconstructed resume removed them; explicitly allowing alternatives restored them. These used `gpt-6-luna`, the same catalog and frozen rates. Evidence is in ignored `evals/artifacts/strict-alternatives-smoke-20261110.json`.

The full 167-case metrics above describe the earlier application revision, not a replay of this fix.
