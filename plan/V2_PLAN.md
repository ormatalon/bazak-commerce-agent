# V2 implementation plan — Bazak Shopping Copilot

Audience: the AI engineer implementing V2. Source of truth: `Design V2 – Bazak Shopping Copilot.md`. Deliver a working local copilot, reproducible dataset evaluations, and LangSmith monitoring that explains why each card was shown.

## 1. Starting point and scope

- Work on `v2`, based on `master` plus the current datasets and V2 design. This branch does not include the V1 implementation. Inspect `staging` for reusable catalog, UI, storage, currency, and evaluation code; port selected modules with their tests rather than merging V1 wholesale.
- Keep the local Chainlit UI, product cards, SQLite conversation history, cached catalog, and structured parser/responder flow. Support English and Hebrew, including follow-ups and show-more.
- Use `gpt-6-luna` for parsing, responses, and any optional LLM evaluator. Use a local multilingual embedding model; start with the design's `multilingual-e5-small` candidate and pin the actual model identifier and revision after verification.
- Use the LangSmith Python SDK directly. LangChain, LangGraph, a vector database, and another evaluation framework are not required.
- Do not implement checkout, live inventory, user accounts beyond the existing local login, or live exchange-rate fetching.

Deliver each phase as a reviewable change with its checks and results. Build a small end-to-end path first, then improve it using measured failures. Do not promise an implementation date until the V1 reuse audit, local model smoke test, and annotation workload are known. Human labeling and review are separate work items, not free engineering capacity.

### Delivery priority and dependencies

- **Required:** a working local conversation flow, dual-vector retrieval, explicit constraints/exclusions, relevance checks and disclosed fallback, English/Hebrew dataset replay, independent scoring, and LangSmith traces plus comparable offline experiments.
- **Later:** automatic dataset synchronization, runtime LLM judges, automated alerts, broad parameter sweeps, and production-style dashboards. These must not delay the required deliverable. Start runtime monitoring with saved views, per-turn checks, and a documented session review.
- **Execution order:** Phase 1 baseline/contracts/labels and minimal tracing → Phase 2 index and feasibility check → one clear-query vertical slice through Phases 3–4 → vague/multi-turn/fallback behavior → Phase 5 full evaluation and calibration → Phase 6 monitoring handoff. Evaluation scaffolding and LangSmith tracing start in Phase 1, not at the end.
- **First reviewable milestone:** one English and one Hebrew request returns real catalog cards through parser → retrieval → response, with a trace link and a local scored result. Use a fake LLM for offline tests and the allowed model for the live smoke test.

## 2. Contracts to settle before implementation

Resolve these inconsistencies in the design explicitly in schemas, tests, and decision notes:

1. **A useful answer does not always mean cards.** Vague shopping requests should show up to three relevant, diverse cards and one follow-up question. Off-catalog requests, attacks, unsupported currencies, or an exhausted relevant catalog may have no cards, but must have a useful explanation. Never pad the response with unrelated products to reach three.
2. **Category guesses are soft.** Strong semantic matches survive a wrong category guess. Borderline matches need a category match; weak matches are dropped. Apply this rule to every card, including fallback cards. The design's shorthand “outside guessed categories” must not reject a strong match.
3. **Numbers are hard in the exact-results path.** Fallback alternatives may relax price/rating only when marked explicitly, with the original limit, changed limit, and reason. Exclusions never relax. Type relevance never relaxes. In a mixed result, identify which cards are alternatives.
4. **Sorting and pagination need a design decision.** Truncating to 10 before sorting can miss the actual cheapest relevant product and cap show-more. Proposed clarification for the current in-memory catalog: determine relevance across all products satisfying the current constraints, apply requested price/rating sort to all qualified products, then paginate. The top 10 remains a diagnostic retrieval window, not a limit on eligible inventory. This changes the design's candidate-first sorting order; record it as a proposed design amendment before implementing it. If candidate-only sorting is retained, label it honestly and page the full relevance-ranked list rather than exhausting after 10.
5. **Separate score meanings.** Similarity and category boost rank products; relative similarity determines relevance; independent labeled examples measure correctness. Do not use the model's own similarity as the evaluation ground truth.
6. **Relative relevance does not prove availability.** An unsupported query still has a highest-scoring catalog product. A z-score measures contrast within that catalog, not whether it contains the requested product type. Phase 2 must test this failure mode before adopting z-score zones as the sole gate. A score-only result may justify “I could not find a relevant match,” not a confident claim that the store does not carry a product.
7. **Directions differ from independent searches.** “A gift for my mother” has alternative directions for one request and shares its constraints/count. “A laptop under $1,000 and perfume under $50” contains separate requests with separate constraints. Keep these structures distinct; refinements must identify the request they edit.

