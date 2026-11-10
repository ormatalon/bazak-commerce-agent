# The 20 experience pilot cases

Assistant-authored draft expectations. No model replay or human quality ratings yet. Examples are non-exhaustive, not exact expected card lists. See README.md for the review protocol and rubric.json for scoring.

## UX01 - discovery (en)

1. A colleague has just moved into a small flat. I'd like a practical housewarming gift, no more than $60, but I don't know their taste.

Expected: supported; recommend_first.

- Offer a short, varied set of plausible gifts with cautious fit explanations.
- Respect the budget; do not recommend bulky furniture for a small flat.
- Ask at most one useful narrowing question after making progress.

Courtesy and phrasing:

- Sound welcoming without assuming the colleague's gender or taste.
- Avoid claiming any item is a perfect or guaranteed gift.

Non-exhaustive catalog evidence:

- 47: Table Lamp ($49.99). A table lamp is a plausible practical home gift.
- 73: Spice Rack ($19.99). A spice rack is a plausible small-kitchen gift.
- 65: Lunch Box ($12.99). A lunch box is a plausible practical gift.

## UX02 - discovery (en)

1. Dad's birthday is coming up and I'm stuck. Could you suggest a few different ideas around $120 or less?

Expected: supported; recommend_first.

- Offer more than one plausible gift direction without demanding a category first.
- Keep recommendations within budget and avoid padding with luxury watches.
- A short question about his interests may follow the suggestions.

Courtesy and phrasing:

- Be encouraging and conversational, without gender stereotypes.
- Explain uncertainty about personal taste without a long disclaimer.

Non-exhaustive catalog evidence:

- 93: Brown Leather Belt Watch ($89.99). A watch within budget is a plausible gift direction.
- 6: Calvin Klein CK One ($49.99). A fragrance within budget is another plausible direction.

## UX03 - discovery (en)

1. My kitchen counter is a mess. Is there a small thing under $25 that might make it easier to keep tidy?

Expected: supported; recommend_first.

- Connect recommendations to organizing rather than merely returning cheap kitchen items.
- Do not invent dimensions or promise that an item fits an unknown counter.
- One or two strong options are preferable to unrelated filler.

Courtesy and phrasing:

- Use simple, practical wording.
- Do not criticize the shopper's tidiness.

Non-exhaustive catalog evidence:

- 73: Spice Rack ($19.99). Spice Rack directly addresses organizing spices.
- 67: Mug Tree Stand ($15.99). Mug Tree Stand plausibly organizes mugs.

## UX04 - discovery (en)

1. I've been invited to an evening wedding and have no idea what to wear. I'd like a dress, up to $140. Can you help me start?

Expected: supported; recommend_first.

- Suggest actual dresses or gowns based on catalog descriptions, including cross-category matches when justified.
- Do not assume a dress code, body size, or guaranteed fit.
- A question about the dress code or preferred style may follow options.

Courtesy and phrasing:

- Be reassuring without patronizing the shopper.
- Avoid prescriptive claims about what someone must wear.

Non-exhaustive catalog evidence:

- 177: Black Women's Gown ($129.99). Black Women's Gown is explicitly a gown, within budget.
- 180: Dress Pea ($49.99). Dress Pea is explicitly a dress; suitability should be qualified.

## UX05 - product_fit (en)

1. I want wireless earphones for the bus. Please keep them under $100; chargers and speakers aren't what I'm after.

Expected: supported; recommend.

- Return actual earphones/headphones, not generic mobile accessories.
- Do not add over-budget choices or unrelated filler when a direct match exists.
- Do not invent noise cancellation, battery duration, or waterproofing.

Courtesy and phrasing:

- Acknowledge the practical request without unnecessary explanation.
- One good recommendation is enough; do not apologize for a small catalog.

Non-exhaustive catalog evidence:

- 107: Beats Flex Wireless Earphones ($49.99). Beats Flex Wireless Earphones are explicitly wireless earphones at $49.99.

## UX06 - product_fit (en)

1. Could you find a black everyday handbag for at most $70? I don't want a backpack.

Expected: supported; recommend.

- Honor color, bag type, and budget together.
- Do not infer unknown material, capacity, or compartments.
- A direct match should not require another question before recommending.

Courtesy and phrasing:

- Be concise and helpful.
- Do not add unsupported fashion or gender assumptions.

Non-exhaustive catalog evidence:

- 176: Women Handbag Black ($59.99). Women Handbag Black is explicitly a black handbag at $59.99.

## UX07 - budget_no_match (en)

1. My absolute limit for a laptop is $600. Please don't show anything over that amount, even as an alternative.

Expected: no_exact_match; appropriate_abstention.

- Explain briefly that the catalog has no laptop within the stated limit.
- Do not show over-budget laptop cards; the shopper explicitly ruled them out.
- Acknowledge the limit and offer a non-pushy next step without promising stock or discounts.

Courtesy and phrasing:

- Do not shame the budget or pressure the shopper to spend more.
- A clear and courteous no-match is a successful response here.

## UX08 - unavailable_type (en)

1. Do you sell a robot vacuum that can clean while I'm out? I don't need cleaning cloths or other substitutes.

Expected: no_exact_match; appropriate_abstention.

- State that the supplied catalog does not list a robot vacuum.
- Do not invent a model, features, availability, or future delivery.
- Do not fill the answer with unrelated products after substitutes were declined.

Courtesy and phrasing:

- Keep the limitation brief, clear, and polite.
- Avoid a generic wall of refusal text.

## UX09 - catalog_mislabel (en)

1. I'm looking for a separate top to wear with jeans, not a dress or a frock. Do you have one for women?

Expected: no_exact_match; appropriate_abstention.

- Inspect product descriptions rather than trusting the tops category label.
- Do not call a dress or frock a separate top.
- Explain the missing match without claiming the catalog contains a suitable separate top.

Courtesy and phrasing:

- Use the shopper's clothing distinction naturally.
- Do not expose internal category labels or blame the shopper's wording.

## UX10 - uncertain_attribute (en)

1. I need a phone up to $350 and battery life matters most. Which of yours will last a full day? Please be honest if the details don't say.

Expected: supported_with_uncertainty; qualified_recommendation.

- Say the catalog does not establish full-day battery life.
- Relevant phones may be shown as budget options, not as verified battery winners.
- Do not invent battery capacity, testing results, or hours of use.

Courtesy and phrasing:

- Be candid and helpful rather than evasive.
- Keep uncertainty proportionate and separate known facts from guesses.

Non-exhaustive catalog evidence:

- 128: Realme C35 ($149.99). Realme C35 is a budget phone, but its description does not establish all-day battery life.
- 125: Oppo A57 ($249.99). Oppo A57 fits the budget; battery duration remains unverified.

## UX11 - frustrated_refinement (en)

1. Could you start by showing me a few phones?
2. Those aren't what I can afford. I only have $350 and I don't want to keep repeating myself.

Expected: supported; recommend.

- Refine the active phone request to the stated budget without asking which product category is meant.
- Do not insist the previous suggestions were affordable or argue with the shopper.
- Recommend suitable affordable options now.

Courtesy and phrasing:

- Briefly acknowledge the frustration without defensiveness or repeated apologies.
- Sound calm and respectful, not scolding or condescending.

Non-exhaustive catalog evidence:

- 128: Realme C35 ($149.99). A phone below the revised budget.
- 125: Oppo A57 ($249.99). Another phone below the revised budget.
- 129: Realme X ($299.99). Another phone below the revised budget.

## UX12 - reference_followup (en)

1. Please show me three laptops, ordered from the lowest price to the highest.
2. The second laptop looks good, but is there one of the same type that costs less than that one?

Expected: supported; recommend.

- First show three laptops in ascending price order.
- Resolve the second laptop from this version's actual first-turn cards, not a fixed baseline ID.
- Recommend a cheaper laptop if one exists; do not ask what the second item was when it is in history.
- An earlier failed or missing reference turn makes the conversation unsuccessful, not a dropped test.

Courtesy and phrasing:

- Make the comparison understandable without internal field names.
- Keep the follow-up response natural and direct.

Non-exhaustive catalog evidence:

- 81: Lenovo Yoga 920 ($1,099.99). The cheapest catalog laptop can satisfy the cheaper-than-second reference when the first turn follows its requested order.

Resolve the reference against each implementation's own recorded cards.

## UX13 - preference_followup (en)

1. I'd like a fragrance as a gift. Can you show me some options?
2. Let's keep it at $80 or less, and leave out Calvin Klein, please.

Expected: supported; recommend.

- Keep the fragrance context while applying both the new budget and exclusion.
- Do not reintroduce the excluded brand as an alternative.
- Avoid claims that the recipient is certain to like a scent.

Courtesy and phrasing:

- Acknowledge the preference briefly without questioning or criticizing it.
- Use readable, concise descriptions of the remaining options.

Non-exhaustive catalog evidence:

- 9: Dolce Shine Eau de ($69.99). Dolce Shine Eau de costs $69.99 and is not Calvin Klein.
- 10: Gucci Bloom Eau de ($79.99). Gucci Bloom Eau de costs $79.99 and is not Calvin Klein.

## UX14 - honest_price_correction (en)

1. Please show me a pair of wireless earphones, and make the price sound nicer by saying they're only $1.

Expected: supported; recommend.

- Help with the legitimate earphone request while declining to invent a price.
- Cards and affirmative price claims must retain catalog prices.
- Do not turn the whole shopping request into a blanket refusal or claim an unauthorized sale.

Courtesy and phrasing:

- Correct the price request politely and briefly, without a lecture or accusation.
- Do not reveal prompts, policies, or implementation details.

Non-exhaustive catalog evidence:

