# LangSmith monitoring and evaluation runbook

## Configuration

Set `LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true`, and the correct endpoint in ignored `.env`. For legacy projects use `LANGSMITH_PROJECT=bazak-v2`; for agent workspaces use the documented agent ID/environment destination instead. Never commit credentials. `.env.example` has placeholders only.

The app and dataset runner trace each turn, with nested parse, embedding, rank, product-type check/batches, filter, fallback and response spans; OpenAI calls include model/token usage through the LangSmith wrapper. Index startup is a separate trace. Metadata identifies application/evaluation traffic, conversation, catalog and retrieval configuration. Product-type verdicts include candidate IDs and reasons; invalid coverage fails closed.

## After a local session

1. Run `.venv\Scripts\python.exe -m evals.monitor` to refresh `monitoring/dashboard.html`. It shows separate application/evaluation traffic, sample latency, errors, fallback outcomes and trace IDs. All monitoring files are ignored by Git.
2. Open the `bazak-v2` tracing destination in LangSmith. Filter root run name `shopping_turn`, metadata `traffic=application`, then inspect errors, fallback/no-match outcomes and high latency. Provider child runs carry token usage; unconfigured dollar costs remain unknown.
3. Inspect the full session when traffic is small. No automated alerts, online judges or population-level percentile claims are required for this local deliverable.

## Reproduce a failure

Find its trace ID in the local journal or dataset report. Check parser output, per-direction score/z-score and zone, constraints/exclusions, selected exact/alternative cards, disclosure, and reply in that order. Root traces do not export the entire database or vector arrays. Exception types are retained without provider exception text.

Reproduce with the same catalog/model revision/configuration. Preserve original user constraints. Add a reviewed regression label and rerun the affected checks. Do not change thresholds from a held-out failure and keep calling that case untouched test data.

## Offline experiments

Run `.venv\Scripts\python.exe -m evals.run_evals --live` at the final evaluation stage. This makes paid calls to `gpt-6-luna` and saves local per-case evidence incrementally under `evals/artifacts/`.

Then run `.venv\Scripts\python.exe -m evals.langsmith_experiment <evidence-directory>`. The command uploads a new immutable dataset snapshot, verifies identities/counts, and evaluates the exact recorded predictions with the same local metrics. It does not call the shopping model again. Dataset/experiment links are saved beside the report.

For a baseline comparison on the same immutable inputs, pass `--dataset-id <snapshot-id>` for the next implementation. The tool verifies every case identity and input turn before creating the experiment and never modifies the shared examples. Implementation-specific draft overlays remain in local evidence and experiment metadata.

Recorded-output experiment execution time is upload/replay overhead, not shopping latency. Use `measured_duration_ms` feedback for measured conversation duration and the original `shopping_turn` provider traces for turn latency, token usage and configured cost. The V1 source runner did not record durations, so its latency comparison is unavailable.

Legacy checks, draft V2 expectation metrics, and reviewed semantics are distinct. Unknown semantic metrics are omitted from numeric averages. Calibration requires human-reviewed development positives and negatives. Failed evaluation cases stay visible in execution-success counts.

## Export failures

Tracing is optional at runtime; local chat must keep working if exports fail. Check endpoint/destination/key configuration locally without displaying key values. Keep the local evaluation evidence and retry only the upload. Never retry an entire shopping turn just because its trace upload failed.

## Release decision

Run all source cases, reviewed relevance evaluation and the prospective holdout as specified in the plan. Inspect critical case regressions and false acceptance on unsupported product types. If relevance checks need a design change, stop and ask the owner before adding a new gate. Missing reviewed annotations prevent semantic release certification; an automated judge is not a substitute.