## 3. Phase 1 — Foundation and evaluation baseline (1 day)

### Engineering work

- Establish `app/`, `tests/`, and `evals/` on V2. Reuse small, relevant pieces from `staging` after review. Update the V1-only instructions in `CLAUDE.md` and README to point to the V2 contract when implementation begins.
- Pin Python dependencies, catalog snapshot/hash, model configuration, and rate-table version. Keep keys in `.env`; add placeholders to `.env.example` only.
- Define typed contracts: parsed request, query directions with category guesses, numeric constraints with strict/inclusive operators, exclusions, sort/count, conversation mode, ranked candidate, and final turn result.
- Preserve original amount, currency code, and user's currency term separately from converted USD bounds. Carry shown IDs and active constraints through persistence.
- Define one structured turn result usable by the UI, local evaluators, and LangSmith. Include exact candidates, alternatives, final cards, rejection reasons, and errors.
- Inventory and validate all dataset IDs and labels. Case identity is `dataset_name:case_id`; IDs repeat between files.
- Create the V2 expectation overlay and a small reviewed relevance set now, before prompt or threshold tuning. Include supported queries, unsupported product types, vague requests, Hebrew, and close wrong-type products. Assign the engineer to draft annotations and the product owner or another human reviewer to approve changed behavior and semantic labels. Track unreviewed cases explicitly.
- Freeze grouped development/test manifests before tuning. Existing cases and historical outputs have already been inspected during V1 work, so call their test partition a frozen regression set, not an untouched benchmark. Add new, reviewer-authored queries kept out of implementation prompts for a prospective holdout. No training split is needed unless a model is actually trained.
- Create minimal LangSmith root/LLM traces and a local evaluation output schema in this phase. Use the Phase 6 specifications incrementally.

### Checks and exit criteria

- Dataset loader validates 65 deterministic CSV rows, 32 behavioral cases, 52 adversarial cases, and 18 Hebrew cases: 167 source cases at plan creation. Derive counts at runtime; README counts are stale.
- Freeze a V1 baseline from `staging` against the same catalog and legacy labels, if the environment can run it. Record unavailable baselines explicitly; historical answer files are reference material, not a fresh measurement.
- Store baseline outputs, configuration, failures, and metric denominators locally. Do not treat LLM-generated historical answers in `datasets/answers/` as gold labels.

## 4. Phase 2 — Dual embedding index (1 day)

### Engineering work

- Add `app/embeddings.py` and `app/index.py`. Build title text from title/category/brand and description text from description/tags. Handle missing fields consistently.
- Verify the pinned model's query/document formatting, multilingual behavior, normalization, and token limits against its model card. Apply the same formatting in calibration and runtime.
- Compute and cache both vectors per product. Cache identity includes catalog hash, product-ID order, model/revision, text-building version, normalization, and vector dimension.
- Validate cache metadata on load; rebuild when stale and write atomically. Cache query vectors within a request so fallback does not repeat embedding work.
- Download the model once during setup. A warm local run must not need a network fetch. Explain missing model/cache errors at startup.

### Tests and exit criteria

- Unit tests with tiny fixed vectors cover weighted cosine scores, missing fields, ID alignment, corrupt/stale cache, and deterministic ties by product ID.
- Integration smoke test loads the real pinned model and checks an English/Hebrew query pair against a fixed small catalog. Keep model-download tests separate from offline unit tests.
- Startup reports cache hit/rebuild, index build duration, and catalog/model version.

### Relevance feasibility checkpoint

