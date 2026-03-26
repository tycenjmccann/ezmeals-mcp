---
name: ezmeals-mcp
description: Meal planning and grocery ordering via EZ Meals. Search 200+ curated recipes, build shopping lists, and create Instacart checkout carts. Use when users want to plan meals, find recipes, get ingredient lists, or order groceries.
---

# EZ Meals — Meal Planning & Grocery Ordering

## What This Does

EZ Meals helps users plan weekly meals and order groceries through any AI assistant. Search 200+ curated recipes, build consolidated shopping lists, and create Instacart checkout carts — all through natural language.

## MCP Server

- **Gateway URL:** `https://ezmeals-mcp-evwbfnpaze.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp`
- **Auth:** OAuth2 client credentials (Cognito)
- **Protocol:** MCP over Streamable HTTP

## Available Tools

### search_recipes
Search the recipe catalog with filters.
- `query` — ingredient or dish name (e.g., "chicken", "tacos")
- `cuisine` — Global Cuisines, Italian, Asian, Indian, American, Latin, Soups & Stews
- `time` — quick (≤30 min), balanced (31-60 min), gourmet (60+ min)
- `dietary` — glutenFree, vegetarian
- `cookMethod` — slowCook, instaPot
- `limit` — max results (default 10)

### browse_cuisines
List all cuisine types with recipe counts. No parameters.

### get_recipe
Get full recipe details by ID. Returns ingredients, instructions, notes, dietary flags, and recommended sides.
- `recipe_id` (required) — from search results

### get_recommended_sides
Get side dishes that pair with a main dish.
- `recipe_id` (required) — the main dish ID

### get_shopping_list
Consolidated grocery list from multiple recipes. Combines duplicates and aggregates quantities.
- `recipe_ids` (required) — comma-separated recipe IDs
- `exclude_categories` — comma-separated (e.g., "Seasonings,Pantry Staples")
- `exclude_ingredients` — comma-separated (e.g., "oil,butter,salt")

### create_instacart_cart
Create an Instacart shopping page. Returns a URL for store selection and checkout. 100,000+ stores.
- `recipe_ids` (required) — comma-separated recipe IDs
- `title` — shopping list title
- `exclude_categories` — categories to skip
- `exclude_ingredients` — ingredients to skip
- `additional_items` — comma-separated extras (e.g., "milk,bread,eggs")

## Common Workflows

### Plan a week of meals
1. Ask user for preferences (cuisine, time, dietary)
2. `search_recipes` with filters
3. Present options, let user choose 3-5 meals
4. `get_recipe` for each to show details
5. `create_instacart_cart` with all recipe IDs

### Quick grocery run
1. User names recipes: "I want to make chicken tacos and spaghetti"
2. `search_recipes` to find each
3. `create_instacart_cart` with both IDs, exclude basics

### Explore and discover
1. `browse_cuisines` to show options
2. `search_recipes` for chosen cuisine
3. `get_recipe` + `get_recommended_sides` for full meal planning

## Example Conversation

**User:** "Find me 3 quick Italian recipes for this week"

**Assistant calls:** `search_recipes(cuisine="Italian", time="quick", limit=5)`

**Assistant:** "Here are 5 quick Italian options: [list]. Which 3 would you like?"

**User:** "The pasta, the chicken parm, and the risotto. Skip the seasonings, I have those."

**Assistant calls:** `create_instacart_cart(recipe_ids="pasta-id,chicken-parm-id,risotto-id", exclude_categories="Seasonings,Pantry Staples", title="Italian Week")`

**Assistant:** "Done! Here's your Instacart cart with 18 ingredients: [link]. Pick your store and checkout when ready."
