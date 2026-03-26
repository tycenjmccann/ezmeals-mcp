# EZ Meals MCP Gateway — Deployment Config

## Public Gateway (ACTIVE)
- **ID:** ezmeals-public-8cgrhnbvcs
- **URL:** https://ezmeals-public-8cgrhnbvcs.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp
- **Auth:** NONE (public access)
- **Region:** us-west-2
- **Account:** 023392223961 (Isengard)

## Targets
- search (IEZDOLXXSP) → ezmeals-mcp-search Lambda
- recipes (CX9JRODLHQ) → ezmeals-mcp-recipes Lambda
- shopping (CWAYVRKS5K) → ezmeals-mcp-shopping Lambda
- auth (I75OJKM0PG) → ezmeals-mcp-auth Lambda

## Cross-Account Access
- DynamoDB: 970547358447 (ezmeals) via STS AssumeRole
- Cognito User Pool: us-west-1_c6QDYtV20 (ezmeals account)

## Old Gateway (deprecated)
- ID: ezmeals-mcp-evwbfnpaze (CUSTOM_JWT auth — no longer primary)
