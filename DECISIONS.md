# V2 implementation decisions

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
