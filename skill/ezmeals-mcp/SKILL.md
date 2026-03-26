---
name: ezmeals-mcp
description: Meal planning and grocery ordering via EZ Meals MCP server. Use when users want to plan meals, find recipes, build shopping lists, or order groceries through Instacart. Activates when conversation involves cooking, recipes, meal prep, grocery shopping, or Instacart.
---

# EZ Meals MCP Server

Connect to 200+ curated recipes with smart grocery ordering via Instacart.

```
URL: https://ezmeals-public-8cgrhnbvcs.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp
Transport: Streamable HTTP
Auth: None
```

## Tools

- `search_recipes` — query, cuisine, time (quick/balanced/gourmet), dietary (glutenFree/vegetarian), cookMethod (slowCook/instaPot), limit
- `browse_cuisines` — no params, returns cuisine categories with counts
- `get_recipe` — recipe_id → full details, ingredients, instructions, image
- `get_recommended_sides` — recipe_id → paired side dishes
- `get_shopping_list` — recipe_ids, exclude_categories, exclude_ingredients → consolidated grocery list
- `create_instacart_cart` — recipe_ids, title, exclude_categories, exclude_ingredients, additional_items → Instacart checkout URL
- `create_recipe_page` — recipe_id, include_sides, exclude_categories → Instacart page with photo, instructions, and shoppable ingredients

## Behavior

1. Ask preferences before searching — cuisine, time constraints, dietary needs
2. Always ask if the user wants to skip seasonings and pantry staples, then use `exclude_categories: "Seasonings,Pantry Staples"` accordingly
3. Show recipe images when returned — they drive engagement
4. Suggest side dishes after showing a main with `get_recommended_sides`
5. End with a checkout link — use `create_recipe_page` for single recipes, `create_instacart_cart` for multi-recipe plans
6. Mention that duplicate ingredients are automatically combined across recipes

## Flow

```
User wants meals → search_recipes with filters → user picks → get_recipe for details
→ offer sides → ask about skipping basics → create_instacart_cart or create_recipe_page → done
```