- On the reviewed development queries, compare supported and unsupported product types using the proposed z-score zones. Include queries for which every catalog product is a poor match, and inspect false accepted cards rather than only mean F1.
- Test whether the same product becomes falsely acceptable when unrelated categories are added to the frozen test catalog. Record this sensitivity; relative scores depend on catalog composition.
- If zones cannot separate these cases, stop threshold tuning as a solution to availability. Propose a separately calibrated absolute similarity floor or a bounded product-type compatibility check, test it on development labels, and document the design amendment. Keep category guesses soft; do not quietly reinstate category filtering.
- Exit requires a working relevance/abstention policy with measured false-accept and false-reject counts. Do not assert that an embedding-only gate can guarantee product-type preservation.

## 5. Phase 3 — Parse, filter, and rank (1–2 days)

### Engineering work

- Update the parser to emit positive English query directions, validated category guesses per direction, explicit numeric limits, exclusions, sort/count, and mode. Feed it real catalog categories and recent conversation state.
- Use one direction for a clear request; a bounded list, initially up to three, for a vague request. A vague shopping request should not be sent straight to clarification without recommendations when relevant inventory exists.
- Keep independent product requests separate from alternative directions. Test separate budgets, per-request exclusions/counts, targeted refinements, and comparison requests.
- Convert currencies in code using the dated fixed rate table. Use decimal arithmetic; round USD upper bounds down and lower bounds up to cents. Respect strict versus inclusive operators after conversion. Generate the conversion introduction in code using the user's currency term.
- For a converted bound `x` in USD and prices in cents: inclusive maximum is `floor(100*x)/100`; strict maximum is `(ceil(100*x)-1)/100`; inclusive minimum is `ceil(100*x)/100`; strict minimum is `(floor(100*x)+1)/100`. Apply the operator once after conversion, not by subtracting a cent in the source currency. Test exact-cent and fractional-cent values.
- Apply numeric constraints and normalized explicit exclusions before selecting candidates. Keyword and category guesses never filter the catalog. Define exclusion matching, including brand/phrase boundaries and Hebrew paraphrases, with labeled tests.
- For each direction calculate semantic score `s = w * title_cosine + (1-w) * description_cosine`. Start with `w=0.6` and category boost `b=0.1`; treat both as tunable configuration.
- Calculate `z = (s - mean_catalog_s) / std_catalog_s` over the whole catalog for that direction, before numeric filtering and without the category boost. This keeps the boost from deciding its own relevance and budgets from changing the reference distribution.
- If variance is effectively zero, mark the direction uninformative; do not accept arbitrary cards because of category boost alone.
- Keep a candidate if `z >= strong_threshold`, or if `z >= borderline_threshold` and its category is guessed. Otherwise reject it. Require `strong_threshold > borderline_threshold`.
- Rank eligible products by `s + category_boost`. Apply the recorded sorting decision from Section 2; retain the full qualified list for pagination. Enforce stable ties.
- For vague-request diversity, select one qualified product per direction first, then fill by deterministic round-robin over the direction-ranked lists, skipping duplicates. Do not compare raw scores from different queries as if they were calibrated together. Requested total count caps the merged list; independent searches retain their own counts.

### Tests and exit criteria

- Cover plurals/synonyms, typo/paraphrase tolerance, Hebrew queries over English products, wrong category guesses, zero variance, numeric boundaries, currency rounding, exclusions, and unknown currency.
- Include a case where all globally highest-scoring products exceed the budget but a relevant affordable product exists. It must survive because filtering precedes candidate selection.
- Verify a weak second/third card is rejected even when the first card is strong. Verify category boost cannot rescue a weak card.
- Verify ranking, candidate sorting, explicit count, deduplication, and deterministic ties independently of LLM calls.
- Test 15 or more relevant products across repeated show-more turns, including an affordable product outside the initial top 10. Exclude already-shown IDs before taking the next page, not after truncation.

## 6. Phase 4 — Fallback, responses, and conversation behavior (1–2 days)

### Engineering work

