---
name: ezmeals-mcp
description: Meal planning and grocery ordering via EZ Meals MCP server. Use when users want to plan meals, find recipes, build shopping lists, or order groceries through Instacart. Activates when conversation involves cooking, recipes, meal prep, grocery shopping, or Instacart.
---

# EZ Meals — Meal Planning & Grocery Ordering

200+ curated recipes with smart grocery ordering via Instacart.

## Tools

- `search_recipes` — query, cuisine, time (quick/balanced/gourmet), dietary (glutenFree/vegetarian), cookMethod (slowCook/instaPot), limit
- `browse_cuisines` — no params, returns cuisine categories with counts
- `get_recipe` — recipe_id → full details, ingredients, instructions, image
- `get_recommended_sides` — recipe_id → paired side dishes
- `get_shopping_list` — recipe_ids, exclude_categories, exclude_ingredients → consolidated grocery list
- `create_instacart_cart` — recipe_ids, title, exclude_categories, exclude_ingredients, additional_items → Instacart checkout URL
- `create_recipe_page` — recipe_id, include_sides, exclude_categories → Instacart page with photo, instructions, and shoppable ingredients

### Authenticated Tools (require login)
- `get_weekly_staples` — auth_token → user's weekly grocery staples list
- `add_weekly_staples` — auth_token, items → add items to weekly staples
- `remove_weekly_staples` — auth_token, items → remove items from weekly staples

## Flow (follow in order — do NOT skip steps)

### Step 1: Narrow Down
Before searching, ask:
- **Cook time**: Quick (≤30 min), Balanced (30-60 min), or Gourmet (60+ min)?
- **Cuisine**: Italian, Asian, Indian, American, Latin, Soups & Stews — or surprise me?
- **Dietary**: Any restrictions? (gluten-free, vegetarian)

If they already said what they want, skip to Step 2.

### Step 2: Present Like a Menu
Use `search_recipes` with their filters, then `get_recommended_sides` for each result. Present each recipe as a complete meal — main + 1-3 top side pairings together, like a restaurant menu:

> **BBQ Chicken** (35 min) — smoky grilled chicken with tangy sauce
> *Sides: Mashed Potatoes · Grilled Vegetables · Caesar Salad*

Show images when returned. If a recipe has more sides than shown, mention "more sides available." Let the user pick a meal the way they'd order at a restaurant: "I'll do the BBQ chicken with mashed potatoes and the salad."

### Step 3: Pantry Staples Check
Before creating the order, ask: "This recipe uses [list spices/staples]. Want me to leave those out of the order since you probably have them?"

If yes: use `exclude_categories: "Seasonings,Pantry Staples"` on the order.

### Step 4: Create the Order
- Single recipe (with or without sides): `create_recipe_page` with `include_sides` or `side_ids`
- Multiple recipes / weekly plan: `create_instacart_cart` (consolidated cart, duplicates auto-merged)

Send the link and you're done.

### Weekly Staples (logged-in users)
If the user mentions weekly groceries, staples, or regular items:
1. Ask them to `login` if they haven't already
2. `get_weekly_staples` to show their saved list
3. They can add/remove items with `add_weekly_staples` / `remove_weekly_staples`
4. Include staples in an Instacart cart using `additional_items` on `create_instacart_cart`

## Rules
- Present mains and sides TOGETHER — never show a main alone then ask about sides separately
- ALWAYS confirm before creating an order
- Show images — they drive engagement
- Be enthusiastic about food — this should feel fun
- "Surprise me" → pick something interesting and explain why
