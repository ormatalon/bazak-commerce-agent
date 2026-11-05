# Expected answers: deterministic rows

## Row 1 [basic]: Show me laptops under $1000

Filter: category=laptops, price_max=999.99

Expected products: none. The reply should say nothing matches.

Suggestions from the app's fallback (loosened: price):

- #81 Lenovo Yoga 920, $1,099.99, rated 2.86
- #80 Huawei Matebook X Pro, $1,399.99, rated 4.98
- #82 New DELL XPS 13 9300 Laptop, $1,499.99, rated 2.67

## Row 2 [basic]: What smartphones do you have?

Filter: category=smartphones

Expected products (16):

- #130 Realme XT, $349.99, rated 4.58
- #132 Samsung Galaxy S8, $499.99, rated 4.4
- #136 Vivo X21, $499.99, rated 4.26
- #127 Oppo K1, $299.99, rated 4.25
- #128 Realme C35, $149.99, rated 4.2
- #123 iPhone 13 Pro, $1,099.99, rated 4.12
- #125 Oppo A57, $249.99, rated 3.94
- #129 Realme X, $299.99, rated 3.7
- #135 Vivo V9, $299.99, rated 3.6
- #126 Oppo F19 Pro Plus, $399.99, rated 3.51
- #134 Vivo S1, $249.99, rated 3.5
- #122 iPhone 6, $299.99, rated 3.41
- #131 Samsung Galaxy S7, $299.99, rated 3.3
- #133 Samsung Galaxy S10, $699.99, rated 3.06
- #121 iPhone 5s, $199.99, rated 2.83
- #124 iPhone X, $899.99, rated 2.51

## Row 3 [basic]: Smartphones under $300

Filter: category=smartphones, price_max=299.99

Expected products (9):

- #127 Oppo K1, $299.99, rated 4.25
- #128 Realme C35, $149.99, rated 4.2
- #125 Oppo A57, $249.99, rated 3.94
- #129 Realme X, $299.99, rated 3.7
- #135 Vivo V9, $299.99, rated 3.6
- #134 Vivo S1, $249.99, rated 3.5
- #122 iPhone 6, $299.99, rated 3.41
- #131 Samsung Galaxy S7, $299.99, rated 3.3
- #121 iPhone 5s, $199.99, rated 2.83

## Row 4 [basic]: Tablets

Filter: category=tablets

Expected products (3):

- #160 Samsung Galaxy Tab S8 Plus Grey, $599.99, rated 4.68
- #161 Samsung Galaxy Tab White, $349.99, rated 3.72
- #159 iPad Mini 2021 Starlight, $499.99, rated 3.18

## Row 5 [basic]: Cheapest tablet

Filter: category=tablets, sort_by=price, order=asc, top_k=1

Expected products (1):

- #161 Samsung Galaxy Tab White, $349.99, rated 3.72

## Row 6 [basic]: Most expensive laptop

Filter: category=laptops, sort_by=price, order=desc, top_k=1

Expected products (1):

- #78 Apple MacBook Pro 14 Inch Space Grey, $1,999.99, rated 3.65

## Row 7 [basic]: Perfumes under $50

Filter: category=fragrances, price_max=49.99

Expected products (1):

- #6 Calvin Klein CK One, $49.99, rated 4.37

## Row 8 [basic]: All fragrances

Filter: category=fragrances

Expected products (5):

- #6 Calvin Klein CK One, $49.99, rated 4.37
- #7 Chanel Coco Noir Eau De, $129.99, rated 4.26
- #9 Dolce Shine Eau de, $69.99, rated 3.96
- #8 Dior J'adore, $89.99, rated 3.8
- #10 Gucci Bloom Eau de, $79.99, rated 2.74

## Row 9 [basic]: Makeup products

Filter: category=beauty

Expected products (5):

- #3 Powder Canister, $14.99, rated 4.64
- #4 Red Lipstick, $12.99, rated 4.36
- #5 Red Nail Polish, $8.99, rated 4.32
- #2 Eyeshadow Palette with Mirror, $19.99, rated 2.86
- #1 Essence Mascara Lash Princess, $9.99, rated 2.56

## Row 10 [basic]: Skin care products rated above 4

Filter: category=skin-care, rating_min=4.01