- Add an explicit fallback policy for zero results or unfilled requested slots. Try relevant unseen inventory under all original limits first. Then attempt rating relaxation only if a rating constraint exists and the change adds eligible products; next attempt price relaxation. Retain exclusions and the relevance gate throughout. Record only changes actually used by selected alternatives. Reject contradictory bounds with a useful clarification rather than silently rewriting them.
- For an upper budget, choose the cheapest relevant alternatives above it; for a lower bound, choose the closest relevant alternatives below it. Document ordering when several limits are relaxed. Deduplicate against exact cards and already selected alternatives.
- For a two-sided price range, try relaxing one bound at a time while preserving the other. Choose the side with the smallest absolute USD boundary violation; break ties by semantic rank then product ID. If rating was also relaxed, disclose both. This is a proposed fallback detail requiring a decision note and labeled examples.
- Search for relevant inventory without numeric limits before explaining a no-match outcome. Distinguish unsupported type, exclusion conflict, numeric conflict, and relevance uncertainty. If no card qualifies, return an explanation and a supported-category suggestion or clarification. Only say the catalog lacks a type when catalog evidence supports that claim.
- The responder receives final products and structured outcome facts only. It must explain alternatives, avoid unsupported attributes, preserve real catalog prices, answer in the user's language, and ask one useful follow-up for vague requests.
- Persist parsed state, shown products, constraints, and outcome metadata. `refine` retains unspecified limits; `new` resets them; `show_more` excludes previous IDs without relaxing relevance or exclusions. Fallback limits belong to the outcome, not the user's saved request: subsequent turns retain the original budget unless the user changes it. Show-more must disclose any new alternatives again.
- Handle parser validation failures, provider timeouts, storage failures, and exhausted show-more results with useful messages.

### Tests and exit criteria

- Full-flow tests cover vague gifts, impossible laptop budget, unsupported product type, exclusions that eliminate everything, currency conversion, fewer than three relevant products, and follow-ups after restart.
- Verify alternatives are visibly disclosed and never counted as exact budget-compliant recommendations.
- Adversarial tests cover prompt leakage, invented discounts, fake tool/system instructions, and malicious catalog descriptions.

## 7. Phase 5 — Dataset evaluation and scoring (2 days)

### Version labels without hiding regressions

- Preserve the four source datasets. Add `datasets/v2/expectations.jsonl` keyed by source case identity, with V2 expectation changes, rationale, annotation version, and reviewer status.
- Migrate vague-request labels from clarification-only to relevant cards plus one question. Change strict category expectations where V2 permits strong cross-category matches. Preserve numeric, exclusion, grounding, and injection expectations.
- Retain two reports: legacy compatibility and V2 correctness. A changed expectation must appear in a migration report rather than disappear as a passing result.
- Add `datasets/v2/relevance.jsonl`: human-reviewed request/product pairs with semantic grade 0=wrong/unrelated, 1=partially relevant, 2=direct match; record constraint compliance, exclusion compliance, and permitted fallback status separately. An over-budget direct-match laptop remains semantically grade 2 but is ineligible for the exact path. Grade 1 never overrides a wrong product type or exclusion.
- Include original constraints, request/direction identity, catalog hash, and annotation rationale. Keep unavailable evidence as unknown rather than inferring a product has a feature because embeddings matched it.
- For a small subset of queries, judge the entire frozen catalog to support true recall and nDCG. For remaining queries, pool candidates from V1 and each V2 variant plus close negatives; report pool coverage and judged precision, not full-catalog recall. Unjudged products remain unknown, not negative. Include all-zero relevance queries explicitly.
- Use the Phase 1 grouped development/regression/prospective-holdout manifests. Tune only on development; inspect frozen tests after configuration selection. Once a test failure drives a change, move that case into regression and obtain fresh prospective cases before making a new generalization claim. Do not place evaluation examples in prompts.

### Three evaluation layers

