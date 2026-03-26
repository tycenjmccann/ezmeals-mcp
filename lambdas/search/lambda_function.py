"""
EZ Meals MCP — Search Lambda
Tools: search_recipes, browse_cuisines
Scans MenuItemData DynamoDB table with filters.
Guest access: max 5 results. Authenticated: unlimited.
"""
import json
import boto3
from boto3.dynamodb.conditions import Attr
from auth_helper import validate_token

GUEST_MAX_RESULTS = 5

ROLE_ARN = "arn:aws:iam::970547358447:role/IsengardAccount-DynamoDBAccess"
TABLE_NAME = "MenuItemData-ryvykzwfevawxbpf5nmynhgtea-dev"
DB_REGION = "us-west-1"

TOOLS = [
    {
        "name": "search_recipes",
        "description": "Search EZ Meals recipe catalog. Use filters for cuisine, time, dietary needs, or search by ingredient/dish name. Returns recipe summaries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term for specific ingredients or dish names. Leave empty to browse by filters."},
                "cuisine": {"type": "string", "enum": ["Global Cuisines", "Italian", "Asian", "Indian", "American", "Latin", "Soups & Stews"], "description": "Filter by cuisine type. 'Global Cuisines' returns all."},
                "time": {"type": "string", "enum": ["quick", "balanced", "gourmet"], "description": "quick (0-30 min), balanced (31-60 min), gourmet (60+ min)"},
                "dietary": {"type": "string", "enum": ["glutenFree", "vegetarian"], "description": "Dietary restriction filter"},
                "cookMethod": {"type": "string", "enum": ["slowCook", "instaPot"], "description": "Cooking method filter"},
                "limit": {"type": "integer", "description": "Max results. Default 10."}
            }
        }
    },
    {
        "name": "browse_cuisines",
        "description": "Browse available cuisine types and see how many recipes are in each category.",
        "inputSchema": {"type": "object", "properties": {}}
    }
]


def get_table():
    sts = boto3.client("sts")
    creds = sts.assume_role(RoleArn=ROLE_ARN, RoleSessionName="mcp-search")["Credentials"]
    dynamodb = boto3.resource(
        "dynamodb", region_name=DB_REGION,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"]
    )
    return dynamodb.Table(TABLE_NAME)


def scan_all(table, **kwargs):
    items = []
    last_key = None
    while True:
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
    return items


def to_summary(item):
    return {
        "id": item.get("id", ""),
        "title": item.get("title", ""),
        "description": item.get("description", ""),
        "cuisineType": item.get("cuisineType", ""),
        "prepTime": int(item.get("prepTime", 0)),
        "cookTime": int(item.get("cookTime", 0)),
        "imageURL": item.get("imageURL", ""),
        "glutenFree": item.get("glutenFree", False),
        "vegetarian": item.get("vegetarian", False),
        "isQuick": item.get("isQuick", False),
        "isBalanced": item.get("isBalanced", False),
        "isGourmet": item.get("isGourmet", False),
        "dishType": item.get("dishType", "main"),
    }


def search_recipes(args):
    # Check auth — guests get capped results
    auth_token = args.get("auth_token", "")
    is_authenticated = bool(validate_token(auth_token)) if auth_token else False
    
    table = get_table()
    query = args.get("query", "").lower().strip()
    cuisine = args.get("cuisine", "")
    time_filter = args.get("time", "")
    dietary = args.get("dietary", "")
    cook_method = args.get("cookMethod", "")
    limit = args.get("limit", 10)
    
    # Enforce guest limit
    if not is_authenticated:
        limit = min(int(limit), GUEST_MAX_RESULTS)

    # Build filter expression
    filters = []
    # Only main dishes by default
    filters.append(Attr("dishType").eq("main"))

    if cuisine and cuisine != "Global Cuisines":
        filters.append(Attr("cuisineType").eq(cuisine))
    if time_filter == "quick":
        filters.append(Attr("isQuick").eq(True))
    elif time_filter == "balanced":
        filters.append(Attr("isBalanced").eq(True))
    elif time_filter == "gourmet":
        filters.append(Attr("isGourmet").eq(True))
    if dietary == "glutenFree":
        filters.append(Attr("glutenFree").eq(True))
    elif dietary == "vegetarian":
        filters.append(Attr("vegetarian").eq(True))
    if cook_method == "slowCook":
        filters.append(Attr("slowCook").eq(True))
    elif cook_method == "instaPot":
        filters.append(Attr("instaPot").eq(True))

    combined = filters[0]
    for f in filters[1:]:
        combined = combined & f

    items = scan_all(table, FilterExpression=combined)

    # Text search if query provided
    if query:
        items = [i for i in items if query in i.get("title", "").lower()
                 or query in i.get("description", "").lower()
                 or any(query in (ing or "").lower() for ing in (i.get("ingredients") or []))]

    results = [to_summary(i) for i in items[:limit]]
    resp = {"recipes": results, "total": len(results)}
    if not is_authenticated:
        resp["guest_mode"] = True
        resp["results_capped_at"] = GUEST_MAX_RESULTS
        resp["tip"] = "Create a free EZ Meals account for unlimited access — it's free forever. Use the signup tool."
    return resp


def browse_cuisines(args):
    table = get_table()
    items = scan_all(table, FilterExpression=Attr("dishType").eq("main"),
                     ProjectionExpression="cuisineType")
    counts = {}
    for item in items:
        ct = item.get("cuisineType", "Unknown")
        counts[ct] = counts.get(ct, 0) + 1
    return {"cuisines": [{"cuisine": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]}


def lambda_handler(event, context):
    """MCP Lambda handler — AgentCore Gateway passes tool name via client_context."""
    import logging
    logging.getLogger().setLevel(logging.INFO)
    
    # AgentCore Gateway passes tool name in context.client_context.custom
    tool_name = ""
    if hasattr(context, 'client_context') and context.client_context:
        custom = context.client_context.custom or {}
        tool_name = custom.get('bedrockAgentCoreToolName', '')
    
    # Strip target prefix
    if "___" in tool_name:
        tool_name = tool_name.split("___", 1)[1]
    
    # Arguments come in the event payload
    args = event if event else {}
    if isinstance(args, str):
        args = json.loads(args)
    
    logging.info(f"TOOL: {tool_name}, ARGS: {args}")

    if tool_name == "search_recipes":
        result = search_recipes(args)
    elif tool_name == "browse_cuisines":
        result = browse_cuisines(args)
    else:
        result = {"error": f"Unknown tool: '{tool_name}'", "event": event, "context_fn": context.function_name if hasattr(context, 'function_name') else 'unknown'}

    return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