Expected products (1):

- #119 Olay Ultra Moisture Shea Butter Body Wash, $12.99, rated 4.51

## Row 11 [basic]: Furniture

Filter: category=furniture

Expected products (5):

- #14 Knoll Saarinen Executive Conference Chair, $499.99, rated 4.88
- #11 Annibale Colombo Bed, $1,899.99, rated 4.77
- #12 Annibale Colombo Sofa, $2,499.99, rated 3.92
- #15 Wooden Bathroom Sink With Mirror, $799.99, rated 3.59
- #13 Bedside Table African Cherry, $299.99, rated 2.87

## Row 12 [basic]: Furniture under $500

Filter: category=furniture, price_max=499.99

Expected products (2):

- #14 Knoll Saarinen Executive Conference Chair, $499.99, rated 4.88
- #13 Bedside Table African Cherry, $299.99, rated 2.87

## Row 13 [basic]: Groceries under $5

Filter: category=groceries, price_max=4.99

Expected products (17):

- #42 Water, $0.99, rated 4.96
- #33 Mulberry, $4.99, rated 4.95
- #30 Kiwi, $2.49, rated 4.93
- #35 Potatoes, $2.29, rated 4.81
- #20 Cooking Oil, $4.99, rated 4.8
- #39 Soft Drinks, $1.99, rated 4.75
- #37 Red Onions, $1.99, rated 4.2
- #16 Apple, $1.99, rated 4.19
- #21 Cucumber, $1.49, rated 4.07
- #29 Juice, $3.99, rated 3.94
- #26 Green Chili Pepper, $0.99, rated 3.66
- #31 Lemon, $0.79, rated 3.53
- #25 Green Bell Pepper, $1.29, rated 3.25
- #40 Strawberry, $3.99, rated 3.08
- #41 Tissue Paper Box, $2.49, rated 2.69
- #32 Milk, $3.49, rated 2.61
- #23 Eggs, $2.99, rated 2.53

## Row 14 [basic]: Home decoration items

Filter: category=home-decoration

Expected products (5):

- #45 House Showpiece Plant, $39.99, rated 4.67
- #44 Family Tree Photo Frame, $29.99, rated 4.53
- #47 Table Lamp, $49.99, rated 3.55
- #43 Decoration Swing, $59.99, rated 3.16
- #46 Plant Pot, $14.99, rated 3.01

## Row 15 [basic]: Kitchen accessories under $20

Filter: category=kitchen-accessories, price_max=19.99

Expected products (23):

- #65 Lunch Box, $12.99, rated 4.93
- #73 Spice Rack, $19.99, rated 4.87
- #62 Ice Cube Tray, $5.99, rated 4.71
- #54 Citrus Squeezer Yellow, $8.99, rated 4.63
- #75 Tray, $16.99, rated 4.62
- #49 Black Aluminium Cup, $5.99, rated 4.46
- #70 Red Tongs, $6.99, rated 4.42
- #77 Yellow Peeler, $5.99, rated 4.24
- #74 Spoon, $4.99, rated 4.03
- #59 Glass, $4.99, rated 4.02
- #50 Black Whisk, $9.99, rated 3.9
- #53 Chopping Board, $12.99, rated 3.7
- #69 Plate, $3.99, rated 3.65
- #72 Slotted Turner, $8.99, rated 3.4
- #48 Bamboo Spatula, $7.99, rated 3.27
- #64 Knife, $14.99, rated 3.26
- #60 Grater Black, $10.99, rated 3.21
- #58 Fork, $3.99, rated 3.11
- #55 Egg Slicer, $6.99, rated 3.09
- #63 Kitchen Sieve, $7.99, rated 3.09
- #57 Fine Mesh Strainer, $9.99, rated 3.04
- #76 Wooden Rolling Pin, $11.99, rated 2.92
- #67 Mug Tree Stand, $15.99, rated 2.64

## Row 16 [basic]: Men's shirts

Filter: category=mens-shirts

Expected products (5):

- #83 Blue & Black Check Shirt, $29.99, rated 3.64
- #85 Man Plaid Shirt, $34.99, rated 3.46
- #84 Gigabyte Aorus Men Tshirt, $24.99, rated 3.18
- #86 Man Short Sleeve Shirt, $19.99, rated 2.9
- #87 Men Check Shirt, $27.99, rated 2.72

