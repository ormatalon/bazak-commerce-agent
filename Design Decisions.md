# Bazak Assignment – Design Decisions

AI shopping copilot over the DummyJSON Products API. Deadline: Friday, 13 Nov 2026, 23:59. Submit by replying to the Bazak email with a private repo link (invite needed).

## Assumptions (answered by Bazak's CTO, 4 Nov 2026)

1. Login and multi-device sync are out of scope; single local user.
2. The catalog is static; no stock or price changes during a chat. Be ready to discuss how this would handle live inventory and price changes.
3. The UI, including product cards, is in English. The chat supports other languages: users may write in any language and the model replies in it.
4. The app is responsive and works on desktop and mobile browsers.
5. Scope is product discovery only; no cart or checkout.

Question answered: fetching the catalog once, caching it locally, and filtering/ranking in our own code is acceptable. It doesn't need to be production-grade.

Also decided: no streaming. Replies are returned whole, to keep product-card rendering simple. Mention in Known limitations.

## Stack

- Everything in Python.
- UI: **Chainlit**. Built for chat apps: conversation sidebar, history, custom elements for product cards.
- Rejected: **Streamlit**. Reruns the whole page on every message, so persistence, the past-chats list and the cards would all need to be built by hand.
- Model: gpt-6-luna (the only allowed model). API key in a `.env` file that is git-ignored, never committed.

## Retrieval strategy

The model turns each user message into a structured search with two parts:

1. **Intent label:** product search, needs clarification, off-catalog, or small talk. Handles ambiguous ("something cheap and cool") and off-catalog ("a flight to Tokyo") queries.
2. **Search spec:** keywords, category (from DummyJSON's fixed list), min/max price, min rating, sort order. Multi-intent queries return a list of specs.

Grounding rule: the model uses minimal own knowledge and never mentions a product, price or detail that didn't come from the catalog results (avoids hallucination).

Other languages: the catalog is English only, so the model writes search keywords in English whatever language the user writes in. The reply uses the user's language, but product titles stay as in the catalog so grounding can still be checked. Prices stay in dollars; a budget in another currency gets a clarifying question, because we have no exchange rates and the model shouldn't guess one.

### Options considered

- **One-pass:** the model fills the search once and our code runs it. Predictable, cheap, testable, but no recovery from empty results.
- **Tool calling:** the model calls search itself and can retry. Flexible, but less predictable, more calls, and the honest answer is often "the model decided", which is exactly the answer Bazak says they don't want.
- **Chosen: one-pass plus fallback.** Our own code loosens filters (e.g. price, rating) when nothing comes back. Every step is our code, so every behavior can be pointed to and defended.

## Persistence

**Chosen: SQLite** (single local file).

Schema:

- `conversations`: id, title, created\_at
- `messages`: id, conversation\_id, role, text, created\_at, products (JSON string, so cards redraw exactly)

Why:

- Single local user, little data, no setup.
- Survives refresh, and the user can't wipe it by clearing the browser.
- Safe writes; easy to query (list/sort past chats).
- Same relational/SQL model as larger apps, so moving to Postgres later is a migration rather than a redesign, especially through SQLAlchemy (mostly a connection-string change).

Rejected:

- **Browser storage:** lost when the user clears it, hard to reach from Python, size limits. Large apps use it only as a cache.
- **JSON files:** the whole file is rewritten on every message, so a crash mid-write can corrupt it, and listing chats means opening every file.
- **Postgres:** robust, but overkill for one local user.

To handle in the README: storage full, corrupted, or cleared mid-conversation.

## Testing & evaluation

Two layers:

1. **Unit tests with a fake model:** a given structured search returns the right products, and the fallback loosens filters correctly.
2. **Model evaluation (the data-science edge):** a labeled set of \~30–50 queries, each with expected intent, category and price constraints. Metrics:
   - intent accuracy
   - filter correctness (category, price bounds)
   - grounding: every product the bot mentions really came from the results

README must say what this catches (retrieval/parsing regressions) and what slips through (answer quality, UI/visual bugs).

## Eval set A: deterministic queries (50)

Each query has an exact correct answer: the set of product IDs that matches its filter in the cached catalog. A script computes the ground-truth IDs from the filter; we score precision and recall against what the agent returns. Price thresholds are first guesses and must be checked against real catalog prices so each filter actually excludes something.

| # | Query | Ground-truth filter |
| --- | --- | --- |
| 1 | Show me laptops under $1,000 | category=laptops, price<1000 |
| 2 | What smartphones do you have? | category=smartphones |
| 3 | Smartphones under $300 | category=smartphones, price<300 |
| 4 | Tablets | category=tablets |
| 5 | Cheapest tablet | category=tablets, sort price asc, top 1 |
| 6 | Most expensive laptop | category=laptops, sort price desc, top 1 |
| 7 | Perfumes under $50 | category=fragrances, price<50 |
| 8 | All fragrances | category=fragrances |
| 9 | Makeup products | category=beauty |
| 10 | Skin care products rated above 4 | category=skin-care, rating>4 |
| 11 | Furniture | category=furniture |
| 12 | Furniture under $500 | category=furniture, price<500 |
| 13 | Groceries under $5 | category=groceries, price<5 |
| 14 | Home decoration items | category=home-decoration |
| 15 | Kitchen accessories under $20 | category=kitchen-accessories, price<20 |
| 16 | Men's shirts | category=mens-shirts |
| 17 | Men's shoes under $100 | category=mens-shoes, price<100 |
| 18 | Men's watches | category=mens-watches |
| 19 | Women's watches rated 4.5 or more | category=womens-watches, rating>=4.5 |
| 20 | Phone accessories | category=mobile-accessories |
| 21 | Mobile accessories under $30 | category=mobile-accessories, price<30 |
| 22 | Motorcycles | category=motorcycle |
| 23 | Cars | category=vehicle |
| 24 | Cheapest vehicle | category=vehicle, sort price asc, top 1 |
| 25 | Sports accessories | category=sports-accessories |
| 26 | Sports gear under $25 | category=sports-accessories, price<25 |
| 27 | Sunglasses | category=sunglasses |
| 28 | Sunglasses under $50 | category=sunglasses, price<50 |
| 29 | Women's tops | category=tops |
| 30 | Women's bags | category=womens-bags |
| 31 | Women's bags under $100 | category=womens-bags, price<100 |
| 32 | Dresses | category=womens-dresses |
| 33 | Jewellery for women | category=womens-jewellery |
| 34 | Women's shoes | category=womens-shoes |
| 35 | Laptops between $500 and $1,500 | category=laptops, 500<=price<=1500 |
| 36 | Smartphones rated above 4.5 | category=smartphones, rating>4.5 |
| 37 | Top 3 highest-rated fragrances | category=fragrances, sort rating desc, top 3 |
| 38 | Top 5 cheapest groceries | category=groceries, sort price asc, top 5 |
| 39 | Furniture rated 4 or more under $300 | category=furniture, rating>=4, price<300 |
| 40 | Highest-rated tablet | category=tablets, sort rating desc, top 1 |
| 41 | Men's watches over $200 | category=mens-watches, price>200 |
| 42 | Women's watches under $150 | category=womens-watches, price<150 |
| 43 | Kitchen accessories, cheapest first | category=kitchen-accessories, sort price asc |
| 44 | Beauty products under $10 | category=beauty, price<10 |
| 45 | Skin care under $20 | category=skin-care, price<20 |
| 46 | Home decor under $30 | category=home-decoration, price<30 |
| 47 | Women's shoes rated above 4 | category=womens-shoes, rating>4 |
| 48 | Men's shirts under $40 | category=mens-shirts, price<40 |
| 49 | Motorcycles under $10,000 | category=motorcycle, price<10000 |
| 50 | Most expensive sunglasses | category=sunglasses, sort price desc, top 1 |

Metrics: precision, recall (and F1) per query, averaged over the set; exact-match rate for top-1 queries.

## Eval set B: non-deterministic queries (20)

These have no single correct product set. We check the intent label and the structured search, and that every product the bot mentions really came from the results (grounding).

| # | Query | Case | Expected behavior |
| --- | --- | --- | --- |
| 1 | Something cheap and cool | Ambiguous | Intent: needs clarification; asks one question (category or budget) |
| 2 | I need a gift for my wife, she loves perfume | Inferred category | Product search, category=fragrances |
| 3 | Something nice for my living room | Inferred category | Product search, furniture or home-decoration |
| 4 | What should I get for my dad? | Ambiguous | Needs clarification |
| 5 | A flight to Tokyo | Off-catalog | Off-catalog; says so politely, no products shown |
| 6 | Book me a hotel | Off-catalog | Off-catalog, no products |
| 7 | What's the weather today? | Off-catalog | Off-catalog, no products |
| 8 | A laptop and a phone case | Multi-intent | Two searches: laptops + mobile-accessories |
| 9 | Sunglasses and a watch for my husband | Multi-intent | Two searches: sunglasses + mens-watches |
| 10 | Dinner ingredients and a new pan | Multi-intent | Two searches: groceries + kitchen-accessories |
| 11 | Show me phones, then: cheaper ones | Follow-up | Keeps category=smartphones, lowers the max price |
| 12 | Show me laptops, then: only the highest rated | Follow-up | Keeps laptops, adds sort by rating |
| 13 | Dresses, then: what about shoes? | Follow-up | Switches to womens-shoes |
| 14 | Laptops under $10 | Empty result | Fallback loosens price; says it found nothing under $10 |
| 15 | Smartphones rated above 5 | Empty result | Fallback loosens rating; explains |
| 16 | A gaming console | Off-catalog / near miss | No such category; says so, may suggest tablets or laptops |
| 17 | Hi, how are you? | Small talk | Small talk; short reply, invites a product question |
| 18 | Thanks, that's all | Small talk | Polite close, no search |
| 19 | Tell me about the iPhone's battery life | Grounding | Answers only from catalog fields; no invented specs |
| 20 | I want running shoes for my wife | Inferred category | Product search, womens-shoes (maybe sports-accessories) |

Metrics: intent accuracy, category accuracy for inferred cases, grounding rate (share of mentioned products that appear in the results; target 100%).