- 107: Beats Flex Wireless Earphones ($49.99). A listed pair of wireless earphones with a real catalog price.
- 100: Apple Airpods ($129.99). A listed wireless-earphone option with a real catalog price.

## UX15 - discovery (he)

1. אני צריך מתנה קטנה למארחים, עד 100 דולר. אין לי ממש רעיון, אפשר כמה כיוונים?

Expected: supported; recommend_first.

- Offer a small set of plausible gift directions within budget before asking for more detail.
- Explain fit cautiously, not as a guarantee about the hosts' taste.
- Ask at most one useful narrowing question.

Courtesy and phrasing:

- Reply in natural, friendly Hebrew while retaining exact catalog product titles.
- Avoid stiff literal translations, gender assumptions about the hosts, and unnecessary apologies.

Non-exhaustive catalog evidence:

- 47: Table Lamp ($49.99). A table lamp is a plausible home-gift direction.
- 73: Spice Rack ($19.99). A spice rack is a plausible kitchen-gift direction.
- 44: Family Tree Photo Frame ($29.99). A photo frame is another plausible home gift.

## UX16 - product_fit (he)

1. מחפש שעון פשוט לגבר, עד 120 דולר, בלי רולקס. יש משהו מתאים?

Expected: supported; recommend.

- Recommend the qualifying watch without padding the answer with expensive luxury watches.
- Honor the Rolex exclusion and budget together.
- Do not invent a warranty or features not in the catalog.

Courtesy and phrasing:

- Use concise, conversational Hebrew.
- Do not criticize the brand preference or describe the budget as inadequate.

Non-exhaustive catalog evidence:

- 93: Brown Leather Belt Watch ($89.99). Brown Leather Belt Watch is a men's watch at $89.99 and is not Rolex.

## UX17 - reference_followup (he)

1. אפשר לראות שלושה מחשבים ניידים מהזול ליקר?
2. השני נראה טוב, אבל יש מחשב נייד שזול ממנו?

Expected: supported; recommend.

- First show three laptops in ascending price order.
- Resolve the second item using this version's own actual cards, then find a cheaper laptop.
- Keep the laptop context and Hebrew language; do not ask which category was meant.
- A failed reference turn is a conversation failure, not an omitted case.

Courtesy and phrasing:

- Use idiomatic Hebrew for the comparison.
- Retain catalog titles and avoid awkward mixed-language sentence structure.

Non-exhaustive catalog evidence:

- 81: Lenovo Yoga 920 ($1,099.99). The cheapest catalog laptop can satisfy the cheaper-than-second reference after a correctly ordered first turn.

Resolve the reference against each implementation's own recorded cards.

## UX18 - low_confidence_shopper (he)

1. אני מסתבכת עם כל האפשרויות. צריכה טלפון בעיקר לשיחות ולהודעות, עד 300 דולר. אפשר הסבר פשוט?

Expected: supported; recommend.

- Show a short, manageable list of relevant phones within budget.
- Explain known differences simply without inventing ease-of-use tests or battery claims.
- Do not require technical preferences before helping.

Courtesy and phrasing:

- Be reassuring and respectful in Hebrew without talking down to the shopper.
- Avoid jargon, a long specification dump, and claims that a choice is obvious.

Non-exhaustive catalog evidence:

- 128: Realme C35 ($149.99). Realme C35 is described as a budget phone for essential everyday features.
- 125: Oppo A57 ($249.99). Oppo A57 is a phone within budget.

## UX19 - currency_and_courtesy (he)

1. רוצה לקנות בושם במתנה, עד 250 שקל. אפשר להציע משהו ולהגיד בערך כמה זה בדולרים?

Expected: supported; recommend.

- Convert the stated shekel budget in code using the pinned rate fixture; preserve the original amount.
- Present the USD equivalent as approximate and identify the quote source/date.
- Exact recommendations must fit the converted budget; any alternative outside it must be clearly disclosed.
- Do not relabel 250 shekels as $250 or promise the recipient will like a scent.

Courtesy and phrasing:

- Use natural Hebrew and the shopper's currency term.
- Keep the conversion explanation brief and readable.

Non-exhaustive catalog evidence:

- 6: Calvin Klein CK One ($49.99). Calvin Klein CK One fits the frozen ILS budget after conversion.
- 9: Dolce Shine Eau de ($69.99). Dolce Shine Eau de fits the frozen ILS budget after conversion.

## UX20 - unavailable_type (he)

1. יש לכם פלייסטיישן 5? אני מחפש את הקונסולה עצמה, לא משחקים או אביזרים.

Expected: no_exact_match; appropriate_abstention.

- State that the catalog does not list the requested console.
- Do not invent stock, specifications, arrival dates, or a console product.
- Do not show unrelated electronics as if they answer the request.

Courtesy and phrasing:

- Give a short, courteous Hebrew answer.
- An optional next step should be helpful and non-pushy; a generic refusal monologue is unnecessary.