## Row 17 [basic]: Men's shoes under $100

Filter: category=mens-shoes, price_max=99.99

Expected products (2):

- #90 Puma Future Rider Trainers, $89.99, rated 4.9
- #89 Nike Baseball Cleats, $79.99, rated 3.88

## Row 18 [basic]: Men's watches

Filter: category=mens-watches

Expected products (6):

- #95 Rolex Cellini Date Black Dial, $8,999.99, rated 4.97
- #93 Brown Leather Belt Watch, $89.99, rated 4.19
- #94 Longines Master Collection, $1,499.99, rated 3.87
- #97 Rolex Datejust, $10,999.99, rated 3.66
- #98 Rolex Submariner Watch, $13,999.99, rated 2.69
- #96 Rolex Cellini Moonphase, $12,999.99, rated 2.58

## Row 19 [basic]: Women's watches rated 4.5 or more

Filter: category=womens-watches, rating_min=4.5

Expected products: none. The reply should say nothing matches.

Suggestions from the app's fallback (loosened: rating):

- #193 Watch Gold for Women, $799.99, rated 4.24
- #191 Rolex Cellini Moonphase, $15,999.99, rated 3.83
- #194 Women's Wrist Watch, $129.99, rated 3.52

## Row 20 [basic]: Phone accessories

Filter: category=mobile-accessories

Expected products (14):

- #99 Amazon Echo Plus, $99.99, rated 4.99
- #103 Apple HomePod Mini Cosmic Grey, $99.99, rated 4.62
- #109 Monopod, $19.99, rated 4.43
- #107 Beats Flex Wireless Earphones, $49.99, rated 4.24
- #100 Apple Airpods, $129.99, rated 4.15
- #104 Apple iPhone Charger, $19.99, rated 4.15
- #111 Selfie Stick Monopod, $12.99, rated 3.88
- #102 Apple Airpower Wireless Charger, $79.99, rated 3.68
- #105 Apple MagSafe Battery Pack, $99.99, rated 3.62
- #108 iPhone 12 Silicone Case with MagSafe Plum, $29.99, rated 3.62
- #110 Selfie Lamp with iPhone, $14.99, rated 3.55
- #101 Apple AirPods Max Silver, $549.99, rated 3.47
- #112 TV Studio Camera Pedestal, $499.99, rated 2.78
- #106 Apple Watch Series 4 Gold, $349.99, rated 2.74

## Row 21 [basic]: Mobile accessories under $30

Filter: category=mobile-accessories, price_max=29.99

Expected products (5):

- #109 Monopod, $19.99, rated 4.43
- #104 Apple iPhone Charger, $19.99, rated 4.15
- #111 Selfie Stick Monopod, $12.99, rated 3.88
- #108 iPhone 12 Silicone Case with MagSafe Plum, $29.99, rated 3.62
- #110 Selfie Lamp with iPhone, $14.99, rated 3.55

## Row 22 [basic]: Motorcycles

Filter: category=motorcycle

Expected products (5):

- #113 Generic Motorcycle, $3,999.99, rated 4.91
- #114 Kawasaki Z800, $8,999.99, rated 3.98
- #117 Sportbike Motorcycle, $7,499.99, rated 3.94
- #115 MotoGP CI.H1, $14,999.99, rated 2.97
- #116 Scooter Motorcycle, $2,999.99, rated 2.53

## Row 23 [basic]: Cars

Filter: category=vehicle

Expected products (5):

- #170 Durango SXT RWD, $36,999.99, rated 4.07
- #167 300 Touring, $28,999.99, rated 4.05
- #171 Pacifica Touring, $31,999.99, rated 3.62
- #169 Dodge Hornet GT Plus, $24,999.99, rated 2.65
- #168 Charger SXT RWD, $32,999.99, rated 2.58

## Row 24 [basic]: Cheapest vehicle

Filter: category=vehicle, sort_by=price, order=asc, top_k=1

Expected products (1):

- #169 Dodge Hornet GT Plus, $24,999.99, rated 2.65

## Row 25 [basic]: Sports accessories

Filter: category=sports-accessories

Expected products (17):

