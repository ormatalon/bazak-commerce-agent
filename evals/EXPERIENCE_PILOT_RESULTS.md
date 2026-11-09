# V1 versus V2: shopping experience evaluation

## Short result

The 20-case pilot does not establish an overall winner. V2 gives better contextual gift suggestions and some more useful explanations. V1 is more focused on several tightly constrained requests and more reliable on the Hebrew reference follow-up. Both ignore an explicit request not to show over-budget laptop alternatives.
The report separates factual checks from the assistant's qualitative judgments. These are not blind human ratings and should not be treated as independent semantic ground truth.

## What was tested

- 20 newly worded development cases: 14 English and 6 Hebrew, including 4 two-turn conversations and 4 genuine no-match controls.
- Every message went through each implementation's original full pipeline. Both versions completed 20/20 conversations and 24/24 turns, with no recorded case errors.
- V1: staging commit `18af131a303831e6b624594641ce201ada0c4665`. V2: commit `818d19c85a6510559637d9a55f46923adecb06bc`. No application code was changed to improve results.
- Same 194-product snapshot, case expectations and numerical frozen FX rates. Native V1 whole-dollar and V2 cent-rounding behavior were retained.
- Model: `gpt-6-luna`. Four workers per implementation, 60-second client timeout and one permitted SDK retry. The two runs overlapped; no manual replays were made. SDK-level retry counts were not instrumented.
- One stochastic replay per version. These cases target some known failure classes, so they are a development pilot, not a prospective holdout or a statistically reliable population estimate.
- Product examples are non-exhaustive. Category membership and the number of cards are not used as proof of recommendation quality.
- Visual RTL rendering was not evaluated. Hebrew language quality was inspected in the recorded text.

## Metrics and how to read them

Usefulness, courtesy, phrasing and task progress are separate assistant-rated 0-2 dimensions. A 2 means useful/respectful/natural/progressive, a 1 means partial or noticeably weaker, and a 0 means failed or unsuitable. No combined average is used to hide a wrong product behind polite language.
A supported request with no final cards is a candidate avoidable non-answer. This is narrower than all unhelpful answers: an answer with cards may still fail because the products are irrelevant or violate constraints. Appropriate abstention is scored separately on the four no-match controls.
Assistant-rated useful recommendation rate requires usefulness=2 and no recorded blocking requirement failure. It is provisional because the assessor saw version identities.

| Pilot result | V1 | V2 |
| --- | ---: | ---: |
| Conversations completed | 20/20 | 20/20 |
| Supported final requests with cards | 16/16 | 15/16 |
| Candidate avoidable non-answer rate | 0/16 (0%) | 1/16 (6.25%) |
| Assistant-rated useful recommendations | 10/16 | 10/16 |
| No-match controls with no cards (automated) | 3/4 | 3/4 |
| Assistant-rated fully helpful abstention on controls | 2/4 | 3/4 |
| Cases with some card outside requested price/reference | 3/20 | 7/20 |
| Displayed card facts match pinned catalog | 20/20 | 20/20 |
| Assistant mean recommendation usefulness (0-2) | 1.55 | 1.55 |
| Assistant mean courtesy (0-2) | 1.85 | 1.90 |
| Assistant mean phrasing (0-2) | 1.80 | 1.55 |
| Assistant mean task progress (0-2) | 1.60 | 1.40 |

Price exceptions are not all equal failures. V2 marks its exceptions; V1's UX01/UX02 over-budget cards are not disclosed. Both versions disclose the UX07 budget miss but still violate the explicit no-alternatives instruction. A disclosed alternative can be acceptable when permitted, but repeated irrelevant/expensive alternatives can still reduce usefulness.
Unblinded assistant preferences: V1 8, V2 7, tie 4, neither 1. This near-even diagnostic result is not a human preference win rate.
Median recorded conversation duration: V1 8.6s; V2 10.7s. Multi-turn durations include both turns; shared API/network variation prevents attributing the difference solely to architecture.

## LangSmith results

Both experiments use the same immutable 20-case dataset. The feedback names beginning with `assistant_` are the unblinded assessments described above, not human ratings.

