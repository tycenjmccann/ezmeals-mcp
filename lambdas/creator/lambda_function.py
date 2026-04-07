"""
EZ Meals MCP — Recipe Creator Lambda
Tool: create_recipe
Takes recipe text (scraped or user-provided), formats via Bedrock, saves to UserCreatedRecipes.
"""
import json
import os
import uuid
import re
import boto3
from datetime import datetime, timezone

ROLE_ARN = "arn:aws:iam::970547358447:role/IsengardAccount-DynamoDBAccess"
TABLE_NAME = "UserCreatedRecipes-ryvykzwfevawxbpf5nmynhgtea-dev"
DB_REGION = "us-west-1"
MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
CUISINE_TYPES = ["Global Cuisines", "American", "Asian", "Indian", "Italian", "Latin", "Soups & Stews"]

_creds_cache = {}


def _get_creds():
    if not _creds_cache:
        creds = boto3.client("sts").assume_role(RoleArn=ROLE_ARN, RoleSessionName="mcp-creator")["Credentials"]
        _creds_cache.update(creds)
    return _creds_cache


def _get_table():
    creds = _get_creds()
    dynamodb = boto3.resource("dynamodb", region_name=DB_REGION,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"])
    return dynamodb.Table(TABLE_NAME)


def _amplify_timestamp():
    """Generate Amplify-compatible timestamp with real millisecond precision."""
    now = datetime.now(timezone.utc)
    return now.strftime('%Y-%m-%dT%H:%M:%S.') + f"{now.microsecond // 1000:03d}Z"


def _format_recipe_via_bedrock(recipe_text):
    """Call Bedrock to convert recipe text into structured format."""
    bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")

    prompt = f"""Convert the following recipe into a structured JSON object. Return ONLY valid JSON, no markdown.

Recipe Text:
{recipe_text}

Output this exact JSON structure:
{{
  "title": "Recipe Name",
  "description": "Engaging 1-2 sentence description mentioning cuisine type.",
  "link": "source URL if present, otherwise empty string",
  "prepTime": 15,
  "cookTime": 30,
  "cuisineType": "one of: {json.dumps(CUISINE_TYPES)}",
  "ingredients": ["1 cup ingredient one", "2 tbsp ingredient two"],
  "instructions": ["Step 1 starting with imperative verb and including quantities.", "Step 2..."],
  "notes": ["Dietary substitution notes only, e.g. For gluten-free: use tamari instead of soy sauce"],
  "glutenFree": true,
  "vegetarian": false,
  "slowCook": false,
  "instaPot": false
}}

Rules:
- ingredients: preserve original quantities, use mixed fractions (1/2 not 0.5)
- instructions: start each with imperative verb, include ingredient quantities in each step
- notes: ONLY dietary substitutions (GF, vegetarian alternatives). No general tips.
- glutenFree: true if recipe CAN be made GF with reasonable substitutions
- cuisineType: must be exactly one from the list above
- prepTime/cookTime: integers in minutes
- If source URL is in the text, extract it to "link"
"""

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        }),
        contentType="application/json",
        accept="application/json"
    )

    result = json.loads(response["body"].read())
    text = result["content"][0]["text"]

    # Extract JSON from response
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(0))
    raise ValueError(f"No valid JSON in Bedrock response: {text[:200]}")


def _compute_time_flags(prep, cook):
    total = (prep or 0) + (cook or 0)
    return {
        "isQuick": total <= 30,
        "isBalanced": 31 <= total <= 60,
        "isGourmet": total > 60,
    }


def create_recipe(args):
    """Create a user recipe from text. Requires auth. Formats via Bedrock, saves to DynamoDB."""
    from auth_helper import require_auth

    user, auth_error = require_auth(args)
    if auth_error:
        return auth_error

    recipe_text = args.get("recipe_text", "").strip()
    user_id = user["user_id"]

    if not recipe_text:
        return {"error": "recipe_text is required — provide a full recipe or describe what you want to create"}

    if len(recipe_text) < 20:
        return {"error": "recipe_text is too short — provide ingredients and instructions, or a detailed description"}

    # Format via Bedrock
    try:
        recipe = _format_recipe_via_bedrock(recipe_text)
    except Exception as e:
        return {"error": f"Failed to format recipe: {str(e)}"}

    # Generate IDs and timestamps
    recipe_id = str(uuid.uuid4())
    timestamp = _amplify_timestamp()
    title = recipe.get("title", "Untitled Recipe")
    title_clean = re.sub(r'\W+', '_', title).strip('_')

    # Compute time flags
    prep = recipe.get("prepTime", 0) or 0
    cook = recipe.get("cookTime", 0) or 0
    flags = _compute_time_flags(prep, cook)

    # Build DynamoDB item — matching Amplify schema exactly
    item = {
        "userid": user_id,
        "recipeid": recipe_id,
        "title": title,
        "description": recipe.get("description", ""),
        "link": recipe.get("link", ""),
        "imageURL": f"user-created-images/{title_clean}_{recipe_id}.jpg",
        "imageThumbURL": f"user-created-images/{title_clean}_thumb_{recipe_id}.jpg",
        "prepTime": prep,
        "cookTime": cook,
        "rating": 5,
        "cuisineType": recipe.get("cuisineType", "Global Cuisines"),
        "isQuick": flags["isQuick"],
        "isBalanced": flags["isBalanced"],
        "isGourmet": flags["isGourmet"],
        "ingredients": recipe.get("ingredients", []),
        "instructions": recipe.get("instructions", []),
        "notes": recipe.get("notes", []),
        "products": [],
        "glutenFree": recipe.get("glutenFree", False),
        "vegetarian": recipe.get("vegetarian", False),
        "slowCook": recipe.get("slowCook", False),
        "instaPot": recipe.get("instaPot", False),
        "flagged": False,
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }

    # Write to DynamoDB
    try:
        table = _get_table()
        table.put_item(Item=item)
    except Exception as e:
        return {"error": f"Failed to save recipe: {str(e)}"}

    return {
        "recipe_id": recipe_id,
        "user_id": user_id,
        "title": title,
        "description": recipe.get("description", ""),
        "cuisineType": recipe.get("cuisineType", ""),
        "prepTime": prep,
        "cookTime": cook,
        "ingredients_count": len(recipe.get("ingredients", [])),
        "instructions_count": len(recipe.get("instructions", [])),
        "message": f"Recipe '{title}' created successfully! It will be enriched with images and ingredient details within a few minutes.",
    }


def lambda_handler(event, context):
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

    if tool_name == "create_recipe":
        result = create_recipe(args)
    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
