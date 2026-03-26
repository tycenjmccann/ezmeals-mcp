# EZ Meals MCP Server

Expose EZ Meals' meal planning and grocery ordering capabilities as an MCP server that any AI assistant can use.

## Quick Start

See [REQUIREMENTS.md](REQUIREMENTS.md) for full architecture and implementation plan.

## Tools

| Tool | Description |
|---|---|
| `search_recipes` | Search 200+ recipes by cuisine, time, dietary needs |
| `get_recipe` | Get full recipe with ingredients and instructions |
| `get_shopping_list` | Consolidated grocery list from multiple recipes |
| `create_instacart_cart` | Send ingredients to Instacart for checkout ($10/order affiliate) |
| `get_recommended_sides` | Side dishes that pair with a main |
| `browse_cuisines` | Available cuisine categories |

## Architecture

AgentCore MCP Gateway → Lambda Functions → DynamoDB + Instacart API

## Status

🟡 Planning — Requirements complete, implementation pending.
