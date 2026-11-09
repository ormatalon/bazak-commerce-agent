# Final V2 evaluation - 9 November 2026

## Outcome

The approved product-type node is implemented and merged into v2. Final live replay completed all 167 source cases with zero execution errors. The implementation has 33 passing offline checks. This completes the node implementation and source-dataset evaluation; semantic release certification remains pending reviewed labels and calibration.

## Product-type verification

- Gaming console: relative-only ranking accepted 2 wrong-type products; the new node accepted 0.
- Electric wheelchair: relative-only ranking accepted 4 wrong-type products; the new node accepted 0.
- 3D printer: relative-only ranking accepted 2 wrong-type products; the new node accepted 0.
- Laptop, perfume, and Hebrew laptop probes each retained 5 appropriate catalog products.
- These are diagnostic probes, not an independent generalization benchmark.

## Automatic checks on the final recorded outputs

- execution_success: 167/167 (100.0%).
- numeric_sort_count_exact_match: 72/72 (100.0%).
- labeled_exact_numeric_compliance: 35/35 (100.0%).
- exact_numeric_compliance: 144/144 (100.0%).
- forbidden_card_compliance: 10/10 (100.0%).
- required_cards_present: 8/8 (100.0%).
- language_accuracy: 11/11 (100.0%).
- no_duplicates: 167/167 (100.0%).
- catalog_card_fidelity: 167/167 (100.0%).
- alternative_disclosure: 167/167 (100.0%).
- no_known_prompt_leak: 167/167 (100.0%).
- no_unshown_catalog_titles: 167/167 (100.0%).

Numbers use their named eligible denominators: 72 deterministic cases include 65 English and 7 Hebrew cases. Numeric checks on parsed limits do not independently prove the parser read every user constraint correctly; the separate labeled-bound check covers the applicable source cases. Disclosure and grounding regex checks are mechanical evidence, not semantic guarantees.

## V1 comparison and remaining regressions

- Legacy deterministic macro F1: V1 0.9861; V2 0.9252 across 72 cases. V2 is lower on this compatibility metric; no quality-improvement claim is made.
- Legacy intent accuracy: V2 87/95; mode 85/95. Four draft V2 expectation overrides pass, but remain unreviewed.
- Legacy exact-card expectations: 1/3; minimum-card expectations: 2/3.
- behavioral:31 and behavioral:32 differ from V1 exact alternative-card expectations. V2 fills three disclosed alternatives; the bags case also misses a high-rated alternative. These require relevance/fallback assessment rather than silently changing the gold labels.
- adversarial:24 asks for all five sunglasses; four were returned. The relative relevance gate still rejects a valid item before the new node. This is a remaining recall failure.
- The dollar-mention checker flags hebrew:18 because the answer truthfully says the products do not cost the injected $100. Inspection confirms it lists real prices and denies the fabricated price. The flag is retained as a conservative numeric diagnostic, not labeled a successful price-manipulation attack.
- Source labels still contain V1 clarification/category behavior. Legacy mismatches and draft V2 correctness metrics are reported separately.

## Calibration and acceptance status

- No human-reviewed development positives/negatives are present. The calibration command correctly refused to certify thresholds from drafts. Thresholds remain provisional.
- No independent reviewer-authored prospective holdout is available. Three repeated holdout runs, reviewed nDCG/relevance scores, semantic ablations and useful-answer/grounding certification remain pending those inputs.
- All proposed release gates are not satisfied. Do not describe this implementation as fully release-certified or claim V2 outperforms V1 from these results.
- Any further relevance-policy or pipeline change still needs owner approval. No additional architecture change was made after the approved product-type node.

## Operations and evidence

- Final evaluation: 167 conversations/cases, 182 turns; measured turn p50 8559 ms, p95 15336 ms on this local run. This is a sample measurement, not a service-level objective.
- The V1 runner did not capture comparable latency. Recorded-output LangSmith experiment duration is replay overhead; actual V2 duration is published as measured_duration_ms feedback and in original traces. Token usage is in provider spans; configured cost is not certified here.
- [V1/V2 experiments on the same immutable inputs](https://smith.langchain.com/o/7b56a565-d567-4ebc-a294-baf18f745709/datasets/4ddc3703-9799-4009-9ad1-f97f727f6db3/compare?selectedSessions=03a01b61-85e6-434b-aa6c-8847005fe7a2,319c70bc-608e-456c-b5bc-bea6e0474248).
- Local final evidence: evals/artifacts/v2-final-verified/rescored/ (per-case JSONL, report, scores, catalog, scorer provenance, operations and final-run monitoring events).
- V1 frozen baseline and its source revision: evals/artifacts/v1-baseline/.
- Earlier complete V2 run: evals/artifacts/v2-full-product-type/. Superseded partial retry: evals/artifacts/v2-final/; it is explicitly marked interrupted and is not published as a full run.
- Only scoring/reporting changes were made after the final model run; immutable outputs were re-scored without additional model calls. Application prediction revision and scorer revision are recorded separately.