1. **Offline unit/contract tests:** fake LLM responses and fixed vectors. Test schemas, arithmetic, filtering, fallback rules, persistence, evaluators, and trace redaction. No API keys or network required.
2. **Retrieval evaluation:** inject gold parsed requests to isolate embeddings/filter/ranking. Measure Hit@10, achievable Recall@10, Precision@3, and nDCG@3 where judgments are sufficient; measure relevance-zone precision/recall/F1 on binary direct-match labels. Compare lexical V1, embeddings without category boost, and the full V2 ranker. Hold parser output constant for retrieval comparisons; compare complete pipelines separately.
3. **End-to-end evaluation:** replay every source case through the real parser, retrieval, and responder. Reset state between conversations. Score each annotated turn and the final conversation outcome; earlier unsafe turns must not be hidden by a good last turn.

### Metric definitions

- **Parser:** exact match of stated numeric bounds/operators, exclusions, sort/count, intent, and mode; report each field and a full-request exact match. Category-guess coverage is diagnostic, not a hard product filter.
- **Deterministic compatibility:** independent gold filtering from CSV plus frozen catalog, with set precision/recall/F1 on the full pre-display result and tie-aware top-k sorting correctness. This legacy category-based score is a diagnostic; V2 semantic ranking is scored against V2 relevance judgments.
- **Retrieval:** define `k` as the requested count or the default 3. `Precision@k = eligible direct matches shown / k`; also report precision among shown cards and slot coverage against `min(k, eligible direct-match supply)` when supply is fully judged. Duplicate cards occupy slots but cannot earn repeated relevance credit. Evaluate fallback alternatives separately from exact cards.
- **Recall and ranking:** on exhaustively judged, answerable queries, let `R` be the number of eligible direct matches and `h` the number in the top 10. Report `Recall@10 = h/R`, its ceiling `min(10,R)/R`, and `achievable_recall@10 = h/min(10,R)`. `Hit@10` is 1 if `h>0`, otherwise 0. Report nDCG@3 with gains `2^grade-1`, logarithmic rank discount, and an ideal list from the same eligibility rules; missing positions have zero gain, including when fewer than three eligible products exist. Mark direct-match recall as N/A for R=0; mark nDCG as N/A when ideal DCG is zero. Score abstention separately.
- **No-match decisions:** report false acceptance on human-labeled unsupported queries and false abstention on answerable ones, each with its own denominator. A low empty-answer rate alone is not success. A nonempty generic explanation does not count as a successful shopping recommendation.
- **Constraints:** exact-path price/rating compliance, exclusion compliance across every card, duplicate rate, fallback type preservation, and disclosure accuracy. Evaluate original-limit violations separately for disclosed alternatives.
- **Behavior:** intent/mode accuracy, task completion, unwarranted refusal rate, expected card count subject to eligible supply, diversity across annotated query directions, language accuracy, follow-up-question correctness, and conversation task success. Score a useful answer with a versioned rubric: eligible recommendations or an appropriate no-match explanation, no constraint/grounding failure, correct fallback disclosure, and the expected next question. Mark unreviewed rubric judgments unknown.
- **Grounding/security:** catalog ID/price/attribute fidelity, unsupported product/price claims, leaked instructions, and attack success rate. Code checks validate structured facts; text attributes and subtle hallucinations require a reviewed rubric. Regex-only checks are insufficient proof of grounding.
- **Operations:** warm/cold startup, p50/p95 turn and stage latency, errors/timeouts, tokens per turn, model-call counts, and provider cost when configured pricing is available. Report missing cost data explicitly.
- Macro-average by case; also report counts, denominators, and slices: dataset, basic/hard, English/Hebrew, vague/clear, fallback/exact, and single/multi-turn. Exclude N/A metrics from denominators. Errors and timeouts remain failed cases.
- Run the full source/regression suite once per candidate configuration. For release, run the frozen prospective holdout three times with the same pinned configuration and show mean/range plus paired per-case changes. Fix request limits and retry policy; retain initial failures and retry counts so retries cannot hide instability. Unit and fixed-vector tests remain deterministic.

### Calibration and judge policy

