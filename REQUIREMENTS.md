# EZ Meals MCP Server — Requirements & Architecture

## Vision

Turn EZ Meals into a platform that any AI assistant can use. Instead of users needing to download our iOS app, their AI assistant (Claude, ChatGPT, Copilot, custom agents) connects to our MCP server and can plan meals, build shopping lists, and send users to Instacart checkout — all through natural language.

Every Instacart checkout = $10 affiliate revenue, regardless of which AI assistant initiated it.

## What We're Building

An MCP server hosted on AWS (via Bedrock AgentCore Gateway) that exposes EZ Meals' core capabilities as tools any MCP-compatible AI agent can call.

```
Any AI Assistant (Claude, ChatGPT, custom agents)
    ↓ MCP Protocol
AgentCore MCP Gateway (auth, routing, scaling)
    ↓
Lambda Functions (business logic)
    ↓
DynamoDB (MenuItemData, Ingredient, AffiliateProduct, WeeklyStaple)
    + Instacart API (shopping list/recipe page creation)
```

---

## MCP Tools to Expose

Based on the existing NovaSonic voice agent tools, mapped to MCP:

### 1. `search_recipes`
**Source:** `EzMealsSearchTool`
**Purpose:** Search the recipe catalog with filters

```json
{
  "name": "search_recipes",
  "description": "Search EZ Meals recipe catalog. Use filters for cuisine, time, dietary needs, or search by ingredient/dish name.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Search term — specific ingredients (chicken, beef) or dish names (tacos, pasta). Leave empty to browse by filters."
      },
      "cuisine": {
        "type": "string",
        "enum": ["Global Cuisines", "Italian", "Asian", "Indian", "American", "Latin", "Soups & Stews"],
        "description": "Filter by cuisine type. 'Global Cuisines' returns all."
      },
      "time": {
        "type": "string",
        "enum": ["quick", "balanced", "gourmet"],
        "description": "Filter by cook time: quick (0-30 min), balanced (31-60 min), gourmet (60+ min)"
      },
      "dietary": {
        "type": "string",
        "enum": ["glutenFree", "vegetarian"],
        "description": "Filter by dietary restriction"
      },
      "cookMethod": {
        "type": "string",
        "enum": ["slowCook", "instaPot"],
        "description": "Filter by cooking method"
      },
      "limit": {
        "type": "integer",
        "description": "Max results to return. Default 10."
      }
    }
  }
}
```

**Returns:** Array of recipe summaries (id, title, description, cuisineType, prepTime, cookTime, imageURL, dietary flags)

### 2. `get_recipe`
**Source:** `EzMealsMealDetailsTool`
**Purpose:** Get full recipe details including ingredients and instructions

```json
{
  "name": "get_recipe",
  "description": "Get complete recipe details including ingredients, instructions, notes, and nutritional flags.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "recipe_id": {
        "type": "string",
        "description": "The recipe ID from search results"
      }
    },
    "required": ["recipe_id"]
  }
}
```

**Returns:** Full recipe object (title, description, ingredients, ingredient_objects, instructions, notes, prepTime, cookTime, servings, cuisineType, dietary flags, recommendedSides, products)

### 3. `get_shopping_list`
**Source:** `ShoppingListViewModel` consolidation logic
**Purpose:** Generate a consolidated shopping list from multiple recipes

```json
{
  "name": "get_shopping_list",
  "description": "Generate a consolidated grocery shopping list from one or more recipes. Combines duplicate ingredients and aggregates quantities.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "recipe_ids": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Array of recipe IDs to include in the shopping list"
      },
      "exclude_categories": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Ingredient categories to exclude (e.g., ['Seasonings', 'Pantry Staples'] for basics the user already has)"
      },
      "exclude_ingredients": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Specific ingredient names to exclude (e.g., ['oil', 'butter', 'salt'])"
      }
    },
    "required": ["recipe_ids"]
  }
}
```

**Returns:** Consolidated ingredient list grouped by category, with quantities aggregated

### 4. `create_instacart_cart`
**Source:** `InstacartService`
**Purpose:** Create an Instacart shopping page from ingredients

```json
{
  "name": "create_instacart_cart",
  "description": "Create an Instacart shopping page from a list of ingredients. Returns a URL where the user can select a store, review matched products, and checkout. Supports 100,000+ stores including Costco, Kroger, Safeway, Sprouts, and more.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "title": {
        "type": "string",
        "description": "Title for the shopping list (e.g., 'Weekly Meal Plan - March 25')"
      },
      "recipe_ids": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Recipe IDs to build the cart from. Ingredients will be consolidated automatically."
      },
      "exclude_categories": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Categories to exclude (e.g., ['Seasonings', 'Pantry Staples'])"
      },
      "exclude_ingredients": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Specific ingredients to exclude"
      },
      "additional_items": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Extra items to add that aren't in recipes (e.g., 'milk', 'bread', 'eggs')"
      }
    },
    "required": ["recipe_ids"]
  }
}
```