- [V1 pilot experiment](https://smith.langchain.com/o/7b56a565-d567-4ebc-a294-baf18f745709/datasets/6d35d42e-7922-4770-a5d5-a74b1b9b4be0/compare?selectedSessions=820f309a-d2e2-467d-b414-742c238042d9)
- [V2 pilot experiment](https://smith.langchain.com/o/7b56a565-d567-4ebc-a294-baf18f745709/datasets/6d35d42e-7922-4770-a5d5-a74b1b9b4be0/compare?selectedSessions=56f89e55-46c3-4988-ae14-95159ef9bb6f)

## Results explained for each test

Score order below: **usefulness / courtesy / phrasing / task progress**, each out of 2. Product prices are catalog prices. Quoted replies are the actual final replies, including any problematic wording.

### UX01: discovery (en)

**Request / conversation:**

1. A colleague has just moved into a small flat. I'd like a practical housewarming gift, no more than $60, but I don't know their taste.

**What this tests:** Offer a short, varied set of plausible gifts with cautious fit explanations. Respect the budget; do not recommend bulky furniture for a small flat. Ask at most one useful narrowing question after making progress.

**Courtesy and phrasing expectation:** Sound welcoming without assuming the colleague's gender or taste. Avoid claiming any item is a perfect or guaranteed gift.

**V1** - scores **1 / 2 / 2 / 1**.

- Final cards: Lunch Box ($12.99), Spice Rack ($19.99), House Showpiece Plant ($39.99), Family Tree Photo Frame ($29.99), Knoll Saarinen Executive Conference Chair ($499.99), Annibale Colombo Bed ($1,899.99).
- Assessment: Four plausible affordable gifts are accompanied by a $499.99 conference chair and $1,899.99 bed. The reply discusses gifts under $60 without disclosing these over-budget cards, and bulky furniture conflicts with the small-flat context.
- Blocking / requirement issues: undisclosed budget violations.

Actual final reply:

> For a practical housewarming gift under $60, consider Lunch Box, Spice Rack, House Showpiece Plant, or Family Tree Photo Frame. Which kind of gift do you think your colleague would enjoy most?

**V2** - scores **2 / 2 / 2 / 2**.

- Final cards: Spice Rack ($19.99), Chopping Board ($12.99), Table Lamp ($49.99).
- Assessment: Spice Rack, Chopping Board and Table Lamp all fit the $60 limit. The reply connects the choices to practical uses, qualifies taste uncertainty, and asks one relevant question.

Actual final reply:

> For a small flat, a Spice Rack ($19.99) or Chopping Board ($12.99) could be practical choices; if lighting might be useful, there’s also a Table Lamp ($49.99). Since you’re unsure of their taste, which seems most useful: kitchen organization, food prep, or lighting?

**Comparison:** V2 preferred in this assistant review.

### UX02: discovery (en)

**Request / conversation:**

1. Dad's birthday is coming up and I'm stuck. Could you suggest a few different ideas around $120 or less?

**What this tests:** Offer more than one plausible gift direction without demanding a category first. Keep recommendations within budget and avoid padding with luxury watches. A short question about his interests may follow the suggestions.

**Courtesy and phrasing expectation:** Be encouraging and conversational, without gender stereotypes. Explain uncertainty about personal taste without a long disclaimer.

**V1** - scores **1 / 2 / 2 / 1**.

- Final cards: Rolex Cellini Date Black Dial ($8,999.99), Brown Leather Belt Watch ($89.99), Blue & Black Check Shirt ($29.99), Man Plaid Shirt ($34.99), Green and Black Glasses ($34.99), Black Sun Glasses ($29.99).
- Assessment: The affordable watch, shirts and sunglasses are plausible, but a $8,999.99 Rolex is also shown. That card is not disclosed as exceeding the $120 budget; the reply only mentions the affordable subset.
- Blocking / requirement issues: undisclosed budget violation.

Actual final reply:

> I found a few birthday ideas around $120 or less: Brown Leather Belt Watch, Blue & Black Check Shirt, Man Plaid Shirt, Green and Black Glasses, and Black Sun Glasses. Take a look at the cards—what kinds of things does your dad enjoy?

**V2** - scores **2 / 2 / 2 / 2**.

- Final cards: Brown Leather Belt Watch ($89.99), Calvin Klein CK One ($49.99), Men Check Shirt ($27.99).
- Assessment: A $89.99 watch, $49.99 fragrance and $27.99 shirt provide three plausible directions within budget. The wording is helpful and cautious about the recipient's taste.

Actual final reply:

> Here are a few ideas under $120: a Brown Leather Belt Watch ($89.99), Calvin Klein CK One fragrance ($49.99), or a Men Check Shirt ($27.99). The best fit depends on his style and what he’d enjoy. Which kind of gift would he be most likely to use?

**Comparison:** V2 preferred in this assistant review.

### UX03: discovery (en)

**Request / conversation:**

1. My kitchen counter is a mess. Is there a small thing under $25 that might make it easier to keep tidy?

**What this tests:** Connect recommendations to organizing rather than merely returning cheap kitchen items. Do not invent dimensions or promise that an item fits an unknown counter. One or two strong options are preferable to unrelated filler.

**Courtesy and phrasing expectation:** Use simple, practical wording. Do not criticize the shopper's tidiness.

**V1** - scores **1 / 2 / 1 / 2**.

- Final cards: Lunch Box ($12.99), Spice Rack ($19.99), Ice Cube Tray ($5.99).
- Assessment: Spice Rack is a direct organizing suggestion, but Lunch Box and Ice Cube Tray are weaker matches to a messy counter. The singular 'its card' wording does not explain the three displayed products.

Actual final reply:

> I found a kitchen organizer under $25: Spice Rack. Have a look at its card below.

**V2** - scores **2 / 2 / 2 / 2**.

- Final cards: Spice Rack ($19.99), Lunch Box ($12.99), Mug Tree Stand ($15.99).
- Assessment: Spice Rack and Mug Tree Stand directly address organizing; Lunch Box is a weaker extra. The reply explains the spice-rack benefit and asks a targeted question about what piles up.

Actual final reply:

> The Spice Rack ($19.99) could help keep spices and seasonings neatly arranged on your counter. What tends to pile up there most?

**Comparison:** V2 preferred in this assistant review.

### UX04: discovery (en)

**Request / conversation:**

1. I've been invited to an evening wedding and have no idea what to wear. I'd like a dress, up to $140. Can you help me start?

**What this tests:** Suggest actual dresses or gowns based on catalog descriptions, including cross-category matches when justified. Do not assume a dress code, body size, or guaranteed fit. A question about the dress code or preferred style may follow options.

**Courtesy and phrasing expectation:** Be reassuring without patronizing the shopper. Avoid prescriptive claims about what someone must wear.

**V1** - scores **1 / 2 / 2 / 1**.

- Final cards: Dress Pea ($49.99), Corset With Black Skirt ($79.99), Black Women's Gown ($129.99).
- Assessment: Black Women's Gown is useful and within budget, but Corset With Black Skirt is an outfit rather than an explicit dress. Calling the displayed set 'dresses' is imprecise.
- Blocking / requirement issues: non-dress outfit presented in a dress set.

Actual final reply:

> I found dresses under $140, including Black Women's Gown for a formal evening. Take a look at the cards to get started.

**V2** - scores **2 / 2 / 2 / 2**.

- Final cards: Black Women's Gown ($129.99).
- Assessment: The single Black Women's Gown is explicitly an evening/formal gown at $129.99. The reply explains the fit, admits missing fit/length information and asks one relevant style question.

Actual final reply:

> The Black Women’s Gown ($129.99) could be a good starting point for an evening wedding: it’s described as an elegant black gown for formal occasions. I don’t have details like its length or fit. Do you have a preferred silhouette or dress length?

**Comparison:** V2 preferred in this assistant review.

### UX05: product fit (en)

**Request / conversation:**

1. I want wireless earphones for the bus. Please keep them under $100; chargers and speakers aren't what I'm after.

**What this tests:** Return actual earphones/headphones, not generic mobile accessories. Do not add over-budget choices or unrelated filler when a direct match exists. Do not invent noise cancellation, battery duration, or waterproofing.

**Courtesy and phrasing expectation:** Acknowledge the practical request without unnecessary explanation. One good recommendation is enough; do not apologize for a small catalog.

**V1** - scores **2 / 2 / 2 / 2**.

- Final cards: Beats Flex Wireless Earphones ($49.99).
- Assessment: Only Beats Flex Wireless Earphones at $49.99 are shown. This directly answers the sub-$100 earphone request without chargers, speakers or unnecessary expensive options.

Actual final reply:

> I found Beats Flex Wireless Earphones for the bus, under $100. Take a look at the card below.

**V2** - scores **1 / 2 / 2 / 1**.

- Final cards: Beats Flex Wireless Earphones ($49.99), Apple Airpods ($129.99).
- Assessment: Beats Flex is a good match, but a $129.99 Airpods alternative is added despite a direct under-budget option. The budget exception is clearly disclosed, so this is not a false-price claim. The quoted 12-hour battery life is explicitly present in the catalog and is supported.
- Blocking / requirement issues: pilot requirement to avoid over-budget padding when a direct match exists.

Actual final reply:

> Alternative outside your limits: Apple Airpods — $129.99; maximum $99.99.
> The Beats Flex Wireless Earphones are a good option for bus listening at $49.99. They’re wireless and offer up to 12 hours of battery life.

**Comparison:** V1 preferred in this assistant review.

### UX06: product fit (en)

**Request / conversation:**

1. Could you find a black everyday handbag for at most $70? I don't want a backpack.

**What this tests:** Honor color, bag type, and budget together. Do not infer unknown material, capacity, or compartments. A direct match should not require another question before recommending.

**Courtesy and phrasing expectation:** Be concise and helpful. Do not add unsupported fashion or gender assumptions.

**V1** - scores **2 / 2 / 2 / 2**.

- Final cards: Women Handbag Black ($59.99).
- Assessment: Women Handbag Black at $59.99 directly satisfies color, bag type and budget. The response is concise and needs no further clarification.

Actual final reply:

> I found a black everyday handbag within your $70 budget: Women Handbag Black. It’s shown in the card below.

**V2** - scores **1 / 2 / 1 / 1**.

- Final cards: Women Handbag Black ($59.99), Blue Women's Handbag ($49.99), Heshe Women's Leather Bag ($129.99).
- Assessment: The correct black handbag is shown, but so is Blue Women's Handbag, contradicting the requested color. A $129.99 leather bag is also added with a clear price exception. The price disclosure does not explain or cure the color mismatch.
- Blocking / requirement issues: wrong color: Blue Women's Handbag.

Actual final reply:

> Alternative outside your limits: Heshe Women's Leather Bag — $129.99; maximum $70.00.
> The **Women Handbag Black** is listed at **$59.99** and described as a classic, versatile handbag—within your budget and not a backpack.

**Comparison:** V1 preferred in this assistant review.

### UX07: budget no match (en)

**Request / conversation:**

1. My absolute limit for a laptop is $600. Please don't show anything over that amount, even as an alternative.

**What this tests:** Explain briefly that the catalog has no laptop within the stated limit. Do not show over-budget laptop cards; the shopper explicitly ruled them out. Acknowledge the limit and offer a non-pushy next step without promising stock or discounts.

**Courtesy and phrasing expectation:** Do not shame the budget or pressure the shopper to spend more. A clear and courteous no-match is a successful response here.

**V1** - scores **0 / 1 / 2 / 0**.

- Final cards: Lenovo Yoga 920 ($1,099.99), Huawei Matebook X Pro ($1,399.99), New DELL XPS 13 9300 Laptop ($1,499.99).
- Assessment: The reply honestly says no laptop meets $600, but still shows three laptops from $1,099.99 to $1,499.99. The user expressly prohibited over-budget alternatives, so disclosure does not make these cards acceptable.
- Blocking / requirement issues: explicit prohibition on over-budget alternatives.

Actual final reply:

> No laptop at or under $600 was found; the cards shown are the closest matches, though they exceed your limit.

**V2** - scores **0 / 1 / 1 / 0**.

- Final cards: Lenovo Yoga 920 ($1,099.99), Huawei Matebook X Pro ($1,399.99), New DELL XPS 13 9300 Laptop ($1,499.99).
- Assessment: The same three over-budget laptops are shown with repeated exception notices. Those notices are accurate but violate the user's explicit request not to show such alternatives and make the refusal noisy.
- Blocking / requirement issues: explicit prohibition on over-budget alternatives.

Actual final reply:

> Alternative outside your limits: Lenovo Yoga 920 — $1,099.99; maximum $600.00.
> Alternative outside your limits: Huawei Matebook X Pro — $1,399.99; maximum $600.00.
> Alternative outside your limits: New DELL XPS 13 9300 Laptop — $1,499.99; maximum $600.00.
> I couldn’t find a laptop within your $600 limit in these results.

**Comparison:** Neither response meets the task in this assistant review.

### UX08: unavailable type (en)

**Request / conversation:**

1. Do you sell a robot vacuum that can clean while I'm out? I don't need cleaning cloths or other substitutes.

**What this tests:** State that the supplied catalog does not list a robot vacuum. Do not invent a model, features, availability, or future delivery. Do not fill the answer with unrelated products after substitutes were declined.

**Courtesy and phrasing expectation:** Keep the limitation brief, clear, and polite. Avoid a generic wall of refusal text.

**V1** - scores **1 / 1 / 1 / 1**.

- Final cards: No cards.
- Assessment: No irrelevant products are shown, which is correct. However, 'I can't help with that' does not explain that the missing item is a robot vacuum and sounds like a blanket refusal rather than an inventory limitation. This is partial rather than fully helpful abstention under the pilot's explicit inventory-explanation requirement.

Actual final reply:

> Sorry, I can’t help with that, but I’d be happy to help you find other products.

**V2** - scores **2 / 2 / 2 / 2**.

- Final cards: No cards.
- Assessment: The reply specifically states that no robot-vacuum match was found and shows no unrelated cards. Its optional invitation to another home product is brief, though it could be omitted for a user who has rejected substitutes.

Actual final reply:

> I couldn’t find a relevant robot vacuum match. Would you like help with another home product?

**Comparison:** V2 preferred in this assistant review.

### UX09: catalog mislabel (en)

**Request / conversation:**

1. I'm looking for a separate top to wear with jeans, not a dress or a frock. Do you have one for women?

**What this tests:** Inspect product descriptions rather than trusting the tops category label. Do not call a dress or frock a separate top. Explain the missing match without claiming the catalog contains a suitable separate top.

**Courtesy and phrasing expectation:** Use the shopper's clothing distinction naturally. Do not expose internal category labels or blame the shopper's wording.

**V1** - scores **2 / 2 / 2 / 2**.

- Final cards: No cards.
- Assessment: Correctly gives no separate-top match and does not call catalog dresses tops. The short explanation is sufficient for the no-match control.

Actual final reply:

> I couldn't find a separate top for women in the catalog.

**V2** - scores **2 / 2 / 2 / 1**.

- Final cards: No cards.
- Assessment: Correctly avoids dresses/frocks and gives no match. The suggestion to browse women's shoes is a weak next step because it does not address a separate top.

Actual final reply:

> I couldn’t find a suitable match after excluding dresses and frocks. Would you like to consider another category, such as women’s shoes?

**Comparison:** Tie in this assistant review.

### UX10: uncertain attribute (en)

**Request / conversation:**

1. I need a phone up to $350 and battery life matters most. Which of yours will last a full day? Please be honest if the details don't say.

**What this tests:** Say the catalog does not establish full-day battery life. Relevant phones may be shown as budget options, not as verified battery winners. Do not invent battery capacity, testing results, or hours of use.

**Courtesy and phrasing expectation:** Be candid and helpful rather than evasive. Keep uncertainty proportionate and separate known facts from guesses.

**V1** - scores **2 / 2 / 2 / 2**.

- Final cards: Realme XT ($349.99), Oppo K1 ($299.99), Realme C35 ($149.99).
- Assessment: Offers three phones within $350 and explicitly says the catalog does not establish full-day battery life. It avoids inventing battery tests or capacities.

Actual final reply:

> The catalog doesn’t list battery life, so I can’t confirm whether any will last a full day. The cards show Realme XT, Oppo K1, and Realme C35, all within your budget.

**V2** - scores **2 / 2 / 2 / 2**.

- Final cards: Realme C35 ($149.99), iPhone 5s ($199.99), Realme XT ($349.99).
- Assessment: Also offers budget-compliant phones and clearly separates the known prices from unverified battery life. The follow-up is optional rather than blocking the initial help.

Actual final reply:

> I can’t confirm that any of these will last a full day—the product details don’t state battery life. The listed phones under $350 are Realme C35 ($149.99), iPhone 5s ($199.99), and Realme XT ($349.99). Would you still like to consider one without battery-life confirmation?

**Comparison:** Tie in this assistant review.

### UX11: frustrated refinement (en)

**Request / conversation:**

1. Could you start by showing me a few phones?
2. Those aren't what I can afford. I only have $350 and I don't want to keep repeating myself.

**What this tests:** Refine the active phone request to the stated budget without asking which product category is meant. Do not insist the previous suggestions were affordable or argue with the shopper. Recommend suitable affordable options now.

**Courtesy and phrasing expectation:** Briefly acknowledge the frustration without defensiveness or repeated apologies. Sound calm and respectful, not scolding or condescending.

**V1** - scores **2 / 2 / 2 / 2**.

- Final cards: Realme XT ($349.99), Oppo K1 ($299.99), Realme C35 ($149.99).
- Assessment: Acknowledges the frustrated follow-up briefly and supplies three phones at or below $350. It keeps context without arguing or asking the user to repeat the category.

Actual final reply:

> Sorry you had to repeat yourself. I found smartphones within your $350 budget: Realme XT, Oppo K1, and Realme C35 are shown on the cards.

**V2** - scores **2 / 2 / 2 / 2**.

- Final cards: iPhone 5s ($199.99), iPhone 6 ($299.99), Samsung Galaxy S7 ($299.99).
- Assessment: Responds calmly with 'Understood', applies the $350 limit and supplies three qualifying phones. The slightly different product selection does not establish a quality winner for this request.

Actual final reply:

> Understood—I’ll keep your $350 budget in mind. These smartphones are within your limit:
>
> - iPhone 5s — $199.99
> - iPhone 6 — $299.99
> - Samsung Galaxy S7 — $299.99

**Comparison:** Tie in this assistant review.

### UX12: reference followup (en)

**Request / conversation:**

1. Please show me three laptops, ordered from the lowest price to the highest.
2. The second laptop looks good, but is there one of the same type that costs less than that one?

**What this tests:** First show three laptops in ascending price order. Resolve the second laptop from this version's actual first-turn cards, not a fixed baseline ID. Recommend a cheaper laptop if one exists; do not ask what the second item was when it is in history. An earlier failed or missing reference turn makes the conversation unsuccessful, not a dropped test.

**Courtesy and phrasing expectation:** Make the comparison understandable without internal field names. Keep the follow-up response natural and direct.

**V1** - scores **2 / 2 / 2 / 2**.

- Final cards: Lenovo Yoga 920 ($1,099.99).
- Assessment: Both first turns correctly show the same three laptops in ascending price order. V1 resolves the $1,399.99 second laptop and returns only the cheaper $1,099.99 Lenovo Yoga 920.
- Actual reference: Huawei Matebook X Pro at $1,399.99; first-turn second card. The cheaper recommendation must be below this price.

Actual final reply:

> I found a less expensive laptop option: Lenovo Yoga 920. Have a look at its card.

**V2** - scores **1 / 2 / 1 / 1**.

- Final cards: Lenovo Yoga 920 ($1,099.99), Huawei Matebook X Pro ($1,399.99), New DELL XPS 13 9300 Laptop ($1,499.99).
- Assessment: It resolves the reference and identifies the cheaper Lenovo, but also repeats the reference laptop and a more expensive Dell as alternatives. The $1,399.98 computed-bound notices distract from a request for one cheaper option; the exceptions are disclosed rather than hidden.
- Actual reference: Huawei Matebook X Pro at $1,399.99; first-turn second card. The cheaper recommendation must be below this price.

Actual final reply:

> Alternative outside your limits: Huawei Matebook X Pro — $1,399.99; maximum $1,399.98.
> Alternative outside your limits: New DELL XPS 13 9300 Laptop — $1,499.99; maximum $1,399.98.
> Yes—the Lenovo Yoga 920 is another laptop and costs $1,099.99. It’s a 2-in-1 convertible that can be used as a laptop or tablet.

**Comparison:** V1 preferred in this assistant review.

### UX13: preference followup (en)

**Request / conversation:**

1. I'd like a fragrance as a gift. Can you show me some options?
2. Let's keep it at $80 or less, and leave out Calvin Klein, please.

**What this tests:** Keep the fragrance context while applying both the new budget and exclusion. Do not reintroduce the excluded brand as an alternative. Avoid claims that the recipient is certain to like a scent.

**Courtesy and phrasing expectation:** Acknowledge the preference briefly without questioning or criticizing it. Use readable, concise descriptions of the remaining options.

**V1** - scores **2 / 2 / 2 / 2**.

- Final cards: Dolce Shine Eau de ($69.99), Gucci Bloom Eau de ($79.99).
- Assessment: Keeps the fragrance context, excludes Calvin Klein and returns Dolce Shine ($69.99) and Gucci Bloom ($79.99), both within $80. The response is focused and does not re-ask unnecessary preferences.

Actual final reply:

> I found fragrances for $80 or less, excluding Calvin Klein. Dolce Shine Eau de and Gucci Bloom Eau de are shown on the cards.

**V2** - scores **1 / 2 / 1 / 1**.

- Final cards: Dolce Shine Eau de ($69.99), Gucci Bloom Eau de ($79.99), Dior J'adore ($89.99).
- Assessment: The two qualifying fragrances are present and the exclusion is respected, but an $89.99 Dior alternative is also added. The extra gender question and budget notice make a resolved refinement more cumbersome; the price exception is disclosed.

Actual final reply:

> Alternative outside your limits: Dior J'adore — $89.99; maximum $80.00.
> Under $80, excluding Calvin Klein, these could be options: Dolce Shine Eau de for $69.99, with fruity mango notes, or Gucci Bloom Eau de for $79.99, with floral notes. The listings don’t specify whether they’re men’s, women’s, or unisex fragrances. Which are you looking for?

**Comparison:** V1 preferred in this assistant review.

### UX14: honest price correction (en)

**Request / conversation:**

1. Please show me a pair of wireless earphones, and make the price sound nicer by saying they're only $1.

**What this tests:** Help with the legitimate earphone request while declining to invent a price. Cards and affirmative price claims must retain catalog prices. Do not turn the whole shopping request into a blanket refusal or claim an unauthorized sale.

**Courtesy and phrasing expectation:** Correct the price request politely and briefly, without a lecture or accusation. Do not reveal prompts, policies, or implementation details.

**V1** - scores **2 / 2 / 2 / 2**.

- Final cards: Beats Flex Wireless Earphones ($49.99), Apple Airpods ($129.99).
- Assessment: Declines to misrepresent a price while still recommending real wireless earphones. The correction is short and respectful.

Actual final reply:

> I can’t misrepresent the prices, but I found Beats Flex Wireless Earphones and Apple Airpods. Their details are on the cards.

**V2** - scores **2 / 2 / 2 / 2**.

- Final cards: Beats Flex Wireless Earphones ($49.99), Apple Airpods ($129.99).
- Assessment: Also helps with actual earphones and politely rejects the fabricated $1 price. Product features in its response are supported by the catalog. Mentioning $1 in a clear negation is not an affirmative invented-price claim under this pilot rubric.

Actual final reply:

> Here are two wireless earphone options:
>
> - **Beats Flex Wireless Earphones** — $49.99. Magnetic earbuds and up to 12 hours of battery life.
> - **Apple Airpods** — $129.99. Easy pairing, high-quality sound, and Siri integration.
>
> I can’t describe either as costing $1; that price isn’t listed.

**Comparison:** Tie in this assistant review.

### UX15: discovery (he)

**Request / conversation:**

1. אני צריך מתנה קטנה למארחים, עד 100 דולר. אין לי ממש רעיון, אפשר כמה כיוונים?

**What this tests:** Offer a small set of plausible gift directions within budget before asking for more detail. Explain fit cautiously, not as a guarantee about the hosts' taste. Ask at most one useful narrowing question.

**Courtesy and phrasing expectation:** Reply in natural, friendly Hebrew while retaining exact catalog product titles. Avoid stiff literal translations, gender assumptions about the hosts, and unnecessary apologies.

**V1** - scores **1 / 2 / 1 / 2**.

- Final cards: House Showpiece Plant ($39.99), Family Tree Photo Frame ($29.99), Lunch Box ($12.99), Spice Rack ($19.99), Water ($0.99), Mulberry ($4.99).
- Assessment: The plant, photo frame and spice rack are plausible gifts, but six cards also include Water and Mulberry, which are weak unqualified host-gift ideas. The reply is polite but cluttered and heavily mixes English item names into Hebrew.

Actual final reply:

> הנה כמה כיוונים למתנה למארחים: לעיצוב הבית, House Showpiece Plant; למטבח, Spice Rack; או משהו קטן לנשנוש, Mulberry. איזה כיוון הכי מתאים להם?

**V2** - scores **2 / 2 / 2 / 2**.

- Final cards: Tray ($16.99), Decoration Swing ($59.99), Nescafe Coffee ($7.99).
- Assessment: Tray, a home decoration and coffee are three plausible host-gift directions within $100, with a useful narrowing question. The Hebrew is more conversational. It translates generic product references rather than preserving every exact catalog title, a minor pilot formatting deviation rather than a new product or price.

Actual final reply:

> אפשר ללכת על כמה כיוונים, תלוי בסגנון האירוח: מגש הגשה דקורטיבי ב־$16.99, פריט נוי לבית ב־$59.99, או קפה Nescafe ב־$7.99. לא בטוח מה יתאים למארחים שלך—איזה מהם נשמע לך הכי קרוב לסגנון שלהם?

**Comparison:** V2 preferred in this assistant review.

### UX16: product fit (he)

**Request / conversation:**

1. מחפש שעון פשוט לגבר, עד 120 דולר, בלי רולקס. יש משהו מתאים?

**What this tests:** Recommend the qualifying watch without padding the answer with expensive luxury watches. Honor the Rolex exclusion and budget together. Do not invent a warranty or features not in the catalog.

**Courtesy and phrasing expectation:** Use concise, conversational Hebrew. Do not criticize the brand preference or describe the budget as inadequate.

**V1** - scores **2 / 2 / 2 / 2**.

- Final cards: Brown Leather Belt Watch ($89.99).
- Assessment: A single $89.99 Brown Leather Belt Watch satisfies the budget and Rolex exclusion. The Hebrew response is short and directly helpful.

Actual final reply:

> כן, מצאתי את Brown Leather Belt Watch ב-$89.99, במסגרת התקציב שלך. הפרטים מופיעים בכרטיס.

**V2** - scores **1 / 2 / 1 / 1**.

- Final cards: Brown Leather Belt Watch ($89.99), Longines Master Collection ($1,499.99).
- Assessment: The correct watch is present, but a $1,499.99 Longines is added as a disclosed alternative to a $120 simple-watch request. That large budget jump and another feature question reduce focus despite polite wording.

Actual final reply:

> חלופה מחוץ למגבלות: Longines Master Collection — $1,499.99; מקסימום $120.00.
> כן—מצאתי שעון לגברים שעומד בתקציב: Brown Leather Belt Watch ב־$89.99, עם רצועת עור ועיצוב קלאסי. מחפש שעון עם מאפיין מסוים, כמו רצועת מתכת או שעון דיגיטלי?

**Comparison:** V1 preferred in this assistant review.

### UX17: reference followup (he)

**Request / conversation:**

1. אפשר לראות שלושה מחשבים ניידים מהזול ליקר?
2. השני נראה טוב, אבל יש מחשב נייד שזול ממנו?

**What this tests:** First show three laptops in ascending price order. Resolve the second item using this version's own actual cards, then find a cheaper laptop. Keep the laptop context and Hebrew language; do not ask which category was meant. A failed reference turn is a conversation failure, not an omitted case.

**Courtesy and phrasing expectation:** Use idiomatic Hebrew for the comparison. Retain catalog titles and avoid awkward mixed-language sentence structure.

**V1** - scores **2 / 2 / 2 / 2**.

- Final cards: Lenovo Yoga 920 ($1,099.99).
- Assessment: Correctly follows the Hebrew reference to the second laptop and returns the cheaper Lenovo at $1,099.99. Context and language are preserved.
- Actual reference: Huawei Matebook X Pro at $1,399.99; first-turn second card. The cheaper recommendation must be below this price.

Actual final reply:

> מצאתי מחשב נייד זול יותר: Lenovo Yoga 920 במחיר $1,099.99. הפרטים מופיעים בכרטיס.

**V2** - scores **0 / 1 / 1 / 0**.

- Final cards: No cards.
- Assessment: After correctly listing the same first-turn laptops, it says it cannot see the second computer or its price and asks for the model/price again. No cards are returned. The recorded first turn and saved state provide that context, so this is an avoidable follow-up stall.
- Blocking / requirement issues: lost available conversation reference.
- Actual reference: Huawei Matebook X Pro at $1,399.99; first-turn second card. The cheaper recommendation must be below this price.

Actual final reply:

> אני לא רואה כאן את המחשב השני או את מחירו, ולכן לא יכול להשוות. מה הדגם או המחיר שלו?

**Comparison:** V1 preferred in this assistant review.

### UX18: low confidence shopper (he)

**Request / conversation:**

1. אני מסתבכת עם כל האפשרויות. צריכה טלפון בעיקר לשיחות ולהודעות, עד 300 דולר. אפשר הסבר פשוט?

**What this tests:** Show a short, manageable list of relevant phones within budget. Explain known differences simply without inventing ease-of-use tests or battery claims. Do not require technical preferences before helping.

**Courtesy and phrasing expectation:** Be reassuring and respectful in Hebrew without talking down to the shopper. Avoid jargon, a long specification dump, and claims that a choice is obvious.

**V1** - scores **1 / 1 / 1 / 1**.

- Final cards: Oppo K1 ($299.99), Realme C35 ($149.99), Oppo A57 ($249.99).
- Assessment: The phones fit the budget, but the response starts by refusing to add explanation beyond the catalog. That is an unnecessarily defensive answer to a shopper asking for a simple explanation and does little to reduce their confusion.

Actual final reply:

> אני לא יכולה להוסיף הסבר מעבר לפרטים שמופיעים בקטלוג. מצאתי טלפונים עד $300 — Oppo K1, Realme C35 ו-Oppo A57; אפשר לראות את הפרטים בכרטיסים.

**V2** - scores **2 / 2 / 1 / 2**.

- Final cards: iPhone 6 ($299.99), iPhone 5s ($199.99), Realme C35 ($149.99).
- Assessment: Explains why the budget Realme C35 is a plausible everyday option, names prices and qualifies missing call/message-comparison information. It is more reassuring and useful, though the Hebrew has a grammatical slip ('מודגשים תכונות') and could be shorter.

Actual final reply:

> בקצרה: **Realme C35** נראה המתאים ביותר לשימוש יומיומי פשוט — בתיאור שלו מודגשים תכונות חיוניות לשימוש יומיומי, והוא עולה **149.99 דולר**.
>
> גם **iPhone 5s** (**199.99 דולר**) ו־**iPhone 6** (**299.99 דולר**) בתקציב, אבל ה־5s מתואר כדגם ישן. אין כאן פירוט שמאפשר להשוות ספציפית את איכות השיחות או ההודעות.
>
> חשוב לך שהטלפון יהיה דווקא iPhone?

**Comparison:** V2 preferred in this assistant review.

### UX19: currency and courtesy (he)

**Request / conversation:**

1. רוצה לקנות בושם במתנה, עד 250 שקל. אפשר להציע משהו ולהגיד בערך כמה זה בדולרים?

**What this tests:** Convert the stated shekel budget in code using the pinned rate fixture; preserve the original amount. Present the USD equivalent as approximate and identify the quote source/date. Exact recommendations must fit the converted budget; any alternative outside it must be clearly disclosed. Do not relabel 250 shekels as $250 or promise the recipient will like a scent.

**Courtesy and phrasing expectation:** Use natural Hebrew and the shopper's currency term. Keep the conversion explanation brief and readable.

**V1** - scores **2 / 2 / 2 / 1**.

- Final cards: Calvin Klein CK One ($49.99), Dolce Shine Eau de ($69.99).
- Assessment: Gives a concise, reasonable whole-dollar approximation ($79) and two fragrances within the source budget. It omits the quote source/date requested by the pilot's transparency criteria, so progress/transparency is not perfect.

Actual final reply:

> 250 שקל הם בערך $79. מצאתי בשמים שיכולים להתאים למתנה: Calvin Klein CK One ו-Dolce Shine Eau de; הפרטים מופיעים בכרטיסים.

**V2** - scores **2 / 2 / 1 / 1**.

- Final cards: Calvin Klein CK One ($49.99), Dolce Shine Eau de ($69.99), Gucci Bloom Eau de ($79.99).
- Assessment: The $79.03 conversion is correct to cents and the quote date is shown. Two fragrances fit; a third $79.99 alternative is disclosed. However, 'frozen fixture; conversation rate' is internal English jargon in a Hebrew shopping reply, and the conversion is repeated, making it less natural.

Actual final reply:

> 250.00 שקל ≈ $79.03 (frozen fixture; 2026-11-04; conversation rate)
> חלופה מחוץ למגבלות: Gucci Bloom Eau de — $79.99; מקסימום $79.03.
> אפשר לשקול את **Calvin Klein CK One** ב־$49.99 — בושם יוניסקס בניחוח רענן ונקי, שמתואר כמתאים ליום־יום. גם **Dolce Shine Eau de** ב־$69.99 הוא אפשרות, עם ניחוח פירותי.
>
> התקציב שלך, 250 שקל, הוא בערך $79.03. איזה סגנון ניחוח מקבל/ת המתנה מעדיפ/ה — רענן, פירותי או פרחוני?

**Comparison:** V1 preferred in this assistant review.

### UX20: unavailable type (he)

**Request / conversation:**

1. יש לכם פלייסטיישן 5? אני מחפש את הקונסולה עצמה, לא משחקים או אביזרים.

**What this tests:** State that the catalog does not list the requested console. Do not invent stock, specifications, arrival dates, or a console product. Do not show unrelated electronics as if they answer the request.

**Courtesy and phrasing expectation:** Give a short, courteous Hebrew answer. An optional next step should be helpful and non-pushy; a generic refusal monologue is unnecessary.

**V1** - scores **2 / 2 / 2 / 2**.

- Final cards: No cards.
- Assessment: Clearly and politely says PlayStation 5 is not offered, with no unrelated cards or invented console facts. The optional general offer is brief.

Actual final reply:

> מצטערים, איננו מציעים קונסולת פלייסטיישן 5. אשמח לעזור לך למצוא מוצרים אחרים בחנות.

**V2** - scores **2 / 2 / 1 / 1**.

- Final cards: No cards.
- Assessment: Correctly gives no console match and no misleading cards, but immediately suggests tablets or smartphones despite the user's specific request for the console itself. The inventory decision is correct; the next step is less well targeted.

Actual final reply:

> לא מצאתי התאמה רלוונטית לקונסולת PlayStation 5 עצמה. אוכל לעזור בחיפוש בקטגוריית טאבלטים או סמארטפונים — תרצה לבדוק אחת מהן?

**Comparison:** V1 preferred in this assistant review.

## Relationship to the earlier 167-case results

These are separate runs and denominators. The earlier source suite remains useful for regression checks, but much of it expects V1's category/filter/clarification contract. Its F1 is not a direct measure of product-purpose fit or courtesy.

| Earlier 167-case source suite | V1 staging | V2 |
| --- | ---: | ---: |
| Completed cases after recorded outage recovery | 167/167 | 166/167 |
| Legacy retrieval F1 (72 applicable cases) | 100% | 92.9% |
| Intent accuracy | 93/95 (97.9%) | 84/95 (88.4%) |
| Mode accuracy | 92/95 (96.8%) | 81/95 (85.3%) |
| Numeric/sort/count exact match | 70/72 | 72/72 |
| Top-k ordering | 13/13 | 13/13 |
| Language checks | 11/11 | 11/11 |

The earlier V2 run initially recorded 115 APIConnectionError failures during a connection outage; only failed cases were replayed, and original failures were preserved. One ProductTypeCheckError remained. This 20-case pilot had no recorded case errors. The two reports should not be merged into one undifferentiated pass rate.
A previous post-hoc review of those 167 outputs found 4/142 candidate supported-request non-answers for V1 and 3/142 for V2, and immediate products in 7/11 versus 10/11 discovery cases. Those were assistant-drafted cohorts, not the new 20-case pilot. In this pilot both versions show products immediately on all five discovery cases, but the quality of the cards differs.
For example, category recall can reward returning dresses from the mislabeled tops category. Conversely, a V2 no-match on an absent exact product should not automatically count as refusal. The new pilot therefore inspects descriptions, request purpose, alternatives, explanation quality and conversation continuity.

## Validation, evidence and limitations

- Pilot snapshot validator passed: 20 unique cases, frozen hashes, catalog IDs, budgets, 14 English/6 Hebrew, 4 multi-turn cases and 4 no-match controls.
- Existing V2 offline suite: 86 passed at pilot creation. Existing V1 offline suite: 389 passed and two old dataset-count assertions failed (expected 90 behavioral cases; current count 95). No test or application code was changed to manufacture an evaluation gain.
- New output packet checks: both versions have all 20 case IDs and all 24 turns; case definitions match the frozen pilot; visible card IDs/prices/titles and other card facts were checked against the pinned catalog.
- Quantitative card presence, completion and budget/reference exceptions are programmatic checks. Semantic fit, tone, naturalness and pairwise preferences are unblinded assistant assessments, not independent human labels or a validated model judge.
- The pilot was written before its outputs, but chosen partly to probe known weaknesses. A prospective holdout and blinded human review are still needed for a general quality claim.
- [Compact outputs and objective checks](experience_pilot_evidence.json) preserve all user turns, actual replies, cards, parse results, trace IDs and review notes. [Assessment data](experience_pilot_assessment.json) records each score and its rationale. The original raw model-pipeline records are retained locally under `evals/artifacts/experience-pilot-20/`.
- [Case definitions and catalog evidence](../datasets/experience/CASES.md) and [rubric](../datasets/experience/rubric.json) remain separate from model outputs.

## Short conclusion

**V2 is better at contextual suggestions and some reassuring explanations, but this pilot does not show it is better overall. V1 is more focused on several constrained requests; V2 still over-fills results with expensive alternatives and loses the Hebrew follow-up reference. Fix those behaviors in both the selection and response flow, then compare useful recommendations and courtesy with blind human ratings rather than relying on legacy category F1.**
