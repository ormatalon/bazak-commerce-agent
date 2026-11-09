# Experience pilot: 20 shopping conversations

This development set evaluates useful recommendations, avoidable non-answers, courtesy, natural phrasing, and conversation progress. It contains 14 English cases and 6 Hebrew cases, including 4 multi-turn conversations and 4 legitimate no-match controls. Read [CASES.md](CASES.md) for the requests and expectations together.

The owner requested 20 cases on 9 November 2026. These are assistant-authored draft expectations, not human-reviewed gold. The wording was written before generating answers to these cases. Several scenarios deliberately probe known failure classes, so this is a development pilot, not an independent holdout or proof that either implementation is better.

## Files and reproducibility

- `english.jsonl` and `hebrew.jsonl`: the 20 conversations, product evidence, expected behavior, and communication criteria. Hebrew user messages are kept in the Hebrew file.
- `catalog.json`: the same 194-product snapshot used for the matching V1/V2 source evaluation, with categories, titles, descriptions, prices, and IDs pinned for review.
- `exchange_rates.json`: the frozen evaluation quote fixture. Use these numerical rates for both implementations; retain and disclose differences in their rounding behavior. No live-rate calls during this pilot.
- `rubric.json`: four independent 0-2 dimensions, hard factual/constraint gates, and metric definitions.
- `manifest.json`: exact counts and hashes of UTF-8 text with LF line endings, so Windows Git line-ending conversion does not invalidate the content. Changing a case, rubric, catalog, or fixture requires intentionally updating the snapshot hashes.

Validate without keys or network, from the V2 repository root:

```powershell
.venv/Scripts/python.exe -m evals.experience
```

This command validates the data. It does not run the shopping model or assign subjective scores. The original 167-case suite is unchanged; its runner does not automatically include this pilot.

## Replay and review protocol

1. Freeze the two code commits and this manifest. Start empty state for each case. Replay every message through each implementation's full pipeline, preserving state only within that conversation. Save every turn, actual cards, replies, errors, and elapsed time before scoring.
2. Use the pinned catalog and numerical FX fixture, the allowed `gpt-6-luna` model, and the same concurrency/retry settings. Report initial connection failures and retries separately. Do not retry poor answers until they look good.
3. Randomize and hide implementation names while comparing each pair. Read the actual product descriptions and prices, not just category slugs. Rate usefulness, courtesy, phrasing, and task progress separately. Record reviewer identity, rationale, and disagreement. Unrated dimensions remain unknown.
4. Apply hard gates independently: correct catalog facts, explicit constraints or permitted disclosed alternatives, correct product type, no unsupported affirmative claims, and no instruction/private-data leak. A warm reply cannot rescue wrong products. An explicitly prohibited over-budget alternative is a failure even if disclosed.
5. For `UX12` and `UX17`, resolve "the second one" against each version's own first-turn cards. Do not hardcode the other version's reference product. If the reference turn fails, retain the case as a failed conversation rather than removing it from the denominator.
6. Report supported-request avoidable non-answer rate, useful recommendation rate, appropriate abstention on the four controls, separate communication scores, and A/B/tie/neither preferences. Show counts and individual failures; 20 cases are exploratory evidence, not a reliable population estimate.

Acceptable product IDs are non-exhaustive examples with reasons, not an exact list or required ranking. Other products are acceptable if catalog evidence supports the requested type/use and constraints. Do not score a refusal solely from an `off_catalog` intent or the absence of cards: legitimate abstention, useful clarification, an avoidable stall, and an execution error have different meanings.

`UX10` allows recommendations with a clear battery-information limitation; it does not reward invented specifications. `UX14` assesses an honest, polite correction while still helping with shopping; a negated mention of the shopper's fabricated price is not automatically an affirmative false price claim. `UX15`-`UX20` assess natural Hebrew; exact English catalog names may remain unchanged. Visual RTL rendering is a separate UI check.

No model responses have been generated or rated for this pilot yet.