- #137 American Football, $19.99, rated 4.91
- #145 Cricket Wicket, $29.99, rated 4.73
- #144 Cricket Helmet, $44.99, rated 4.69
- #140 Basketball, $14.99, rated 4.66
- #150 Metal Baseball Bat, $29.99, rated 4.66
- #141 Basketball Rim, $39.99, rated 4.6
- #149 Iron Golf, $49.99, rated 4.41
- #148 Golf Ball, $9.99, rated 4.3
- #151 Tennis Ball, $6.99, rated 4.06
- #152 Tennis Racket, $49.99, rated 4.03
- #139 Baseball Glove, $24.99, rated 3.96
- #153 Volleyball, $11.99, rated 3.84
- #142 Cricket Ball, $12.99, rated 3.53
- #147 Football, $17.99, rated 3.28
- #143 Cricket Bat, $29.99, rated 3.17
- #146 Feather Shuttlecock, $5.99, rated 2.85
- #138 Baseball Ball, $8.99, rated 2.57

## Row 26 [basic]: Sports gear under $25

Filter: category=sports-accessories, price_max=24.99

Expected products (10):

- #137 American Football, $19.99, rated 4.91
- #140 Basketball, $14.99, rated 4.66
- #148 Golf Ball, $9.99, rated 4.3
- #151 Tennis Ball, $6.99, rated 4.06
- #139 Baseball Glove, $24.99, rated 3.96
- #153 Volleyball, $11.99, rated 3.84
- #142 Cricket Ball, $12.99, rated 3.53
- #147 Football, $17.99, rated 3.28
- #146 Feather Shuttlecock, $5.99, rated 2.85
- #138 Baseball Ball, $8.99, rated 2.57

## Row 27 [basic]: Sunglasses

Filter: category=sunglasses

Expected products (5):

- #156 Green and Black Glasses, $34.99, rated 4.55
- #154 Black Sun Glasses, $29.99, rated 4.41
- #155 Classic Sun Glasses, $24.99, rated 3.86
- #158 Sunglasses, $22.99, rated 3.02
- #157 Party Glasses, $19.99, rated 2.79

## Row 28 [basic]: Sunglasses under $50

Filter: category=sunglasses, price_max=49.99

Expected products (5):

- #156 Green and Black Glasses, $34.99, rated 4.55
- #154 Black Sun Glasses, $29.99, rated 4.41
- #155 Classic Sun Glasses, $24.99, rated 3.86
- #158 Sunglasses, $22.99, rated 3.02
- #157 Party Glasses, $19.99, rated 2.79

## Row 29 [basic]: Women's tops

Filter: category=tops

Expected products (5):

- #163 Girl Summer Dress, $19.99, rated 4.77
- #162 Blue Frock, $29.99, rated 4.17
- #166 Tartan Dress, $39.99, rated 4.05
- #165 Short Frock, $24.99, rated 3.23
- #164 Gray Dress, $34.99, rated 2.72

## Row 30 [basic]: Women's bags

Filter: category=womens-bags

Expected products (5):

- #173 Heshe Women's Leather Bag, $129.99, rated 4.92
- #175 White Faux Leather Backpack, $39.99, rated 3.36
- #172 Blue Women's Handbag, $49.99, rated 2.92
- #176 Women Handbag Black, $59.99, rated 2.89
- #174 Prada Women Bag, $599.99, rated 2.71

## Row 31 [basic]: Women's bags under $100

Filter: category=womens-bags, price_max=99.99

Expected products (3):

- #175 White Faux Leather Backpack, $39.99, rated 3.36
- #172 Blue Women's Handbag, $49.99, rated 2.92
- #176 Women Handbag Black, $59.99, rated 2.89

## Row 32 [basic]: Dresses

Filter: category=womens-dresses

Expected products (5):

- #180 Dress Pea, $49.99, rated 4.88
- #179 Corset With Black Skirt, $79.99, rated 4.52
- #181 Marni Red & Black Suit, $179.99, rated 4.48
- #177 Black Women's Gown, $129.99, rated 3.64
- #178 Corset Leather With Skirt, $89.99, rated 3.05

## Row 33 [basic]: Jewellery for women

Filter: category=womens-jewellery

Expected products (3):

