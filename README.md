# EZ Meals MCP Server

An MCP server that gives any AI assistant access to 200+ curated recipes, smart side dish pairings, and one-click Instacart grocery ordering. No account required.

## Connect

```
URL: https://ezmeals-public-8cgrhnbvcs.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp
Transport: Streamable HTTP
Authentication: None
```

That's it. No API key, no OAuth, no signup. Just point your MCP client at the URL.

## Tools

| Tool | Description |
|---|---|
| `search_recipes` | Search by cuisine, cook time, dietary needs, or keywords |
| `browse_cuisines` | See all cuisine categories with recipe counts |
| `get_recipe` | Full recipe — ingredients, instructions, image, nutrition |
| `get_recommended_sides` | Side dishes that pair with a main (with images) |
| `get_shopping_list` | Consolidated grocery list from one or more recipes |
| `create_instacart_cart` | Instacart shopping cart for multiple recipes |
| `create_recipe_page` | **Full Instacart recipe page** — photo, cooking instructions, and shoppable ingredients in one link |

## Example Flow

```
1. search_recipes(cuisine="Italian")
   → 15 recipes with images

2. get_recommended_sides(recipe_id="stuffed-shells-spinach-ricotta")
   → Garlic Bread, Caesar Salad, Roasted Broccolini...

3. create_recipe_page(recipe_id="stuffed-shells-spinach-ricotta", include_sides=true)
   → One URL with recipe photo, 39 cooking steps, 45 shoppable ingredients
```

The user gets a single link to see the recipe and order all the groceries.

## What You Get

- **200+ recipes** across Italian, Asian, Indian, American, Latin, Soups & Stews
- **Smart side pairings** — every main has curated side dish recommendations
- **Recipe images** — presigned S3 URLs, displayable in any chat client
- **Instacart recipe pages** — hosted page with photo, instructions, and shopping cart
- **Ingredient consolidation** — duplicates merged across multiple recipes
- **Dietary filters** — gluten-free, vegetarian
- **Cook time filters** — quick (≤30 min), balanced (30-60 min), gourmet (60+ min)

## Architecture

```
MCP Client → AgentCore Gateway (us-west-2) → Lambda Functions → DynamoDB + S3 + Instacart API
```

- **Gateway**: AgentCore MCP Gateway, public access (no auth)
- **Compute**: 4 Lambda functions (search, recipes, shopping, auth)
- **Data**: DynamoDB (recipes + ingredients), S3 (images)
- **Shopping**: Instacart Developer Platform API (recipe pages + shopping lists)

## Status

✅ **Live** — All tools operational, zero auth required.

## Agent Skill

A ready-made [AgentSkills](https://agentskills.io) file lives at `skill/ezmeals-mcp/SKILL.md`. It teaches any AI agent how to use this server — when to call each tool, how to filter ingredients, and how to guide users to checkout.

Install it into your tool of choice:

```bash
# Claude Code
ln -s ../../skill/ezmeals-mcp .claude/skills/ezmeals-mcp

# Cursor
ln -s ../../skill/ezmeals-mcp .cursor/skills/ezmeals-mcp

# Kiro
ln -s ../../skill/ezmeals-mcp .kiro/skills/ezmeals-mcp

# OpenClaw
ln -s skill/ezmeals-mcp skills/ezmeals-mcp
```
