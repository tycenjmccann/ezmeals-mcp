# Guest Access & Rate Limiting — Implementation Plan

## Overview

Add guest (unauthenticated) access to the MCP server with rate limiting. Guests can discover recipes on a limited basis, then sign up for full access.

## Guest Tier Limits

| | Guest | Authenticated |
|---|---|---|
| search_recipes | 3 calls/day, max 5 results | Unlimited, max 50 results |
| browse_cuisines | Counts toward 3 calls/day | Unlimited |
| get_recipe | ❌ Blocked | ✅ Full access |
| get_recommended_sides | ❌ Blocked | ✅ Full access |
| get_shopping_list | ❌ Blocked | ✅ Full access |
| create_instacart_cart | ❌ Blocked | ✅ Full access |
| signup | ✅ Always available | N/A |
| confirm_signup | ✅ Always available | N/A |
| login | ✅ Always available | N/A |

## Anti-Scraping Protection

- Guest sees max 15 recipe summaries/day (3 searches × 5 results)
- No full recipe details (ingredients, instructions) without auth
- No shopping list or Instacart cart without auth
- Each guest gets a unique Cognito Identity ID for tracking

## Implementation Steps

### 1. Create Cognito Identity Pool
- Enable unauthenticated access
- Link to existing EZ Meals User Pool for authenticated access
- Create IAM roles for guest vs authenticated

### 2. Update Gateway Authorizer
- Accept tokens from Identity Pool (in addition to current OAuth)
- Or: create a lightweight token endpoint that guests can call

### 3. Create Usage Counter Table
- DynamoDB table: `ezmeals-mcp-usage`
- Key: `identity_id` (string)
- Attributes: `date` (string YYYY-MM-DD), `search_count` (number)
- TTL: auto-expire after 7 days

### 4. Update Search Lambda
- Check if caller is guest (from identity context)
- If guest: check daily usage count, enforce 3/day limit
- If guest: cap results at 5 regardless of `limit` param
- Return helpful error when limit hit: "Sign up for unlimited access"

### 5. Update Recipe/Shopping Lambdas
- Check if caller is guest
- If guest: return error "This tool requires an EZ Meals account. Use the signup tool."

## Error Messages (Agent-Friendly)

```json
// Guest hits search limit
{
  "error": "guest_limit_reached",
  "message": "You've used 3 of 3 free searches today. Create an EZ Meals account for unlimited access.",
  "action": "Call the signup tool with an email and password to create a free account.",
  "searches_used": 3,
  "searches_limit": 3
}

// Guest tries to access auth-required tool
{
  "error": "authentication_required",
  "message": "Full recipe details require an EZ Meals account.",
  "action": "Call the signup tool to create a free account, then login to access all features.",
  "available_tools_for_guests": ["search_recipes", "browse_cuisines", "signup", "confirm_signup", "login"]
}
```

## Estimated Effort
- 30-45 minutes
