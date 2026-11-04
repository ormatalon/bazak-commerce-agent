## Test datasets

The repo includes two small datasets of questions with expected answers, used to evaluate the agent. Each case is labeled `basic` or `hard`.

### `deterministic.csv`

65 single-turn shopping queries (50 basic, 15 hard), each with the exact search filters the agent should extract: `category`, `price_min`, `price_max`, `rating_min`, `sort_by`, `order` and `top_k`. Empty columns mean the filter should not be set.

### `behavioral.jsonl`

26 conversations (20 basic, 6 hard), some with several turns, that test how the agent handles situations such as ambiguous requests, off-catalog requests, follow-ups, empty results and prompt injection. Each case lists the user's `turns` and the expected outcome:

- `expected_intent`: the intent the agent should identify
- `expected_mode`: whether the search is new or refines the previous one
- `expected_categories` and `category_match`: the categories to show, and whether all or any of them must appear
- `expect_fallback`: the filter the agent should loosen when nothing matches
- `expected_behavior`: a plain-language description of the correct response