- Tune in a small, recorded sequence: establish the 0.6/0.4 unboosted baseline, choose relevance/abstention thresholds, then test the category boost. Adjust title weight only if development failures justify it. Avoid an unconstrained sweep over many parameters on 167 source cases. Optimize direct-match relevance F1 with an explicit false-accept constraint from unsupported queries; inspect language and no-match slices. Lock the chosen configuration before final tests.
- Keep scoring functions independent of production filtering/ranking. Test metric functions with hand-calculated positives, negatives, ties, duplicates, missing cards, and empty sets. For legacy set metrics, both-empty earns 1 only if the intended search executed; abstaining from an answerable request does not earn a perfect score.
- Use human review for semantic ground truth. An optional `gpt-6-luna` judge may assess groundedness, relevance, disclosure, and helpfulness with a fixed rubric and structured output, but is a secondary signal. Check agreement on a human-reviewed sample; keep judge failures separate and never let a judge overrule a code-detected violation.

### Deliverables and proposed release gates

- Produce per-case JSONL and a Markdown report with inputs, labels, parsed fields, candidate scores/zones, exact/alternative cards, reply, failed assertions, timing, and trace IDs. Record git SHA, catalog/model/prompt/config hashes, dataset/label version, split, and seed where applicable.
- Proposed acceptance targets, to validate before tuning: all offline tests pass; 100% exact-path numeric compliance; 100% exclusion compliance; 100% disclosure of relaxed limits; zero successful injection/leak cases; no unsupported product/price claims on reviewed held-out outputs.
- Provisional quality targets: numeric/sort/count parser exact match >=95%; intent/mode accuracy >=95%; human-labeled direct-match precision among shown exact cards >=90%; achievable Recall@10 >=90% on exhaustively judged answerable queries; rubric-based useful answers on answerable cases >=95%; zero false accepted cards in the reviewed unsupported-type release cases. Validate target feasibility on development data and freeze targets before final tests.
- Report numerator/denominator and uncertainty alongside each target. With 18 mixed Hebrew cases, percentage targets alone are misleading: show case-level failures and do not claim language parity or population-level safety from a tiny slice. Zero failures means zero observed in the named test set, not a general guarantee.
- Compare V2 nDCG@3 and answerable-case failures with V1 using the same requests, catalog, and V2 labels. If V1 is unavailable, use an explicitly named lexical baseline. Accept only after reviewing every critical regression; a small positive aggregate delta is not enough. These are proposed targets, not observed results.
- Set a latency budget after the first measured local baseline, on named hardware, before optimization. No unmeasured latency or cost claim is a release result.

## 8. Phase 6 — LangSmith tracing, experiments, and monitoring (incremental from Phase 1)

### Instrumentation