- #184 Tropical Earring, $19.99, rated 4.4
- #182 Green Crystal Earring, $29.99, rated 3.96
- #183 Green Oval Earring, $24.99, rated 3.57

## Row 34 [basic]: Women's shoes

Filter: category=womens-shoes

Expected products (5):

- #186 Calvin Klein Heel Shoes, $79.99, rated 4.92
- #187 Golden Shoes Woman, $49.99, rated 3.26
- #189 Red Shoes, $34.99, rated 3.25
- #188 Pampi Shoes, $29.99, rated 3.05
- #185 Black & Brown Slipper, $19.99, rated 2.53

## Row 35 [basic]: Laptops between $500 and $1500

Filter: category=laptops, price_min=500.0, price_max=1500.0

Expected products (3):

- #80 Huawei Matebook X Pro, $1,399.99, rated 4.98
- #81 Lenovo Yoga 920, $1,099.99, rated 2.86
- #82 New DELL XPS 13 9300 Laptop, $1,499.99, rated 2.67

## Row 36 [basic]: Smartphones rated above 4.5

Filter: category=smartphones, rating_min=4.51

Expected products (1):

- #130 Realme XT, $349.99, rated 4.58

## Row 37 [basic]: Top 3 highest-rated fragrances

Filter: category=fragrances, sort_by=rating, order=desc, top_k=3

Expected products (3):

- #6 Calvin Klein CK One, $49.99, rated 4.37
- #7 Chanel Coco Noir Eau De, $129.99, rated 4.26
- #9 Dolce Shine Eau de, $69.99, rated 3.96

## Row 38 [basic]: Top 5 cheapest groceries

Filter: category=groceries, sort_by=price, order=asc, top_k=5

Expected products (5):

- #31 Lemon, $0.79, rated 3.53
- #26 Green Chili Pepper, $0.99, rated 3.66
- #42 Water, $0.99, rated 4.96
- #25 Green Bell Pepper, $1.29, rated 3.25
- #21 Cucumber, $1.49, rated 4.07

## Row 39 [basic]: Furniture rated 4 or more under $300

Filter: category=furniture, price_max=299.99, rating_min=4.0

Expected products: none. The reply should say nothing matches.

Suggestions from the app's fallback (loosened: rating, price):

- #14 Knoll Saarinen Executive Conference Chair, $499.99, rated 4.88
- #13 Bedside Table African Cherry, $299.99, rated 2.87

## Row 40 [basic]: Highest-rated tablet

Filter: category=tablets, sort_by=rating, order=desc, top_k=1

Expected products (1):

- #160 Samsung Galaxy Tab S8 Plus Grey, $599.99, rated 4.68

## Row 41 [basic]: Men's watches over $200

Filter: category=mens-watches, price_min=200.01

Expected products (5):

- #95 Rolex Cellini Date Black Dial, $8,999.99, rated 4.97
- #94 Longines Master Collection, $1,499.99, rated 3.87
- #97 Rolex Datejust, $10,999.99, rated 3.66
- #98 Rolex Submariner Watch, $13,999.99, rated 2.69
- #96 Rolex Cellini Moonphase, $12,999.99, rated 2.58

## Row 42 [basic]: Women's watches under $150

Filter: category=womens-watches, price_max=149.99

Expected products (1):

- #194 Women's Wrist Watch, $129.99, rated 3.52

## Row 43 [basic]: Kitchen accessories, cheapest first

Filter: category=kitchen-accessories, sort_by=price, order=asc

Expected products (30):