**Returns:** `{ "instacart_url": "https://www.instacart.com/store/shopping_lists/...", "ingredient_count": 15, "categories": [...] }`

### 5. `get_recommended_sides`
**Source:** `MenuItem.recommendedSides` + `MenuItemData` lookup
**Purpose:** Get recommended side dishes for a main

```json
{
  "name": "get_recommended_sides",
  "description": "Get recommended side dishes that pair well with a main dish.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "recipe_id": {
        "type": "string",
        "description": "The main dish recipe ID"
      }
    },
    "required": ["recipe_id"]
  }
}
```

**Returns:** Array of side dish recipes (id, title, description, prepTime, cookTime)

### 6. `browse_cuisines`
**Purpose:** List available cuisines and recipe counts for discovery

```json
{
  "name": "browse_cuisines",
  "description": "Browse available cuisine types and see how many recipes are in each category.",
  "inputSchema": {
    "type": "object",
    "properties": {}
  }
}
```

**Returns:** `[{"cuisine": "Italian", "count": 25}, {"cuisine": "Asian", "count": 30}, ...]`

---

## Architecture

### Infrastructure: AgentCore MCP Gateway + Lambda

```
MCP Client (any AI assistant)
    │
    ▼
AgentCore MCP Gateway (ezmeals-mcp-gateway)
    ├── Auth: Cognito OAuth2 (client credentials)
    ├── Semantic search: enabled
    └── Targets:
        │
        ├── Lambda: ezmeals-mcp-search
        │   └── Tools: search_recipes, browse_cuisines
        │
        ├── Lambda: ezmeals-mcp-recipes
        │   └── Tools: get_recipe, get_recommended_sides
        │
        ├── Lambda: ezmeals-mcp-shopping
        │   └── Tools: get_shopping_list, create_instacart_cart
        │
        └── MCP Server Target: Instacart MCP (optional, for direct passthrough)
            └── URL: https://mcp.instacart.com/mcp
```

### Why Lambda Targets (not a standalone MCP server)

- **Zero infrastructure management** — AgentCore handles scaling, auth, routing
- **Pay per invocation** — no idle costs
- **Built-in auth** — Cognito OAuth2 out of the box
- **Semantic search** — AgentCore can route natural language to the right tool automatically
- **Same DynamoDB tables** — Lambdas use the same cross-account role we already have

### AWS Resources

| Resource | Details |
|---|---|
| AgentCore Gateway | `ezmeals-mcp-gateway` in us-west-2 |
| Lambda: search | `ezmeals-mcp-search` — scans MenuItemData with filters |
| Lambda: recipes | `ezmeals-mcp-recipes` — gets full recipe details |
| Lambda: shopping | `ezmeals-mcp-shopping` — consolidates ingredients + calls Instacart API |
| DynamoDB | Existing tables (MenuItemData, Ingredient, AffiliateProduct) via cross-account role |
| Cognito | Auto-created by AgentCore for OAuth2 client credentials |
| Instacart API | Dev: `connect.dev.instacart.tools`, Prod: `connect.instacart.com` |

### Data Flow: "Plan my meals and order groceries"

```
User → AI Assistant: "Plan 3 meals for this week, nothing too fancy, skip the basics, and order on Instacart"

AI Assistant → EZ Meals MCP:
  1. search_recipes(cuisine: "Global Cuisines", time: "quick", limit: 10)
     ← Returns 10 quick recipes
  
  2. AI picks 3 recipes based on variety
  
  3. get_recipe(recipe_id: "chicken-tacos") × 3
     ← Returns full details for each
  
  4. create_instacart_cart(
       recipe_ids: ["chicken-tacos", "quick-spaghetti", "steak-kebabs"],
       exclude_categories: ["Seasonings", "Pantry Staples"],
       title: "Weekly Meals - March 25"
     )
     ← Returns Instacart URL

AI Assistant → User: "Here's your meal plan:
  Monday: Chicken Tacos (25 min)
  Wednesday: Quick Spaghetti (20 min)  
  Friday: Steak Kebabs (35 min)
  
  I've created your Instacart cart with 18 ingredients (skipped seasonings and pantry staples): [link]"
```

---

## Revenue Model

| Source | Revenue | Trigger |
|---|---|---|
| Instacart affiliate | $10 per completed order | User checks out via Instacart URL from MCP |
| API usage (future) | Tiered pricing | High-volume MCP consumers (enterprise agents) |
| Recipe licensing (future) | Per-recipe fee | Agents that want to display full recipe content |

**Conservative estimate:** If 100 AI assistants each drive 1 Instacart order/day = $1,000/day = $30,000/month

---

## Authentication & Access Control

### For MCP Consumers (AI Assistants)

AgentCore Gateway handles this automatically:
- **OAuth2 client credentials flow** via Cognito
- Each consumer gets a `client_id` + `client_secret`
- Tokens scoped to `invoke` permission
- Rate limiting per client

### For Internal DynamoDB Access

