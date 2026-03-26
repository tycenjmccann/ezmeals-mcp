# EZ Meals MCP Gateway — Deployment Config

## Gateway
- **ARN:** arn:aws:bedrock-agentcore:us-west-2:023392223961:gateway/ezmeals-mcp-evwbfnpaze
- **ID:** ezmeals-mcp-evwbfnpaze
- **URL:** https://ezmeals-mcp-evwbfnpaze.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp
- **Region:** us-west-2
- **Role:** arn:aws:iam::023392223961:role/AgentCoreGatewayExecutionRole

## Auth (Cognito)
- **User Pool:** us-west-2_wS679TCPo
- **Client ID:** 6idjuaeg7ibeulo8v0krio5ud5
- **Domain:** agentcore-8634da80.auth.us-west-2.amazoncognito.com
- **Token URL:** https://agentcore-8634da80.auth.us-west-2.amazoncognito.com/oauth2/token
- **Scope:** ezmeals-mcp/invoke

## Targets (added as we build)
- [ ] search Lambda
- [ ] recipes Lambda
- [ ] shopping Lambda