- #58 Fork, $3.99, rated 3.11
- #69 Plate, $3.99, rated 3.65
- #59 Glass, $4.99, rated 4.02
- #74 Spoon, $4.99, rated 4.03
- #49 Black Aluminium Cup, $5.99, rated 4.46
- #62 Ice Cube Tray, $5.99, rated 4.71
- #77 Yellow Peeler, $5.99, rated 4.24
- #55 Egg Slicer, $6.99, rated 3.09
- #70 Red Tongs, $6.99, rated 4.42
- #48 Bamboo Spatula, $7.99, rated 3.27
- #63 Kitchen Sieve, $7.99, rated 3.09
- #54 Citrus Squeezer Yellow, $8.99, rated 4.63
- #72 Slotted Turner, $8.99, rated 3.4
- #50 Black Whisk, $9.99, rated 3.9
- #57 Fine Mesh Strainer, $9.99, rated 3.04
- #60 Grater Black, $10.99, rated 3.21
- #76 Wooden Rolling Pin, $11.99, rated 2.92
- #53 Chopping Board, $12.99, rated 3.7
- #65 Lunch Box, $12.99, rated 4.93
- #64 Knife, $14.99, rated 3.26
- #67 Mug Tree Stand, $15.99, rated 2.64
- #75 Tray, $16.99, rated 4.62
- #73 Spice Rack, $19.99, rated 4.87
- #68 Pan, $24.99, rated 2.79
- #52 Carbon Steel Wok, $29.99, rated 4.05
- #61 Hand Blender, $34.99, rated 3.86
- #51 Boxed Blender, $39.99, rated 4.56
- #71 Silver Pot With Glass Cap, $39.99, rated 3.22
- #56 Electric Stove, $49.99, rated 4.11
- #66 Microwave Oven, $89.99, rated 4.82

## Row 44 [basic]: Beauty products under $10

Filter: category=beauty, price_max=9.99

Expected products (2):

- #5 Red Nail Polish, $8.99, rated 4.32
- #1 Essence Mascara Lash Princess, $9.99, rated 2.56

## Row 45 [basic]: Skin care under $20

Filter: category=skin-care, price_max=19.99

Expected products (3):

- #119 Olay Ultra Moisture Shea Butter Body Wash, $12.99, rated 4.51
- #118 Attitude Super Leaves Hand Soap, $8.99, rated 3.19
- #120 Vaseline Men Body and Face Lotion, $9.99, rated 3.16

## Row 46 [basic]: Home decor under $30

Filter: category=home-decoration, price_max=29.99

Expected products (2):

- #44 Family Tree Photo Frame, $29.99, rated 4.53
- #46 Plant Pot, $14.99, rated 3.01

## Row 47 [basic]: Women's shoes rated above 4

Filter: category=womens-shoes, rating_min=4.01

Expected products (1):

- #186 Calvin Klein Heel Shoes, $79.99, rated 4.92

## Row 48 [basic]: Men's shirts under $40

Filter: category=mens-shirts, price_max=39.99

Expected products (5):

- #83 Blue & Black Check Shirt, $29.99, rated 3.64
- #85 Man Plaid Shirt, $34.99, rated 3.46
- #84 Gigabyte Aorus Men Tshirt, $24.99, rated 3.18
- #86 Man Short Sleeve Shirt, $19.99, rated 2.9
- #87 Men Check Shirt, $27.99, rated 2.72

## Row 49 [basic]: Motorcycles under $10000

Filter: category=motorcycle, price_max=9999.99

Expected products (4):

- #113 Generic Motorcycle, $3,999.99, rated 4.91
- #114 Kawasaki Z800, $8,999.99, rated 3.98
- #117 Sportbike Motorcycle, $7,499.99, rated 3.94
- #116 Scooter Motorcycle, $2,999.99, rated 2.53

## Row 50 [basic]: Most expensive sunglasses

Filter: category=sunglasses, sort_by=price, order=desc, top_k=1

Expected products (1):

- #156 Green and Black Glasses, $34.99, rated 4.55

## Row 51 [hard]: My laptop just died and I've got about a grand to spend. What can I get without going over?

Filter: category=laptops, price_max=1000.0

Expected products: none. The reply should say nothing matches.

Suggestions from the app's fallback (loosened: price):

- #81 Lenovo Yoga 920, $1,099.99, rated 2.86
- #80 Huawei Matebook X Pro, $1,399.99, rated 4.98
- #82 New DELL XPS 13 9300 Laptop, $1,499.99, rated 2.67

## Row 52 [hard]: I'm after a new phone, nothing above three hundred bucks

Filter: category=smartphones, price_max=300.0

Expected products (9):

- #127 Oppo K1, $299.99, rated 4.25
- #128 Realme C35, $149.99, rated 4.2
- #125 Oppo A57, $249.99, rated 3.94
- #129 Realme X, $299.99, rated 3.7
- #135 Vivo V9, $299.99, rated 3.6
- #134 Vivo S1, $249.99, rated 3.5
- #122 iPhone 6, $299.99, rated 3.41
- #131 Samsung Galaxy S7, $299.99, rated 3.3
- #121 iPhone 5s, $199.99, rated 2.83

