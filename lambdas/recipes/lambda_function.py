"""
EZ Meals MCP — Recipes Lambda
Tools: get_recipe, get_recommended_sides
Gets full recipe details and resolves side dish recommendations.
"""
import json
import boto3
from decimal import Decimal

ROLE_ARN = "arn:aws:iam::970547358447:role/IsengardAccount-DynamoDBAccess"
TABLE_NAME = "MenuItemData-ryvykzwfevawxbpf5nmynhgtea-dev"
DB_REGION = "us-west-1"


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o) if o % 1 else int(o)
        return super().default(o)


def get_table():
    sts = boto3.client("sts")
    creds = sts.assume_role(RoleArn=ROLE_ARN, RoleSessionName="mcp-recipes")["Credentials"]
    dynamodb = boto3.resource(
        "dynamodb", region_name=DB_REGION,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"]
    )
    return dynamodb.Table(TABLE_NAME)


def get_recipe(args):
    recipe_id = args.get("recipe_id", "")
    if not recipe_id:
        return {"error": "recipe_id is required"}
    
    table = get_table()
    resp = table.get_item(Key={"id": recipe_id})
    item = resp.get("Item")
    if not item:
        return {"error": f"Recipe not found: {recipe_id}"}
    
    # Parse ingredient_objects if it's a JSON string
    ingredient_objects = item.get("ingredient_objects", "[]")
    if isinstance(ingredient_objects, str):
        try:
            ingredient_objects = json.loads(ingredient_objects)
        except json.JSONDecodeError:
            ingredient_objects = []
    
    return {
        "id": item.get("id", ""),
        "title": item.get("title", ""),
        "description": item.get("description", ""),
        "cuisineType": item.get("cuisineType", ""),
        "dishType": item.get("dishType", "main"),
        "prepTime": int(item.get("prepTime", 0)),
        "cookTime": int(item.get("cookTime", 0)),
        "servings": str(item.get("servings", "")),
        "imageURL": item.get("imageURL", ""),
        "ingredients": item.get("ingredients", []),
        "ingredient_objects": ingredient_objects,
        "instructions": item.get("instructions", []),
        "notes": item.get("notes", []),
        "glutenFree": item.get("glutenFree", False),
        "vegetarian": item.get("vegetarian", False),
        "slowCook": item.get("slowCook", False),
        "instaPot": item.get("instaPot", False),
        "recommendedSides": item.get("recommendedSides", []),
        "products": item.get("products", []),
    }


def get_recommended_sides(args):
    recipe_id = args.get("recipe_id", "")
    if not recipe_id:
        return {"error": "recipe_id is required"}
    
    table = get_table()
    
    # Get the main recipe to find its recommendedSides
    resp = table.get_item(Key={"id": recipe_id})
    item = resp.get("Item")
    if not item:
        return {"error": f"Recipe not found: {recipe_id}"}
    
    side_ids = item.get("recommendedSides", [])
    if not side_ids:
        return {"sides": [], "message": "No recommended sides for this recipe"}
    
    # Resolve each side ID to a summary
    sides = []
    for sid in side_ids:
        if not sid:
            continue
        side_resp = table.get_item(Key={"id": sid})
        side = side_resp.get("Item")
        if side:
            sides.append({
                "id": side.get("id", ""),
                "title": side.get("title", ""),
                "description": side.get("description", ""),
                "prepTime": int(side.get("prepTime", 0)),
                "cookTime": int(side.get("cookTime", 0)),
            })
    
    return {"sides": sides, "main_recipe": item.get("title", "")}


def lambda_handler(event, context):
    """MCP Lambda handler — tool name from context, args from event."""
    import logging
    logging.getLogger().setLevel(logging.INFO)
    
    tool_name = ""
    if hasattr(context, 'client_context') and context.client_context:
        custom = context.client_context.custom or {}
        tool_name = custom.get('bedrockAgentCoreToolName', '')
    
    if "___" in tool_name:
        tool_name = tool_name.split("___", 1)[1]
    
    args = event if event else {}
    if isinstance(args, str):
        args = json.loads(args)
    
    logging.info(f"TOOL: {tool_name}")

    if tool_name == "get_recipe":
        result = get_recipe(args)
    elif tool_name == "get_recommended_sides":
        result = get_recommended_sides(args)
    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return {"content": [{"type": "text", "text": json.dumps(result, cls=DecimalEncoder, default=str)}]}
