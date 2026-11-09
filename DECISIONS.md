# V2 implementation decisions

## Approved extension — product-type node, 9 November 2026

- The owner approved adding a `gpt-6-luna` product-type check after ranking, before exact/fallback card selection, after z-scores accepted unrelated inventory for unsupported types. This supersedes the original two-call parser/responder path for product searches.
- Check all semantically shortlisted, unseen, nonexcluded products, including candidates that may become price/rating alternatives. Batch across requests/directions; deduplicate identical query/product pairs. A normal shortlist takes one additional call; larger shortlists use batches of at most 64 pairs so inventory and show-more are not silently capped.
- The node checks product type and named identity using catalog evidence. It does not decide numeric eligibility, loosen exclusions, reorder results or invent products. Category guesses remain soft. The code validates complete response identity coverage and fails closed on missing, duplicate, fabricated or invalid decisions.
- Checker reasons and per-candidate decisions are visible in LangSmith. No new dependency or model was introduced. Tests, supported/unsupported-type probes and the complete 167-case source replay run after the implementation checks; draft semantic labels remain drafts.
- The first full replay exposed incorrect parser strict-bound flags and omitted singular counts. Clarify each existing flag in the prompt/schema, reject strict flags without their corresponding bound, and interpret explicit singular superlatives as count 1. This fixes the existing numeric/count contract; no retrieval or pipeline-design change is made. Preserve the first run and score the corrected configuration separately.
- Validate all existing source card-count labels and distinguish no fallback, rating, price and both in legacy scoring. These are diagnostic compatibility checks; they do not replace V2 semantic labels or change the source expectations.

## Execution rules — 9 November 2026

- User instructions override V1-only clauses in CLAUDE.md: implement Design V2 in separate phase branches, merge each completed phase into v2, do not pause for stage reviews, and run evaluations at the end. Keep simple typed functions, explicit code, secrets handling, Chainlit/SQLite, and decision logging.
- Keep the existing deleted `Design Decisions.md` and `plan/PLAN.md` untouched. The active plan is `plan/V2_PLAN.md`. Existing local run files and Chainlit configuration are not staged wholesale.
- Branches use `v2-phase-N-*`: Git cannot create `v2/phase-*` while branch `v2` exists.
- Local multilingual embeddings, LangSmith, and their runtime dependencies are authorized by the V2 plan. Pin installed versions and the Hugging Face model revision. No other OpenAI model is called.
- Dataset expectation changes and semantic annotations are drafts until human reviewed; no assistant-generated label is presented as human ground truth. Final reports must expose this coverage limitation. Per the user's no-review instruction, do not request intermediate annotation reviews.
- Unit checks may run as implementation verification. Dataset replay, threshold calibration, baseline runs, and relevance feasibility measurements are deferred to the final evaluation, as explicitly requested. Initial thresholds remain marked provisional.
- Reuse the V1 catalog loader and Chainlit SQLAlchemy persistence integration, already implemented on staging, rather than choosing a new database architecture. Review the reused source directly; no review subagents or approval gates.

## Phase 1

- Original numeric amounts and strict operators remain in conversation state. Conversion produces an independent USD search copy to avoid cumulative rounding and accidental budget changes during fallback.
- A request owns one to three alternative directions; independent searches have independent limits. This follows the revised plan and avoids assigning one budget to unrelated product requests.
- Minimal tracing uses LangSmith's public trace context instead of wrapping every pure function. This is one of the SDK approaches described by the implementation references and preserves explicit stage boundaries.

## Phase 2

- Use E5 query/passage prefixes for every language, normalized vectors, CPU execution, and a 512-token limit, following the pinned model card. A first explicit download populates `.models/`; normal startup is offline for model loading.
- The cache stores two aligned arrays and plain JSON metadata in NPZ with pickle loading disabled. Rebuild on invalid metadata, vector shape, or norms; atomic replacement avoids half-written caches.
- Per the user's evaluation-at-end instruction, the relevance feasibility checkpoint runs at the final stage. No calibrated relevance or unsupported-type accuracy is claimed before that checkpoint.

## Phase 3

- Apply the revised plan's proposed all-qualified sorting policy: sort the full relevant inventory and paginate it. A top-10 list is trace/evaluation diagnostics only; truncating it before sorting would violate ordinary cheapest/highest-rated behavior and break show-more.
- Compute relevance z-scores without category boosts over the full catalog. Filter numeric constraints before selecting any candidates/cards, but preserve full-catalog score statistics. No category or keyword hard filters are introduced.
- Merge alternative directions by round-robin; raw similarities from different queries are not compared. Keep independent requests and their bounds separate.
- Exclusions use normalized whole phrases in catalog fields. Parser translates Hebrew exclusions to positive English matching phrases. This deterministic rule is conservative and requires semantic coverage evaluation; no untested claim of understanding all negation is made.

## Phase 4

- Reuse Chainlit's SQLAlchemy data layer and existing recovery/login code from staging. V2 messages have metadata version 2; V1 structured searches are not silently reinterpreted as V2 searches.
- Follow the revised plan's two-sided-range fallback rule: relax one price bound, retain the other, choose smallest absolute USD violation, then semantic rank and product ID. Keep rating-only alternatives before price alternatives.
- Disclosures for each alternative and currency conversions are generated by code and prepended to the grounded model reply. The show-more button uses the same turn path, so it cannot introduce undisclosed over-budget alternatives.
- Preserve original user constraints in saved state; conversion and fallback operate on copies. Save structured outcomes with each assistant message for replay and diagnosis.

## Phase 5

- Pure scoring functions distinguish legacy compatibility, observable V2 invariants, and unreviewed semantic metrics. Unknown semantic judgments are null, not an automatic success. Recall/nDCG require complete eligible judgments.
- Calibration refuses to use draft labels as human ground truth. Source expectations remain preserved; draft overrides and prospective holdout status are reported explicitly.
- Live replay requires `--live`, limits concurrency, stores every conversation's evidence as it finishes, and retains execution errors. Provider exception messages are omitted to prevent credential/request leakage.

## Phase 6

- The owner supplied a LangSmith credential; store it only in ignored `.env`. Workspace read access was verified without exposing its value. Use the `bazak-v2` destination for runtime traces.
- Required monitoring is a sanitized local event journal/dashboard plus LangSmith stage/LLM traces and a runbook. Automatic judges, alerts, and dataset synchronization remain deferred as the revised plan permits.
- Upload immutable evaluation snapshots and score recorded predictions rather than making a second set of model calls. Preserve source trace IDs and configuration so LangSmith experiment scores refer to the exact local evidence.
- Pass the pipeline's public trace headers into Chainlit message/card persistence so async SQL spans retain their turn parent. SQL parameters and authentication values are never exported.
- Final integration checks found a console-encoding issue in draft Hebrew relevance text; restore UTF-8 Hebrew. Final evaluation artifacts now save the complete normalized catalog alongside its hash for reproducibility.