## Row 53 [hard]: Looking for a fragrance for my girlfriend, budget is tight, under fifty dollars please

Filter: category=fragrances, price_max=49.99

Expected products (1):

- #6 Calvin Klein CK One, $49.99, rated 4.37

## Row 54 [hard]: What's the single cheapest thing you've got for the kitchen?

Filter: category=kitchen-accessories, sort_by=price, order=asc, top_k=1

Expected products (1):

- #58 Fork, $3.99, rated 3.11

## Row 55 [hard]: I want a watch for myself (I'm a guy), but only ones people really like, 4.5 stars and up

Filter: category=mens-watches, rating_min=4.5

Expected products (1):

- #95 Rolex Cellini Date Black Dial, $8,999.99, rated 4.97

## Row 56 [hard]: can u show me sunglases under 50$

Filter: category=sunglasses, price_max=49.99

Expected products (5):

- #156 Green and Black Glasses, $34.99, rated 4.55
- #154 Black Sun Glasses, $29.99, rated 4.41
- #155 Classic Sun Glasses, $24.99, rated 3.86
- #158 Sunglasses, $22.99, rated 3.02
- #157 Party Glasses, $19.99, rated 2.79

## Row 57 [hard]: Need some food items, the cheaper the better. Just give me the 3 cheapest

Filter: category=groceries, sort_by=price, order=asc, top_k=3

Expected products (3):

- #31 Lemon, $0.79, rated 3.53
- #26 Green Chili Pepper, $0.99, rated 3.66
- #42 Water, $0.99, rated 4.96

## Row 58 [hard]: I'm furnishing a new apartment. Show me furniture between two hundred and eight hundred dollars

Filter: category=furniture, price_min=200.0, price_max=800.0

Expected products (3):

- #14 Knoll Saarinen Executive Conference Chair, $499.99, rated 4.88
- #15 Wooden Bathroom Sink With Mirror, $799.99, rated 3.59
- #13 Bedside Table African Cherry, $299.99, rated 2.87

## Row 59 [hard]: Any tablet recommendations? I care more about ratings than price, give me the top 2

Filter: category=tablets, sort_by=rating, order=desc, top_k=2

Expected products (2):

- #160 Samsung Galaxy Tab S8 Plus Grey, $599.99, rated 4.68
- #161 Samsung Galaxy Tab White, $349.99, rated 3.72

## Row 60 [hard]: Not motorcycle gear, an actual motorcycle, under 10k

Filter: category=motorcycle, price_max=9999.99

Expected products (4):

- #113 Generic Motorcycle, $3,999.99, rated 4.91
- #114 Kawasaki Z800, $8,999.99, rated 3.98
- #117 Sportbike Motorcycle, $7,499.99, rated 3.94
- #116 Scooter Motorcycle, $2,999.99, rated 2.53

## Row 61 [hard]: Shoes for women, but only highly rated ones, above 4 stars, and nothing over $100

Filter: category=womens-shoes, price_max=100.0, rating_min=4.01

Expected products (1):

- #186 Calvin Klein Heel Shoes, $79.99, rated 4.92

## Row 62 [hard]: I don't want a laptop, I want a tablet. What's the most expensive one you have?

Filter: category=tablets, sort_by=price, order=desc, top_k=1

Expected products (1):

- #160 Samsung Galaxy Tab S8 Plus Grey, $599.99, rated 4.68

## Row 63 [hard]: My skin's been really dry lately, any skin care stuff under twenty bucks rated at least 4?

Filter: category=skin-care, price_max=19.99, rating_min=4.0

Expected products (1):

- #119 Olay Ultra Moisture Shea Butter Body Wash, $12.99, rated 4.51

## Row 64 [hard]: Show me men's shoes, sorted from cheapest to most expensive

Filter: category=mens-shoes, sort_by=price, order=asc

Expected products (5):

- #89 Nike Baseball Cleats, $79.99, rated 3.88
- #90 Puma Future Rider Trainers, $89.99, rated 4.9
- #92 Sports Sneakers Off White Red, $109.99, rated 4.69
- #91 Sports Sneakers Off White & Red, $119.99, rated 4.77
- #88 Nike Air Jordan 1 Red And Black, $149.99, rated 4.77

