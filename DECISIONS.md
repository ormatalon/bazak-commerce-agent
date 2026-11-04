# Decisions made without Or

Each entry: what was decided, why, and what else was considered. The Lead keeps this log and reports new entries at the end of each wave.

## Wave 2

- **Each word of a keyword counts separately.** "Coffee table" must find the only table, and "running shoes" with no category must find shoes. The cost: "face cream" with no category also matches Ice Cream. Alternative: require all words, which returned nothing for those cases.
- **Loosened results rank by keyword count before distance from the limit.** Otherwise "iphone rated above 5" shows no iPhone and the reply reads as if we don't carry one. Alternative: distance only, as first written in `CLAUDE.md`.
- **A search with no category and no keywords is never loosened.** Loosening it would return all 194 products as a match. The cost: "anything under 50 cents" finds nothing. Alternative: loosen and show the cheapest, which contradicts the rule against returning the whole catalog.
- **Non-Latin keywords stay as words and match nothing.** A Hebrew keyword used to vanish, which returned all 194 products. The parser is told to write keywords in English, so this is only a safety net.
- **Ties on the sort value score as either being right.** Search breaks ties by rating then ID, but a shopper asking for the cheapest can't tell tied products apart, and rows 38, 54 and 57 failed a perfect agent. Alternative: copy search's order into the ground truth, which makes it depend on search.
- **The prompt rewords every phrase close to a dataset row, including ones `CLAUDE.md` suggested.** The rule against dataset text comes first, and these would inflate scores. A test checks new phrases by similarity. Alternative: keep the suggested phrases.
- **A `new` search with no field set gets the safe default.** It would otherwise match the whole catalog. Alternative: run it.
- **The safe default logs a warning with the reason only.** A failed parse otherwise looks like a real clarification and scores as correct on rows expecting one. Alternative: no logging.
- **The OpenAI client retries once.** A persistent error then shows in about 2 minutes, not 3. Alternative: the client's default of two retries.
- **`keywords` stays null when the shopper names only the category.** The plan's Hebrew check now only requires any keywords to be English. Alternative: always fill keywords, which adds nothing because a category search doesn't filter on them.

## Wave 1

- **A broken cache file counts as missing.** The app downloads the catalog again and overwrites it, because the file is only derived data. Alternative: crash with a message.
- **A failed cache save warns and carries on.** The catalog is already in memory, so stopping would be worse, but every load then downloads again, so it prints a warning. Alternative: fail silently, which the Reviewer rejected.
- **The cache holds raw API data, validated on load.** That way it doesn't depend on our model's field names. Alternative: save `Product.model_dump()` output.
- **`CatalogError` is its own exception,** so `app/main.py` can catch it and show the message at startup. Alternative: a bare `RuntimeError`.

## Wave 0

- **Eval labels for the new language cases.** Added Hebrew and Spanish rows to `datasets/`, with Hebrew chosen because Bazak is Israeli. Alternative: test only Spanish, which would miss right-to-left text.
- **Grounding score covers titles and money amounts only.** Other numbers are printed for Or to read. Alternative: an allow-list for every number, which failed true replies such as "5 laptops; here are 3".
- **Reply language is checked with Hebrew script and short stopword lists.** Alternative: a language detection library, which adds a dependency for 4 eval cases.
- **Show more makes no LLM call.** It only adds cards, so it needs no language. Alternative: pass the last typed message to the responder, which costs a call for no new information.
- **Chainlit stays after the mobile test.** At 375px in headless Chromium, the login, chat, past-chats drawer and resuming a chat all worked with no sideways scrolling. One early run clicked the sidebar button and no drawer appeared; it worked in every later run and wasn't explained, so Or's phone-width check in wave 3 should try it. Alternative: switch frameworks, which the test gave no reason to do.
- **Hebrew needs CSS.** In the same test, a Hebrew reply rendered left-to-right with its punctuation misplaced. The App role fixes this in Step 5.
- **`app/main.py` adds the repo root to `sys.path`.** `chainlit run` only puts `app/` on the path, so `from app...` failed. Alternative: run from another layout, which would move every module for one import.
- **`app/llm.py` holds the real OpenAI client, owned by the LLM role.** Keeping it separate means the other modules and all tests only see a plain callable.
- **Pinned the direct dependencies** to the tested versions, so a stranger's install matches.
- **`app/pipeline.py` runs one turn with no Chainlit in it.** The UI, the flow test and the evals all call it, so scores measure the shipped wiring. Alternative: put the logic in the Chainlit handler, which evals would have to copy.
- **The responder only sees `shown`, not every match.** Otherwise it could name a fourth phone when three cards appear. Alternative: tell it in the prompt to mention only some, which nothing would enforce.
- **`keywords` is nullable.** On a refine, null means keep, the same as every other field. Alternative: treat an empty list as keep, a special case for one field.
- **`top_k` is checked in a validator, not `Field(gt=0)`.** That keeps `exclusiveMinimum` out of the structured-output schema, because no real call has confirmed the API accepts it. Alternative: test it first, which needs the key.
- **Stray search fields are dropped when the intent isn't `product_search`.** An off-catalog request can't show cards. Alternative: reject the output, which would turn a correct decline into a clarifying question.