- Same cross-account STS AssumeRole pattern as the recipe creator
- Role: `arn:aws:iam::970547358447:role/IsengardAccount-DynamoDBAccess`
- Read-only access to MenuItemData, Ingredient tables

### For Instacart API

- Instacart API key stored in Lambda environment variables (encrypted)
- Impact.com affiliate params appended to all generated URLs

---

## Implementation Plan

### Phase 1: Lambda Functions (2-3 days)

1. **`ezmeals-mcp-search`** Lambda
   - Scan MenuItemData with filter expressions
   - Support cuisine, time, dietary, cookMethod filters
   - Return summary objects (not full recipes)
   - Implement `browse_cuisines` aggregation

2. **`ezmeals-mcp-recipes`** Lambda
   - Get single recipe by ID
   - Parse ingredient_objects JSON
   - Resolve recommendedSides IDs to recipe summaries

3. **`ezmeals-mcp-shopping`** Lambda
   - Fetch ingredient_objects for multiple recipes
   - Consolidate duplicates (same logic as iOS app's DoMath)
   - Apply exclusion filters
   - Call Instacart API to create shopping page
   - Append affiliate tracking params
   - Return URL

### Phase 2: AgentCore Gateway (1 day)

1. Install AgentCore CLI: `pip install bedrock-agentcore-starter-toolkit`
2. Create gateway: `agentcore gateway create-mcp-gateway --name ezmeals-mcp --region us-west-2`
3. Add Lambda targets for each function group
4. Test with MCP inspector

### Phase 3: Skill File & Distribution (1 day)

1. Create `ezmeals-mcp-skill.md` — markdown file that tells AI assistants how to use the server
2. Register on MCP directories
3. Create example prompts and use cases
4. Document the OAuth2 client registration flow for consumers

### Phase 4: Testing & Launch (1 day)

1. Test with Claude Desktop (MCP client)
2. Test with a Strands Agent
3. Test end-to-end: search → plan → Instacart checkout
4. Monitor CloudWatch for Lambda errors and latency
5. Verify Instacart affiliate tracking works

---

## Skill File (for AI Assistants)

This is the markdown file that tells any AI assistant how to use EZ Meals:

```markdown
# EZ Meals — Meal Planning & Grocery Ordering

## What This Does
EZ Meals helps users plan weekly meals and order groceries. Search 200+ curated recipes,
build meal plans, generate consolidated shopping lists, and create Instacart checkout
carts — all through natural language.

## Available Tools
- search_recipes: Find recipes by cuisine, time, dietary needs, or ingredients
- get_recipe: Get full recipe details (ingredients, instructions, notes)
- get_shopping_list: Consolidate ingredients from multiple recipes
- create_instacart_cart: Send ingredients to Instacart for checkout
- get_recommended_sides: Find side dishes that pair with a main
- browse_cuisines: See available cuisine categories

## Common Workflows

### Plan a week of meals
1. Ask what the user wants (cuisine preferences, time constraints, dietary needs)
2. search_recipes with appropriate filters
3. Present options, let user choose
4. get_recipe for each selected meal to show details
5. create_instacart_cart with all recipe_ids to generate shopping link

### Quick grocery run
1. User names specific recipes they want to cook
2. search_recipes to find them
3. create_instacart_cart with exclude_categories for basics they have

### Explore new cuisines
1. browse_cuisines to show options
2. search_recipes filtered to chosen cuisine
3. get_recipe for interesting results
```

---

## File Structure

```
ezmeals-mcp/
├── REQUIREMENTS.md          ← This document
├── lambdas/
│   ├── search/
│   │   ├── lambda_function.py
│   │   └── requirements.txt
│   ├── recipes/
│   │   ├── lambda_function.py
│   │   └── requirements.txt
│   └── shopping/
│       ├── lambda_function.py
│       └── requirements.txt
├── gateway/
│   └── deploy.sh            ← AgentCore Gateway setup script
├── skill/
│   └── ezmeals-mcp-skill.md ← Skill file for AI assistants
└── tests/
    └── test_mcp.py           ← End-to-end MCP tests
```

---

## Dependencies on Existing Systems

| System | Dependency | Access Pattern |
|---|---|---|
| MenuItemData DynamoDB | Recipe catalog (200+ recipes) | Read-only scan/query via cross-account role |
| Ingredient DynamoDB | Standardized ingredient names | Read-only scan |
| AffiliateProduct DynamoDB | Product recommendations | Read-only scan |
| Instacart API | Shopping page creation | REST API with Bearer auth |
| S3 Images | Recipe images for Instacart pages | Public URL construction |

---

## Open Questions

1. **Rate limiting** — what limits per MCP consumer? Start with 100 req/min?
2. **Recipe licensing** — should we limit what data we return for free vs paid?
3. **User accounts** — should MCP consumers be able to create user-specific meal plans that persist?
4. **Weekly staples** — expose the weekly staples CRUD tools too, or keep that app-only?
5. **Recipe creation** — should the MCP server accept new recipes (from the recipe creator pipeline)?
