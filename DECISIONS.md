# Decisions made without Or

Each entry: what was decided, why, and what else was considered. The Lead keeps this log and reports new entries at the end of each wave.

## Wave 5

- **Fixed two reply rules after the first real run, before Or read the results.** A fallback reply said "Nothing in the catalog is under $10", copied from a prompt example, though 46 products cost less. Another stated "$49.98", a limit our code worked out from "cheaper". Both broke existing rules, so no design changed. The fix was checked by replaying 6 fallback cases on the real model (16 calls), not a full run. Alternative: wait for Or, which would leave a known false sentence in the app.
- **`evals/results.md` is committed from the run before that fix.** Its scores don't depend on the wording, but its replies for those cases show the old sentences. The final full run replaces it.

## Before wave 5

- **Exchange rates are a fixed table in `app/currency.py`, dated 4 Nov 2026.** Or asked for conversion and "roughly" fits a snapshot. It adds no network call or failure, and tests can check every number. Alternatives: a live rates API, which adds a failure on every message, or the model's own knowledge, which breaks the grounding rule and can't be tested.
- **The model reads the currency and code does the arithmetic.** The model writes the number as stated, with no 0.01 adjustment, and code converts. Alternative: let the model convert.
- **Converted limits are whole dollars.** The rate is rough, and the reply states the same number the search uses. The cost: "under 3,000 NIS" searches up to and including $948. Alternative: keep cents, which reads as false precision.
- **Seven currencies have rates: AUD, CAD, CHF, EUR, GBP, ILS, JPY.** Any other asks for the budget in dollars. Alternative: list more, each one more rate to keep current.
- **A question for a broad request asks only about the category, not the budget.** This replaces the earlier rule for shoes and watches, which also asked for a budget. Or's newer instruction is about finding the category. Alternative: also ask the budget.
- **Case 3, "Something nice for my living room", now expects a question.** It fits furniture and home decoration, so Or's rule applies. It used to expect cards from either.
- **Case 30, the shekel budget, now expects a converted search.** It used to expect a question, and four new cases cover both rules.

- **Or's rule for shoes and watches names only those two kinds.** They're the only kinds the catalog sells in both a men's and a women's category. Alternative: a general rule the model applies, which is harder to test.
- **The two-card eval cases check the exact product IDs.** `both` alone can't tell two suggestions from a search that dropped both limits. Alternative: read the replies by hand.
- **When one limit works alone, only that limit is dropped.** "Laptops rated 1 or more under $10" now keeps the rating and drops the price. Or's rule set the two-product case; this follows from it. Before, both limits were dropped. Alternative: keep the old order, rating then price.
- **The user's sort doesn't choose the two suggestions.** Each one answers its own limit, so "cheapest first" could otherwise pick the wrong one. Alternative: follow the sort.
- **The two suggestions can't grow with Show more.** There are exactly two, so no button appears. Alternative: add more products for each limit.
- **`datasets/answers/` shows the fallback's suggestions from the app's own code.** There's no independent source for them, and the file says so. Alternative: leave them out, which hides what Or wanted to see.

## Wave 4

- **A login page, not auto-login.** Chainlit's only password-free route is header auth, which lets in anyone who can reach the port and makes `APP_PASSWORD` meaningless. Alternative: header auth.
- **No Show more button on a resumed chat.** Chainlit sends the thread to the UI after `on_chat_resume`, so a button sent during resume is lost. Typing "show more" still works. Alternative: override more of Chainlit.
- **Cards are redrawn from message metadata, not stored as elements.** Chainlit only stores elements with a file storage provider. This keeps it to one SQLite file. Alternative: add a file provider.
- **Only shown products are saved, never every match.** All matches can be most of the catalog.
- **No connection stays open between statements (`NullPool`).** On Windows an open connection locks the file, so it couldn't be deleted or replaced while the app runs. The cost is one connection per statement, which is fine for one local user.
- **A failed statement is retried once after recreating any missing table, and a failed write shows one notice per outage.** Chainlit's writes run in the background and its layer swallows errors, so a failure would otherwise be silent. Alternative: log only.
- **A locked or unreadable file stops the app; only a damaged one is backed up.** Moving a healthy file away would look like lost chats. One backup is kept, and a newer one replaces it.
- **Notices and errors aren't saved.** They aren't part of the conversation, and saving a "could not save" notice would fail again.
- **Login values are checked for presence only.** A placeholder such as `choose-a-password` is accepted. Alternative: reject known placeholders, which adds a list to maintain.
- **Chainlit's thumbs buttons stay.** Their data goes into the `feedbacks` table, and nothing reads it.
- **Chainlit's warnings for failed statements stay in the console.** They include the SQL and its parameters, so chat text, but no secrets. Alternative: silence them, which hides the reason for a failure.
- **`greenlet` added with Or's approval,** through `sqlalchemy[asyncio]`. Chainlit's async layer can't load without it.