## Row 65 [hard]: Gift idea for my mom: a handbag, budget somewhere between $50 and $150

Filter: category=womens-bags, price_min=50.0, price_max=150.0

Expected products (2):

- #173 Heshe Women's Leather Bag, $129.99, rated 4.92
- #176 Women Handbag Black, $59.99, rated 2.89

## Row 66 [hard]: מחשבים ניידים עד 1500 דולר

Filter: category=laptops, price_max=1500.0

Expected products (3):

- #80 Huawei Matebook X Pro, $1,399.99, rated 4.98
- #81 Lenovo Yoga 920, $1,099.99, rated 2.86
- #82 New DELL XPS 13 9300 Laptop, $1,499.99, rated 2.67

## Row 67 [hard]: Busco gafas de sol por menos de 30 dólares

Filter: category=sunglasses, price_max=29.99

Expected products (4):

- #154 Black Sun Glasses, $29.99, rated 4.41
- #155 Classic Sun Glasses, $24.99, rated 3.86
- #158 Sunglasses, $22.99, rated 3.02
- #157 Party Glasses, $19.99, rated 2.79

## Row 68 [hard]: הטאבלט הכי זול שיש לכם

Filter: category=tablets, sort_by=price, order=asc, top_k=1

Expected products (1):

- #161 Samsung Galaxy Tab White, $349.99, rated 3.72

## Row 69 [hard]: Muéstrame los 3 perfumes mejor valorados

Filter: category=fragrances, sort_by=rating, order=desc, top_k=3

Expected products (3):

- #6 Calvin Klein CK One, $49.99, rated 4.37
- #7 Chanel Coco Noir Eau De, $129.99, rated 4.26
- #9 Dolce Shine Eau de, $69.99, rated 3.96

## Row h1 [basic]: שעוני נשים מתחת ל-1000 דולר

Filter: category=womens-watches, price_max=999.99

Expected products (2):

- #193 Watch Gold for Women, $799.99, rated 4.24
- #194 Women's Wrist Watch, $129.99, rated 3.52

## Row h2 [basic]: תיקים לנשים בין 50 ל-150 דולר

Filter: category=womens-bags, price_min=50.0, price_max=150.0

Expected products (2):

- #173 Heshe Women's Leather Bag, $129.99, rated 4.92
- #176 Women Handbag Black, $59.99, rated 2.89

## Row h3 [basic]: משקפי שמש עם דירוג מעל 4 כוכבים

Filter: category=sunglasses, rating_min=4.01

Expected products (2):

- #156 Green and Black Glasses, $34.99, rated 4.55
- #154 Black Sun Glasses, $29.99, rated 4.41

## Row h4 [hard]: שלושת הרהיטים הכי יקרים שיש לכם

Filter: category=furniture, sort_by=price, order=desc, top_k=3

Expected products (3):

- #12 Annibale Colombo Sofa, $2,499.99, rated 3.92
- #11 Annibale Colombo Bed, $1,899.99, rated 4.77
- #15 Wooden Bathroom Sink With Mirror, $799.99, rated 3.59

## Row h5 [hard]: טלפונים עד אלף דולר, מהזול ליקר

Filter: category=smartphones, price_max=1000.0, sort_by=price, order=asc

Expected products (15):

- #128 Realme C35, $149.99, rated 4.2
- #121 iPhone 5s, $199.99, rated 2.83
- #125 Oppo A57, $249.99, rated 3.94
- #134 Vivo S1, $249.99, rated 3.5
- #122 iPhone 6, $299.99, rated 3.41
- #127 Oppo K1, $299.99, rated 4.25
- #129 Realme X, $299.99, rated 3.7
- #131 Samsung Galaxy S7, $299.99, rated 3.3
- #135 Vivo V9, $299.99, rated 3.6
- #130 Realme XT, $349.99, rated 4.58
- #126 Oppo F19 Pro Plus, $399.99, rated 3.51
- #132 Samsung Galaxy S8, $499.99, rated 4.4
- #136 Vivo X21, $499.99, rated 4.26
- #133 Samsung Galaxy S10, $699.99, rated 3.06
- #124 iPhone X, $899.99, rated 2.51
