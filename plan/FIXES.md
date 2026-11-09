# Fixes

What went wrong, why, and how it was fixed. Newest first. The commit is at the end of each line.

## Found by the adversarial dataset (8–9 Nov)

`datasets/adversarial.jsonl` was written from four rounds of probing the real app, after the prompts were final. Its 15 `edge` cases failed 13 of 13 card rules before these fixes.

> **Overfitting risk.** Each of these fixes was made for cases we had just seen, so it may solve only those cases, and `adversarial.jsonl` is no longer a held-out test. The 72 deterministic queries showed no regressions, but two prompt changes in a row moved a borderline case somewhere else (pet food, then dresses). That pattern suggests the real limit is the design: word matching on titles and tags, with a model that never sees the products. A broader prompt rewrite, or a change to the pipeline, may be better than more patches.

- **"Phones but not Apple" showed only iPhones**, and the reply said no other phone existed. *Cause:* there was no way to exclude anything, so "non-Apple" went into `keywords` and ranked Apple first. *Fix:* a new `exclude_keywords` field, a hard filter on title, brand and tags that the fallback never loosens. `add9173`
- **"A kitchen knife" came with a Lunch Box and a Spice Rack**, and "how many kitchen knives?" said 30. *Cause:* "kitchen" is in the category's own name, so it matched every product in it. *Fix:* with a category set, words of its name don't count as keyword matches. `73d6a46`
- **"Do you have any knives?" said there were none.** *Cause:* matching knew only + s and + es, so "knives" never matched "Knife". *Fix:* the code matches y → ies and f/fe → ves, and the prompt asks for singular, correctly spelled keywords, which also fixes typos ("kniffe"). `9980954`
- **"Food for my dog" also showed Cat Food.** *Cause:* any one matching word earned a card, and Cat Food matches "food". *Fix:* only the products matching the most keyword words get cards. Show more steps down to the rest. `17dfdcb`
**Still open:**
- **"Food for my dog" is declined as off-catalog** in 2 of 3 runs, a side effect of the singular-keyword prompt rule above. The cause is that the parser sees only category slugs, and "groceries" says nothing about dog food. Listing each category's tags in the prompt fixed it (9 of 9), but made "dresses" ambiguous, because the catalog files girls' dresses under `tops`. Not committed.
- **Comparing two named products** ("iPhone X vs Galaxy S10") can show only one and say the other is missing.
- **"List every product"** dumps the whole catalog as 24 searches.
- **After two questions in a row**, the reply can forget the product ("for men" after a rupee budget).
- **"Wireless headphones"** also shows a charger. Matching is by word only, with no synonyms.
- **"The cheapest phones"** shows 1 card. A prompt rule says a plural superlative still means one item, written for "most expensive sunglasses".

## Earlier fixes (4–7 Nov)

- **Editing a sent message kept the old filters.** *Cause:* the edit re-ran the turn on state that already held the replaced turn's search. *Fix:* editing is switched off. `e73974e`
- **"List all", then "the 2 cheapest", still showed everything.** *Cause:* `show_all` outranked the new number. *Fix:* a stated number clears `show_all`. `e73974e`
- **A bedside table was called a match for "dining table".** *Cause:* one shared word ("table") earned it a card. *Fix:* replies name products by their title and say when nothing shown is what was asked. `9fd0b9b`
- **Replies stated limits our code worked out** ("$49.98" from "cheaper"). *Cause:* the responder saw the computed bound. *Fix:* the reply never writes a computed limit, and never repeats an amount the shopper dictated. `86c04ff`, `9fd0b9b`
- **"Nothing in the catalog is under $10"** for laptops, though 46 products are. *Cause:* the wording was copied from a prompt example. *Fix:* fallback replies talk only about the kind of product asked for. `86c04ff`
- **"How many is that?" started a new search.** *Fix:* a count question is a refine that changes nothing. `b4dcaf1`
- **A deleted database file lost the open chat from the sidebar.** *Fix:* the file is recreated, the user and the chat are restored, and the user is told once. `c80426f`
- **A phone case came with two speakers**, and "how many?" was answered by the model. *Cause:* every product in the category was a candidate. *Fix:* cards only for keyword matches, the count comes from code, and `show_all` lists everything. `dee9cc8`
- **Budgets in other currencies were read as dollars.** *Fix:* the model reads the currency, code converts it with a dated fixed-rate table, and the reply states the conversion. `f3cb521`
- **"Watches" or "electronics" fits several categories,** with no rule for which one. *Fix:* a request that fits several categories gets one question offering them. `8d36320`, `f3cb521`
- **"Furniture rated 4+ under $300" showed nothing useful.** *Cause:* no product meets both limits. *Fix:* the reply says so and suggests the cheapest with that rating and the highest rated at that price. `58da12f`
- **A run killed halfway could overwrite `results.md` with partial scores.** *Fix:* the report is built from the saved run file, and an incomplete run is saved next to it instead. `93c07a9`
- **Eval scores could be wrong in both directions,** for example a parser that always asks a question scoring 1.0 on rows that expect nothing. *Fix:* a dozen scoring fixes, such as needing a real search on empty rows, scoring several searches as one union, and treating tied products as equally right. `c4af780`
- **The prompt contained phrases from the datasets,** which inflated scores. *Fix:* reworded, with a test that blocks copied phrases. `c35e40d`
- **Answering "$300" switched the reply's language.** *Cause:* the reply's language followed a message with no words. *Fix:* the reply uses the language of the latest message that has words, checked by code in any language. `e341939`, `e040912`
- **A correct decline became a clarifying question.** *Cause:* an invented category in a stray search failed validation first. *Fix:* stray searches are dropped before validation. `384ecd9`
- **"Coffee table" found no table without "coffee" in it.** *Cause:* a multi-word keyword was matched as one string. *Fix:* each word counts on its own, non-Latin words are kept, and a fallback with no category and no keywords returns nothing. `897c0e8`
- **The card's image box had the wrong shape, and ratings were rounded.** *Fix:* a fixed image box and the exact rating. `05d6e47`