## Wave 3

- **The "nothing found" and "no more products" notes are written by code, not inferred by the model.** Whether anything was shown is a fact our code already has. Alternative: tell the model to work it out from the results.
- **The responder gets search bounds as stored, and the prompt explains them.** `price_max` 19.99 reads as "under $20". Alternative: pass the user's wording, which the schema doesn't carry.
- **Replies are one to three short sentences.** The cards carry the detail. This is prompt advice, not enforced.
- **A blank model reply raises an error.** It takes the same path as a failed call, so the chat shows the error. Alternative: send an empty message.
- **A refine replaces the current searches with the ones it edited.** If "a laptop and a phone case" is followed by "cheaper ones" aimed at one of them, the other is dropped. Alternative: keep every search, which needs rules for which ones still show.
- **A refine with an out-of-range index edits the first search, and one with no previous search merges into an empty search.** Neither should crash on a model mistake. Alternative: return the safe default.
- **A search with no field set, a typed "show more" with nothing before it, and a refine that clears everything all become a clarifying question.** Each would otherwise show all 194 products as a match or nothing at all. Alternative: run them.
- **A search with only a sort or a count still runs.** "The cheapest thing you sell" has an honest answer. The cost: "show me 5" with no earlier search shows the 5 highest rated products. Alternative: require a category, keywords or a bound, which would make the first question a clarification too.
- **Show more always gives 3 cards, even after a `top_k`.** After "the cheapest tablet", it gives the next 3 cheapest. Alternative: repeat the `top_k` count, which gives one card per click.
- **Cards from Show more arrive in a message with no text.** A fixed English label would break the rule that the button needs no language.
- **Show more runs in the click handler, not in a thread.** It is a quick filter, and with no pause between reading and saving the state, a double click can't show the same cards twice. Tested: a double click added 3 cards, not 6.
- **Errors in the chat use fixed text, and the log holds only the exception's type.** OpenAI errors can contain request details. Alternative: show the exception text.
- **Right-to-left uses `unicode-bidi: plaintext` in `public/style.css`.** Each paragraph follows its own first strong letter, so Hebrew and English both display correctly with no language detection. Alternative: detect the language and set `dir`, which is more code.
- **Buttons are at least 44px tall on a phone.** "Show more" measured 36px before the rule. Alternative: leave Chainlit's size.

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
- **A row expecting nothing earns 1.0 only if a search ran with its category, and a crashed row earns 0.** Otherwise a parser that always asks a question scores perfectly on those rows. Alternative: both-empty is always 1.0.
- **A correct `top_k` answer gets F1 1.0.** The returned set is treated as the expected set, because a tied product is equally right. Alternative: add all tied products to the expected set, which is harder to explain.
- **A currency word before a number has no left word boundary.** That lets the Hebrew prefix in "בדולר 30" match. The cost: "30 dollars 5 results" scores the 5 as an amount, which a read of the failure list would catch. Alternative: require a boundary and miss the Hebrew form.
- **"No false fallback" is scored over `product_search` rows with no expected fallback, and a crash counts as wrong.** Other intents never search, so including them would inflate the number. Alternative: all 30 cases.
- **A conversation with an error or missing turns counts as crashed.** Scoring the turns that did run would hide the failure. Alternative: score the last turn that ran.
- **Every report is built from the saved run file.** A rescore can't disagree with the live run. Alternative: build the live report from memory.
- **A run with errors, or one that stopped early, leaves `results.md` alone.** The report goes next to the run file instead. Alternative: overwrite, which could replace good numbers with partial ones.

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
