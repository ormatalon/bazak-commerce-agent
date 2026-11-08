# Ragas faithfulness results

Run file: `run_20261105_151853_regrouped.jsonl`, judged by gpt-6-luna.

## Summary

| set | cases | no search | scored | no claims | errors | mean faithfulness | below 1.0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| english basic | 20 | 9 | 11 | 0 | 0 | 0.85 | 4 |
| english hard | 12 | 3 | 9 | 0 | 0 | 0.97 | 1 |
| hebrew basic | 2 | 1 | 1 | 0 | 0 | 1.00 | 0 |
| hebrew hard | 6 | 0 | 6 | 0 | 0 | 0.92 | 1 |
| all | 40 | 13 | 27 | 0 | 0 | 0.91 | 6 |

## Cases below 1.0, or with an error

### case 2 [english basic]: 0.80
- user: I need a gift for my wife, she loves perfume
- reply: I found several perfume options that could make a lovely gift for your wife, including Calvin Klein CK One, Chanel Coco Noir Eau De, and Dolce Shine Eau de. Have a look at the cards below.
- unsupported: Several perfume options could make lovely gifts for the wife.
  - judge's reason: The context lists perfume options but does not state that they are suitable gifts or that the shopper has a wife.

### case 9 [english basic]: 0.50
- user: Sunglasses and a watch for my husband
- reply: I found sunglasses and men’s watches for your husband. Take a look at the cards below.
- unsupported: The assistant found sunglasses and men's watches for the husband.
  - judge's reason: The context shows searches for sunglasses and men's watches, but does not say they were intended for a husband.

### case 15 [english basic]: 0.67
- user: Smartphones rated above 5
- reply: No smartphones rated above 5 were found; Realme XT, Samsung Galaxy S8, and Vivo X21 are the closest matches, shown on the cards.
- unsupported: No smartphones with ratings above 5 were found.
  - judge's reason: The context says no products matched the minimum rating of 5.01, but that does not establish that no smartphone had a rating above 5 and below 5.01.

### case 20 [english basic]: 0.33
- user: I want running shoes for my wife
- reply: I couldn’t find running shoes; Calvin Klein Heel Shoes, Golden Shoes Woman, and Red Shoes are the closest products. Please see the cards.
- unsupported: The search did not find running shoes.
  - judge's reason: The context lists five search matches, but does not establish that none of them are running shoes.
- unsupported: Calvin Klein Heel Shoes, Golden Shoes Woman, and Red Shoes are the closest available products to running shoes.
  - judge's reason: These products are shown in the search results, but the context does not say they are the closest available products.

### case 21 [english hard]: 0.75
- user: I need a phone under $500 and a pair of sunglasses for my trip next week
- reply: I found phones under $500 and sunglasses for your trip. Vivo X21 ships in 1-2 business days, and Green and Black Glasses ships overnight; see the cards for these and other options.
- unsupported: The available options include phones priced under $500 and sunglasses for the upcoming trip.
  - judge's reason: The context shows phone options priced below $500 and sunglasses, but it does not say the sunglasses are for an upcoming trip.

### case h13 [hebrew hard]: 0.50
- user: אני מחפש מתנה לאשתי, היא אוהבת בשמים
- reply: מצאתי כמה בשמים שעשויים להתאים למתנה לאשתך. Calvin Klein CK One, Chanel Coco Noir Eau De ו-Dolce Shine Eau de מוצגים בכרטיסים.
- unsupported: כמה בשמים עשויים להתאים כמתנה לאישה שאוהבת בשמים.
  - judge's reason: ההקשר מציין חמישה תוצאות חיפוש בסך הכול ושלושה מוצרים שמוצגים, אך אינו קובע כמה מהם מתאימים כמתנה לאישה שאוהבת בשמים.

## Every case

| case | set | faithfulness |
| --- | --- | --- |
| 1 | english basic | no search |
| 2 | english basic | 0.80 |
| 3 | english basic | no search |
| 4 | english basic | no search |
| 5 | english basic | no search |
| 6 | english basic | no search |
| 7 | english basic | no search |
| 8 | english basic | 1.00 |
| 9 | english basic | 0.50 |
| 10 | english basic | 1.00 |
| 11 | english basic | 1.00 |
| 12 | english basic | 1.00 |
| 13 | english basic | 1.00 |
| 14 | english basic | 1.00 |
| 15 | english basic | 0.67 |
| 16 | english basic | no search |
| 17 | english basic | no search |
| 18 | english basic | no search |
| 19 | english basic | 1.00 |
| 20 | english basic | 0.33 |
| 21 | english hard | 0.75 |
| 22 | english hard | 1.00 |
| 23 | english hard | 1.00 |
| 24 | english hard | 1.00 |
| 25 | english hard | no search |
| 26 | english hard | 1.00 |
| 31 | english hard | 1.00 |
| 32 | english hard | 1.00 |
| 33 | english hard | 1.00 |
| 34 | english hard | no search |
| 35 | english hard | no search |
| 36 | english hard | 1.00 |
| h6 | hebrew basic | no search |
| h7 | hebrew basic | 1.00 |
| h8 | hebrew hard | 1.00 |
| h9 | hebrew hard | 1.00 |
| h10 | hebrew hard | 1.00 |
| h13 | hebrew hard | 0.50 |
| h14 | hebrew hard | 1.00 |
| h15 | hebrew hard | 1.00 |