- Add `app/observability.py` using SDK `traceable` spans and an instrumented OpenAI client where compatible with the pinned API. Keep tracing optional and isolate export failures so they do not break chat.
- One root trace per user turn; child spans: parse, currency conversion, query embedding, numeric/exclusion filtering, ranking per direction, relevance checks, fallback, response generation, and persistence. Index build gets a separate startup trace.
- Record sanitized request/structured output, product IDs, candidate counts, semantic scores, category boosts, z-scores/zones, rejected-card reasons, fallback changes, final card IDs, stage durations, LLM usage, and exceptions. Log bounded candidate lists, not the entire index or raw vectors.
- Attach conversation/thread ID, turn ID, language, intent/mode, git SHA, catalog hash, embedding revision, prompt/config versions, and dataset/case/split for eval runs. Preserve parent/child context through async calls.
- Configuration: `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, endpoint/region, and the destination appropriate to the workspace. Current docs distinguish agent-addressed environments from legacy tracing projects: use agent ID/environment for agent-based workspaces, or project configuration for legacy workspaces; do not mix addressing modes.
- Redact secrets and personal fields before export, including nested LLM inputs/outputs. Test the actual exported payload, not just application logs. Keep credentials, authentication headers, and full local conversation databases out of traces. Public evaluation examples may be traced in full after sanitization.
- Smoke-test a successful turn, fallback turn, parser error, and interleaved conversations; verify correct trace nesting and isolation. Verify disabled tracing and exporter failure leave the application usable. Bound exporter timeouts/queues and verify a slow exporter does not stall chat. Flush pending traces at evaluation shutdown so report links resolve.

### Dataset experiments

- Git datasets and versioned labels remain the source of truth. Required first implementation: upload an immutable, named dataset snapshot with stable case identities and source/version hashes; verify uploaded counts and split membership. Keep old experiment snapshots intact. Automatic idempotent synchronization is optional later work.
- Run offline experiments via SDK `evaluate`/`aevaluate` with explicit concurrency and retry limits. One conversation is one example, containing all its turns; return turn-level facts for the local scoring functions.
- Reuse the same evaluators locally and in LangSmith. Attach numeric feedback for constraint compliance, relevance, fallback disclosure, grounding, language, and task success. Use summary evaluators for aggregate metrics, excluding N/A values.
- Name experiments with version, git SHA, configuration, and dataset split. Compare baseline, ablations, and final V2. Export local artifacts even if LangSmith is unavailable; mark experiment upload failure separately from model failure.

### Runtime monitoring

- Track request counts, p50/p95 latency, error/timeout rate, token usage, optional cost, fallback rate, no-relevant-product rate, card-count distribution, language, and schema-validation failures. Separate application traffic from eval traffic.
- Attach cheap code-based feedback to every turn for price/ID fidelity, matched exclusion rules, duplicate cards, and structured fallback disclosure. Distinguish “no rule violation detected” from verified semantic compliance: a failed parser can omit an exclusion, and a metadata flag cannot prove the reply disclosed a relaxation. Review text and original user constraints in dataset evaluations. Leave unverified semantics unknown.
- Required monitoring deliverable: saved views or a small dashboard for volume/errors, latency, fallback/no-match outcomes, per-turn compliance checks, and failure traces, split by application/eval traffic. Run a scripted demo containing success, fallback, no-match, and failure; verify every outcome is visible and every local report can link to its trace.
- Optional later semantic judging: sample a bounded number of normal turns plus fallback/error/negative-feedback turns, deduplicated, with a fixed daily cap. Do not judge every timeout with an empty reply. Use the allowed model only, keep judge outputs separate from ground truth, and keep judging off the response path.
- Optional later alerts: critical for a detected exclusion leak, undisclosed relaxation, or verified successful injection; warning for an error-rate or latency increase over an explicit time window and minimum sample count. Set numeric thresholds after collecting a baseline; separate exporter outages from application outages. Local low-volume runs should use full-session review instead of unstable percentiles.
- Add a runbook: find trace, locate failing stage, reproduce against pinned catalog/config, review/redact the case, add a regression label, rerun the suite, compare experiments. Alert automation is not a release dependency for this local application.

## 9. Engineer handoff and completion checklist

- Code: catalog/index, parser/schema, currency, retrieval/relevance, fallback, response/pipeline, UI/storage, and observability modules with clear boundaries.
- Evaluation: loaders, independent ground truth, pure scorers, replay runner, a bounded calibration script, LangSmith snapshot upload/experiment runner, split manifest, and reviewed V2 label migration notes.
- Documentation: reproducible Windows setup using the virtualenv interpreter, first model download, local/offline tests, live dataset runs, calibration, tracing setup, cost/latency measurements, known failures, and accepted design decisions.
- Provide runnable commands after implementation, such as `.venv\Scripts\python.exe -m pytest tests evals` and documented `python -m evals.<runner>` entry points. Do not present planned CLI flags or nonexistent commands as working today.
- Final evidence: test summary, all-source-case evaluation report, prospective-holdout repeated-run report, baseline/ablation comparison, known/resolved regression list, relevance feasibility results, annotation coverage, redaction/export failure tests, monitoring views, and representative LangSmith success/fallback/error traces and experiments.
- Completion requires measured results and reviewed failure cases. A connected LangSmith account or a passing average alone is insufficient.

## LangSmith implementation references

Consulted 9 November 2026. Recheck against the pinned SDK during implementation.

- [Custom instrumentation: traceable spans and trace context](https://docs.langchain.com/langsmith/annotate-code)
- [Tracing quickstart: workspace destination and environment configuration](https://docs.langchain.com/langsmith/observability-quickstart)
- [SDK evaluations: datasets, evaluators, and experiments](https://docs.langchain.com/langsmith/evaluate-llm-application)
- [Online LLM evaluators: filters and runtime quality feedback](https://docs.langchain.com/langsmith/online-evaluations-llm-as-judge)
