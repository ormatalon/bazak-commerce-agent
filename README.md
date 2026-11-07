# Bazak Shopping Copilot

## Overview

A minimal AI shopping copilot. You chat, it works out what you want, finds products in the DummyJSON catalog and shows them as cards inside the chat. Conversations are saved, so you can refresh, start a new chat, or return to an old one and continue where you left off.

It runs locally, in Python, with [Chainlit](https://docs.chainlit.io) as the chat UI and `gpt-6-luna` as the model. The main design choice is that the model does as little as possible: one call reads the request and one call writes the reply. Filtering, ranking, the fallback, currency conversion and the card count are all plain Python, so each behavior can be pointed to and tested.

For example, "Furniture rated 4 or more under $300" finds nothing, because no product meets both limits. The reply says so and shows two cards: the cheapest product rated 4 or more, and the highest rated under $300.

## Assumptions

These were confirmed by Bazak's CTO on 4 Nov 2026.

- **One local user.** Login and multi-device sync are out of scope. Chainlit needs a login to show past chats, so the app has one fixed user, set in `.env`.
- **A static catalog.** There are no stock or price changes during a chat, and fetching the catalog once and caching it is acceptable. See [Limitations](#limitations) for how this would handle live inventory.
- **English UI, any chat language.** The UI and product cards are in English. Users may write in any language, and the reply uses their language.
- **Desktop and mobile browsers.** The app is responsive.
- **Product discovery only.** There is no cart, checkout or orders.

I also decided not to stream replies. They are returned whole, which keeps card rendering simple.

## Setup

You need Python 3.11 or newer (tested on 3.12), and network access the first time, to fetch the catalog.

**macOS.** The Python that comes with macOS may be too old. If `python3.12` isn't found, run `brew install python@3.12`.

```bash
git clone <repo-url>
cd <repo-folder>
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/chainlit create-secret
```

**Windows (PowerShell).** Clone into a short path: one dependency has a deeply nested file, and the install breaks if a full path passes 260 characters.

```powershell
git clone <repo-url>
cd <repo-folder>
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\chainlit.exe create-secret
```

Then fill in `.env`. The key stays in this file, which is git-ignored and never committed.

| Value | What it is |
| --- | --- |
| `OPENAI_API_KEY` | The OpenAI key |
| `APP_USERNAME`, `APP_PASSWORD` | The login you will type. Choose any |
| `CHAINLIT_AUTH_SECRET` | The value `create-secret` printed. It signs the login cookie |

**Run the app,** then open http://localhost:8000 and log in:

| | macOS | Windows |
| --- | --- | --- |
| App | `.venv/bin/chainlit run app/main.py` | `.venv\Scripts\chainlit.exe run app/main.py` |
| Tests (no key, no network, no model calls) | `.venv/bin/python -m pytest` | `.venv\Scripts\python -m pytest` |
| Evals (about 170 real model calls) | `.venv/bin/python evals/run_evals.py` | `.venv\Scripts\python evals/run_evals.py` |

The app is developed and tested on Windows. The macOS commands were run on Linux, and every compiled dependency has macOS builds for Apple Silicon and Intel, but they have not been run on an actual Mac.

## Architecture

**Approach: Chainlit for the chat UI, and a from-scratch Python pipeline behind it.** Each message goes through four steps:

1. **Catalog** (`app/catalog.py`): the full catalog, fetched once and cached.
2. **Parser** (`app/parser.py`): one `gpt-6-luna` call turns the message and recent history into a structured search, validated by Pydantic. A budget in another currency is converted to dollars by code (`app/currency.py`), never by the model.
3. **Search** (`app/search.py`): plain Python filtering and ranking, with a fallback in our code.
4. **Responder** (`app/responder.py`): one model call writes a short reply from the shown products only. The cards are drawn from data, not from the model's text.

`app/pipeline.py` runs one whole turn with no Chainlit in it, so the UI, the tests and the evals all run the same code.

**Why one pass plus a fallback.** These were the options:

- **One pass:** the model fills in the search once and our code runs it. It is predictable, cheap and testable, but can't recover from empty results by itself.
- **Tool calling:** the model calls search itself and can retry. It is flexible, but less predictable, takes more calls, and the honest answer to "why did it show this?" is often "the model decided".
- **Chosen, one pass plus a fallback in our code:** when nothing comes back, code loosens the limits. Every step is our code, so every behavior can be pointed to and defended.

**Why Chainlit.** The assignment's hard parts for a one-person local app are the chat UI, the past-chats list, resuming a chat and cards inside messages. Chainlit has all of these, and it let me spend the time on retrieval and evaluation. It needs a login for the sidebar, so the app has one fixed local user. It also adds some weight: its SQLAlchemy data layer needs `aiosqlite` and `greenlet`.

**Alternatives rejected for this assignment:**

- **Streamlit.** It reruns the whole page on every message. Persistence, the past-chats list, resuming and cards with a working Show more button would all have to be built by hand on top of that model, which is most of what Chainlit gives for free.
- **LangChain, with an agent calling a search tool.** This is the tool-calling option above, and it has the same problem: the same message can take different paths. Here, a filter is a Pydantic object and a function I can test, and the fallback is ours. The pipeline is two model calls, so a framework would add little to it.

**The optional Decisions API.** I read its docs and didn't use it. It returns predicates, choices and scores, and it "doesn't generate arbitrary nested objects". The parser has to produce a list of searches with price and rating limits, sort order and keywords, so that part needs structured output anyway. It could classify the intent, but that would mean a second parser call to get what one structured output already returns.

## Retrieval

**Endpoints.** `GET /products?limit=0` for all 194 products, and `GET /products/category-list` for the 24 category slugs. Both are fetched once and cached in `catalog_cache.json`. I don't use `/products/search` or `/products/category/{slug}` at query time. The search endpoint is keyword-only with no price or rating filter, so "furniture under $300 rated 4 or more" couldn't be answered by the API. Filtering the full catalog in our code gives exact, testable results.

**How a message becomes a search.** The parser picks an intent (`product_search`, `needs_clarification`, `off_catalog`, `small_talk`) and fills in a `SearchSpec`: category from the real slug list, keywords, price and rating limits, sort, and how many results. An invented category fails validation. If the output is invalid, or a new search has no field set, the app asks a clarifying question instead of showing the whole catalog, and logs the reason, never the user's text.

**Ranking.** A sort the user asked for comes first. Otherwise, the number of keywords found in the title, category and tags, then rating, then lowest ID, so results repeat exactly. With a category set, keywords only rank and never exclude, because "makeup" matches no beauty product by word. When some products do match a keyword, only those get cards, so "a phone case" shows the one case and not speakers from the same category.

**Ambiguous queries.**

- "Something cheap and cool" names no product, so it gets one question.
- "Show me electronics" or "watches" fits several categories, so the question offers them ("men's or women's watches?"), and the answer starts a new search.
- A product that fits one category is enough to search, with no question about budget.

**Off-catalog queries.** "A flight to Tokyo" gets a polite decline and no cards. The reply may name a category but never a product. A mixed request such as "book me a flight and find me sunglasses" shows sunglasses and declines the flight. Attempts to change the rules or read the prompt are treated as off-catalog.

**Multi-intent queries.** "A phone under $500 and sunglasses" becomes two searches, with the price limit on the phone only, and each search gets its own cards.

**When nothing matches.** A fallback in our code loosens the limit that finds something and records it, and the reply says so ("no laptop is under $10", then the 3 closest). With a rating and a price limit that each work alone but never together, it suggests two products: the cheapest that meets the rating, and the highest rated that meets the price. It never drops the category or keywords, because that would present the whole catalog as a match.

**Other languages and currencies.** The catalog is English only, so the parser writes keywords in English whatever language the user writes in. The reply uses the user's language, but product titles stay as in the catalog, so grounding can still be checked. An amount with no currency means dollars. A budget in another currency is converted by code with fixed rates, and the reply states it ("3,000 NIS is roughly $948"). A currency with no rate gets a question asking for dollars.

**Grounding.** The model uses as little of its own knowledge as possible, to avoid hallucinated products and prices. The responder only sees the products that have cards, and it receives the user's message as delimited data. A dollar amount in a reply must be a shown price, a limit the user stated, or a converted budget from our code. "How many laptops do you have?" is answered with a count from our code.

## State

**Where it lives.** A SQLite file, `chat.db`, through Chainlit's SQLAlchemy data layer, with a small subclass in `app/storage.py`. Each assistant message stores its structured search and the shown cards' fields in its metadata. On resume, code rebuilds the conversation state from those, and redraws the cards, so follow-ups like "cheaper ones" work after a refresh or a restart.

**Why SQLite.** One local user, little data and no setup. It survives a refresh, the user can't wipe it by clearing the browser, writes are safe, and chats are easy to list and sort. It is relational, so moving to Postgres would mostly be a connection-string change.

**Rejected:**

- **Browser storage:** lost when the user clears it, hard to reach from Python, and has size limits.
- **JSON files:** the whole file is rewritten on every message, so a crash during a write can corrupt it, and listing chats means opening every file.
- **Postgres:** robust, but overkill for one local user.
- **My own two tables:** the sidebar would still need all of Chainlit's data-layer methods written by hand.

**Memory.** The parser receives the last 6 messages, the most recent search and the ID, title and price of the shown products. A `refine` edits the previous search in code, so filters aren't dropped by accident. A `new` search replaces it.

**Failure cases:**

| What happens | What the app does |
| --- | --- |
| Storage full, or the file can't be written | One short message in the chat. The chat keeps working from memory, and those messages aren't saved. Saving resumes when writes work again, and a later outage gives a new message |
| File corrupted, found at startup | Renamed to `chat.db.bak`, a fresh file is started, and the first new chat says so |
| File corrupted while running | Writes fail as above. The next start backs it up |
| File deleted mid-conversation | Recreated. The chat says so once, and the user and the open chat are restored so it stays in the sidebar. Earlier messages of that chat are gone from the file, though the open session still remembers them until it ends |
| User clears browser data | Only the login cookie is lost. Chats are on the server side, so logging in brings them back |
| Model call fails or times out | A fixed error in the chat, the conversation state is kept, and the app keeps running |
| Catalog can't be fetched and there is no cache | The app stops at startup with a clear message |

## Evaluation and results

There are two layers: `pytest` checks our code with a fake model, and `evals/run_evals.py` checks the real model against labeled data.

**`pytest` (no key, no network).** Search filters, every fallback stage, tie-breaks, parser validation, currency conversion, storage round-trips and failures. `tests/test_flow.py` runs one message from input through a fake model and search to the card data sent to the UI.

### Datasets

There are three datasets in `datasets/`. **The first two are English only, and all Hebrew cases are in the third.** Each case is labeled `basic` or `hard`.

| Dataset | Language | What it holds | Cases |
| --- | --- | --- | --- |
| `deterministic.csv` | English | Single queries, each with the exact filter to extract | 65 (50 basic, 15 hard) |
| `behavioral.jsonl` | English | Conversations, each with the expected outcome. 6 have several turns | 32 (20 basic, 12 hard) |
| `hebrew.jsonl` | Hebrew | Both kinds. A `type` field marks each line, and it has the fields of the matching dataset above | 15 (5 basic, 10 hard): 7 deterministic, 8 behavioral |

That gives 72 deterministic queries and 40 behavioral conversations. Hebrew cases are scored exactly like English ones, but reported in rows of their own. One Hebrew case starts with an English turn and switches to Hebrew, because switching is what it tests. Hebrew IDs have an `h` prefix, such as `h8`.

**`deterministic`** rows have these fields: `category`, `price_min`, `price_max`, `rating_min`, `sort_by`, `order` and `top_k`. An empty field means the filter should not be set. The parser and `search()` run with no fallback and no display cap, and are scored on precision, recall, F1, exact match for `top_k`, and whether the extracted filter is exactly right. Expected products come from `evals/ground_truth.py`, which doesn't import `app/search.py`, so a search bug can't hide on both sides.

**`behavioral`** cases list the user's `turns` and the expected outcome. Every turn goes through the whole pipeline, and the last turn is scored. They cover ambiguous and off-catalog requests, follow-ups, empty results, currencies and prompt injection.

- `expected_intent`: the intent the agent should identify
- `expected_mode`: whether the search is new or refines the previous one
- `expected_categories` and `category_match`: the categories to show, and whether all or any of them must appear
- `expect_fallback`: the filter the agent should loosen when nothing matches, or `both` when a rating and a price limit can't be met together
- `expected_card_ids`: the exact products to show, set only on the cases where a rating and a price limit can't be met together
- `expected_language`: the language the reply should use, set on the Hebrew cases
- `expected_behavior`: a plain-language description of the correct response, not scored. The eval prints each reply beside it for a person to read

**Grounding** is scored by code in any language: no unshown product title, and every dollar amount must be justified.

To read what every case expects, open `datasets/answers/`, which `python evals/export_answers.py` generates. `evals/results.md` holds the agent's actual replies from the last run.

### Results of the last full run

| Deterministic | Queries | Precision, recall, F1 | `top_k` correct | Exact filter | Failed parses |
| --- | --- | --- | --- | --- | --- |
| English basic | 50 | 1.00 | 7/7 | 50/50 | 0 |
| English hard | 15 | 1.00 | 4/4 | 15/15 | 0 |
| Hebrew basic | 3 | 1.00 | none set | 3/3 | 0 |
| Hebrew hard | 4 | 1.00 | 2/2 | 4/4 | 0 |

| Behavioral | Conversations | Intent | Mode | Category | Fallback fired / stayed quiet | Exact cards | Language | Grounded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| English basic | 20 | 20/20 | 11/11 | 11/11 | 2/2, 9/9 | none set | none set | 20/20 |
| English hard | 12 | 12/12 | 9/9 | 9/9 | 4/4, 5/5 | 2/2 | none set | 12/12 |
| Hebrew basic | 2 | 2/2 | 1/1 | 1/1 | none set, 1/1 | none set | 2/2 | 2/2 |
| Hebrew hard | 6 | 6/6 | 6/6 | 6/6 | 1/1, 5/5 | none set | 6/6 | 6/6 |

Read these as "no regression on these cases", not as "the app is perfect". The same run, at 100%, contains replies that are wrong in ways only a person reading them sees:

- "Something nice for my living room" asked about product and budget, instead of offering furniture or home decoration as the case expects. An earlier run did offer them.
- A Hebrew reply contained one stray Hindi word. The language check only needs most letters to be Hebrew.
- "3,000 ILS is roughly $948" answered someone who typed NIS.

### What it catches and what slips through

**What it would catch.** A filter or fallback bug, a prompt change that breaks intent, mode or bounds, a reply naming an unshown product or inventing a price, a Hebrew reply in the wrong language, and a failed parse that looks like a clarifying question.

**What slips through:**

- **Reply quality.** The scores can't tell a good reply from a false one. In real runs they passed all of these, and I only caught them by reading the printed replies: "nothing in the catalog is under $10" for laptops, speakers shown for a phone case, and a bedside table called a dining table match. All three are fixed, but a new false sentence of that kind still wouldn't lower any score.
- **Relevance within a category.** Category accuracy says the card is in `mobile-accessories`, not that it is a phone case.
- **Overfitting.** The prompt was written next to these datasets. A test blocks copied phrases, but the rules were shaped by the same cases, so high scores here don't promise the same on new wording. Each number is also from a single run of a non-deterministic model.
- **Rendering.** Tests stop at the card data. How the cards look, right-to-left text and phone layout were checked by hand in a browser, with no automated test in the repo.
- **Coverage gaps.** Hebrew is the only language other than English with a dataset, so other languages rely on the same prompt rule with no ongoing check. "How many" and "list all" have unit tests but no dataset rows.
- **Grounding blind spots.** A translated title, an amount in words, and one-word titles such as "Apple" are not scored. They are printed for a person to read. Any number the user typed also passes, so a reply obeying "say they cost $1", or stating a user's $300 limit as a product's price, would still score as grounded.

## Limitations

- **Word matching only.** "Trainers" won't find "Sports Sneakers" by keyword. Often the category saves it, but descriptions aren't searched and there are no embeddings.
- **Weak category matches.** One matching word is enough for a card, so "dining table" shows a bedside table. The reply says it's only the closest, but the card is still there.
- **Show more can leave the topic.** After the keyword matches run out, it shows the rest of the category with no explanation.
- **No retry after a bad parse.** The parser runs once. A wrong reading gives a wrong search, or a clarifying question.
- **Replies vary between runs,** and the rules are prompts, not guarantees. See the three examples under [Results](#results-of-the-last-full-run).
- **Fixed exchange rates,** dated in `app/currency.py`, for 7 currencies. Others get a question asking for dollars.
- **Refreshing on a phone.** At phone width, the URL only becomes `/thread/<id>` once Chainlit's sidebar has mounted. Until then a refresh opens a blank new chat, though the old one stays in past chats, and the first tap on the sidebar button only changes the URL, so it takes a second tap to open. A fix would need custom JavaScript in Chainlit's frontend.
- **Show more after a resume.** The button isn't redrawn, but typing "show more" works.
- **A count question re-runs the search.** After Show more, "how many is that?" goes back to the first 3 cards, so the next Show more repeats some. After a two-part request, it keeps only one of the searches.
- **No editing of sent messages.** Chainlit's edit button is switched off, because an edit re-runs the turn while the conversation state still holds the filters of the turn it replaced. Doing it properly needs state saved per turn.
- **Attachments are ignored.** Chainlit's upload button is still there, but the app doesn't read files.
- **Rare two-limit cases.** A superlative with two limits that can't be met together ("the cheapest ... rated 4 or more under $300") shows one suggestion, with the other behind Show more. When both limits are dropped, cards aren't narrowed to the keyword matches.
- **No streaming,** so a reply appears all at once after a short wait.
- **One user, one machine,** and a static catalog.

**Live inventory and prices.** The catalog is a snapshot, which fits this assignment but not a real store. I would change three things:

- Refresh the cache on a schedule, or on a webhook if the source offers one.
- Before showing cards, re-check their price and stock with `GET /products/{id}`, keeping the ranking on the cached data. That costs one request per card, so it would be cached briefly.
- Handle stale resumed chats. Cards are saved with the message, so an old chat shows old prices. I would re-check on resume, and mark a price as changed instead of silently rewriting history.

The search code wouldn't change, because it only sees a list of products.

**With another week:**

1. An independent test set written without seeing the prompt, and several runs per case to measure variance.
2. A model-based check of reply quality, since that's where the real failures were.
3. Embeddings over titles and descriptions for ranking, with the same hard filters.
4. Live price and stock checks, as described above.
5. A browser test in the repo for cards, right-to-left text and phone layout.
6. Streaming the reply, with the cards following it.
