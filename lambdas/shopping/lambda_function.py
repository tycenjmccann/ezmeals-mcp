"""
EZ Meals MCP — Shopping Lambda
Tools: get_shopping_list, create_instacart_cart, create_recipe_page,
       get_weekly_staples, add_weekly_staples, remove_weekly_staples
Consolidates ingredients across recipes and creates Instacart checkout/recipe page URLs.
"""
import json
import os
import sys
import boto3
import urllib.request
from decimal import Decimal
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
from auth_helper import require_auth

ROLE_ARN = "arn:aws:iam::970547358447:role/IsengardAccount-DynamoDBAccess"
TABLE_NAME = "MenuItemData-ryvykzwfevawxbpf5nmynhgtea-dev"
STAPLES_TABLE = "WeeklyStaple-ryvykzwfevawxbpf5nmynhgtea-dev"
DB_REGION = "us-west-1"
IMAGE_BUCKET = "amplify-ezmealsnew-menu-item-imageseb66c-dev"
IMAGE_PREFIX = "public/menu-item-images/"
INSTACART_API_KEY = os.environ.get("INSTACART_API_KEY", "")
INSTACART_BASE_URL = os.environ.get("INSTACART_BASE_URL", "https://connect.dev.instacart.tools/idp/v1")
IMPACT_PARTNER_ID = os.environ.get("IMPACT_PARTNER_ID", "")

_creds_cache = {}


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o) if o % 1 else int(o)
        return super().default(o)


def _get_creds():
    if not _creds_cache:
        creds = boto3.client("sts").assume_role(RoleArn=ROLE_ARN, RoleSessionName="mcp-shopping")["Credentials"]
        _creds_cache.update(creds)
    return _creds_cache


def get_table():
    creds = _get_creds()
    dynamodb = boto3.resource("dynamodb", region_name=DB_REGION,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"])
    return dynamodb.Table(TABLE_NAME)


def resolve_image_url(relative_path):
    if not relative_path:
        return ""
    filename = relative_path.split("/")[-1]
    creds = _get_creds()
    s3 = boto3.client("s3", region_name=DB_REGION,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"])
    return s3.generate_presigned_url("get_object",
        Params={"Bucket": IMAGE_BUCKET, "Key": IMAGE_PREFIX + filename}, ExpiresIn=3600)


def _parse_csv(val):
    if isinstance(val, str):
        return [v.strip() for v in val.split(",") if v.strip()]
    return val or []


def parse_quantity(qty_str):
    if not qty_str or not qty_str.strip():
        return 0.0
    qty_str = qty_str.strip()
    try:
        parts = qty_str.split()
        if len(parts) == 2 and '/' in parts[1]:
            return float(parts[0]) + float(Fraction(parts[1]))
        elif '/' in qty_str:
            return float(Fraction(qty_str))
        return float(qty_str)
    except (ValueError, ZeroDivisionError):
        return 1.0


def get_ingredients_for_recipes(recipe_ids):
    table = get_table()
    all_ingredients = []
    for rid in recipe_ids:
        item = (table.get_item(Key={"id": rid}).get("Item") or {})
        obj_str = item.get("ingredient_objects", "[]")
        if isinstance(obj_str, str):
            try:
                objects = json.loads(obj_str)
            except json.JSONDecodeError:
                objects = []
        else:
            objects = obj_str if isinstance(obj_str, list) else []
        for obj in objects:
            all_ingredients.append({
                "ingredient_name": obj.get("ingredient_name", ""),
                "quantity": obj.get("quantity", ""),
                "unit": obj.get("unit", ""),
                "category": obj.get("category", ""),
                "note": obj.get("note", ""),
            })
    return all_ingredients


def consolidate_ingredients(ingredients, exclude_categories=None, exclude_ingredients=None):
    exclude_cats = set(c.lower() for c in (exclude_categories or []))
    exclude_ings = set(i.lower() for i in (exclude_ingredients or []))
    consolidated = {}
    for ing in ingredients:
        name = ing["ingredient_name"]
        if name.lower() in exclude_ings or ing["category"].lower() in exclude_cats:
            continue
        key = f"{name.lower()}|{ing['unit'].lower()}"
        if key in consolidated:
            consolidated[key]["quantity"] = str(
                parse_quantity(consolidated[key]["quantity"]) + parse_quantity(ing["quantity"])
            )
        else:
            consolidated[key] = dict(ing)
    return list(consolidated.values())


def _build_line_items(consolidated, additional_items=None):
    line_items = []
    for ing in consolidated:
        item = {"name": ing["ingredient_name"].lower()}
        parts = []
        if ing["quantity"]:
            parts.append(ing["quantity"])
        if ing["unit"]:
            parts.append(ing["unit"])
        parts.append(ing["ingredient_name"])
        if ing["note"]:
            parts.append(f"({ing['note']})")
        item["display_text"] = " ".join(parts)
        qty = parse_quantity(ing["quantity"])
        if qty > 0 and ing["unit"]:
            item["measurements"] = [{"quantity": qty, "unit": ing["unit"]}]
        line_items.append(item)
    for extra in (additional_items or []):
        line_items.append({"name": extra.lower()})
    return line_items


def _call_instacart(endpoint, payload):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{INSTACART_BASE_URL}/{endpoint}", data=body,
        headers={"Authorization": f"Bearer {INSTACART_API_KEY}",
                 "Content-Type": "application/json", "Accept": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, {"error": f"Instacart API error ({e.code}): {e.read().decode('utf-8') if e.fp else str(e)}"}
    except Exception as e:
        return None, {"error": f"Instacart API failed: {str(e)}"}


def _append_affiliate(url):
    if IMPACT_PARTNER_ID and url:
        sep = "&" if "?" in url else "?"
        url += f"{sep}utm_campaign=instacart-idp&utm_medium=affiliate&utm_source=instacart_idp&utm_term=partnertype-mediapartner&utm_content=campaignid-20313_partnerid-{IMPACT_PARTNER_ID}"
    return url


# ── Tools ──

def get_shopping_list(args):
    recipe_ids = _parse_csv(args.get("recipe_ids", ""))
    if not recipe_ids:
        return {"error": "recipe_ids is required"}
    ingredients = get_ingredients_for_recipes(recipe_ids)
    consolidated = consolidate_ingredients(ingredients,
        _parse_csv(args.get("exclude_categories", "")),
        _parse_csv(args.get("exclude_ingredients", "")))
    by_category = {}
    for ing in consolidated:
        by_category.setdefault(ing["category"] or "Other", []).append(ing)
    return {"shopping_list": by_category, "total_items": len(consolidated), "recipe_count": len(recipe_ids)}


def create_instacart_cart(args):
    recipe_ids = _parse_csv(args.get("recipe_ids", ""))
    if not recipe_ids:
        return {"error": "recipe_ids is required"}
    title = args.get("title", "EZ Meals Shopping List")
    ingredients = get_ingredients_for_recipes(recipe_ids)
    consolidated = consolidate_ingredients(ingredients, _parse_csv(args.get("exclude_categories", "")), _parse_csv(args.get("exclude_ingredients", "")))
    line_items = _build_line_items(consolidated, _parse_csv(args.get("additional_items", "")))
    data, err = _call_instacart("products/products_link", {
        "title": title, "link_type": "shopping_list",
        "line_items": line_items, "landing_page_configuration": {"enable_pantry_items": True}})
    if err:
        return err
    return {"instacart_url": _append_affiliate(data.get("products_link_url", "")),
            "ingredient_count": len(line_items), "title": title}


def create_recipe_page(args):
    """Create a full Instacart recipe page with photo, instructions, and shoppable ingredients."""
    recipe_id = args.get("recipe_id", "")
    if not recipe_id:
        return {"error": "recipe_id is required"}

    side_ids = _parse_csv(args.get("side_ids", ""))
    exclude_cats = _parse_csv(args.get("exclude_categories", ""))

    # Fetch main recipe
    table = get_table()
    item = table.get_item(Key={"id": recipe_id}).get("Item")
    if not item:
        return {"error": f"Recipe not found: {recipe_id}"}

    # Auto-include recommended sides if requested
    if args.get("include_sides") and not side_ids:
        side_ids = [s for s in (item.get("recommendedSides") or []) if s]

    # Ingredients from main + sides
    all_ids = [recipe_id] + side_ids
    ingredients = get_ingredients_for_recipes(all_ids)
    consolidated = consolidate_ingredients(ingredients, exclude_cats)
    line_items = _build_line_items(consolidated)

    # Instructions — main first, then each side
    instructions = list(item.get("instructions") or [])
    if side_ids:
        for sid in side_ids:
            side = table.get_item(Key={"id": sid}).get("Item")
            if side and side.get("instructions"):
                instructions.append(f"--- {side.get('title', 'Side Dish')} ---")
                instructions.extend(side["instructions"])

    image_url = resolve_image_url(item.get("imageURL", ""))

    # Apply health filters based on recipe dietary flags
    if item.get("glutenFree"):
        for li in line_items:
            li.setdefault("filters", {})["health_filters"] = ["GLUTEN_FREE"]

    payload = {
        "title": item.get("title", "EZ Meals Recipe"),
        "image_url": image_url,
        "author": "EZ Meals",
        "instructions": instructions,
        "ingredients": line_items,
        "landing_page_configuration": {
            "enable_pantry_items": True,
            "partner_linkback_url": "https://apps.apple.com/us/app/easy-meal-planner/id1590772277",
        },
        "expires_in": 365,
    }
    servings_raw = str(item.get("servings", "") or "")
    servings = int(''.join(c for c in servings_raw.split()[0] if c.isdigit()) or 0) if servings_raw else 0
    if servings:
        payload["servings"] = servings
    cook_time = int(item.get("prepTime", 0) or 0) + int(item.get("cookTime", 0) or 0)
    if cook_time:
        payload["cooking_time"] = cook_time

    data, err = _call_instacart("products/recipe", payload)
    if err:
        return err

    result = {
        "recipe_page_url": _append_affiliate(data.get("products_link_url", "")),
        "title": item.get("title", ""),
        "ingredient_count": len(line_items),
        "instruction_count": len(instructions),
        "image_url": image_url,
    }
    if side_ids:
        result["includes_sides"] = len(side_ids)
    return result


def get_staples_table():
    creds = _get_creds()
    dynamodb = boto3.resource("dynamodb", region_name=DB_REGION,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"])
    return dynamodb.Table(STAPLES_TABLE)


def get_weekly_staples(args):
    user, err = require_auth(args)
    if err:
        return err
    table = get_staples_table()
    resp = table.query(
        IndexName="byUserID",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("userID").eq(user["user_id"])
    )
    items = [{"id": s["id"], "name": s["itemName"], "selected": s.get("isSelected", False)}
             for s in resp.get("Items", [])]
    return {"staples": items, "count": len(items)}


def add_weekly_staples(args):
    user, err = require_auth(args)
    if err:
        return err
    items = _parse_csv(args.get("items", ""))
    if not items:
        return {"error": "items is required — comma-separated list of grocery items"}
    table = get_staples_table()
    import uuid
    from datetime import datetime
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    added = []
    for item_name in items:
        cleaned = item_name.strip()
        if not cleaned:
            continue
        table.put_item(Item={
            "id": str(uuid.uuid4()),
            "userID": user["user_id"],
            "itemName": cleaned,
            "isSelected": False,
            "createdAt": now,
            "updatedAt": now,
        })
        added.append(cleaned)
    return {"added": added, "count": len(added)}


def remove_weekly_staples(args):
    user, err = require_auth(args)
    if err:
        return err
    items = _parse_csv(args.get("items", ""))
    if not items:
        return {"error": "items is required — comma-separated list of grocery items to remove"}
    table = get_staples_table()
    resp = table.query(
        IndexName="byUserID",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("userID").eq(user["user_id"])
    )
    staples = resp.get("Items", [])
    removed, not_found = [], []
    for item_name in items:
        search = item_name.strip().lower()
        match = next((s for s in staples if s["itemName"].lower() == search), None)
        if not match:
            match = next((s for s in staples if search in s["itemName"].lower()), None)
        if match:
            table.delete_item(Key={"id": match["id"]})
            removed.append(match["itemName"])
            staples = [s for s in staples if s["id"] != match["id"]]
        else:
            not_found.append(item_name.strip())
    result = {"removed": removed, "count": len(removed)}
    if not_found:
        result["not_found"] = not_found
    return result


# ── Handler ──

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

    handlers = {
        "get_shopping_list": get_shopping_list,
        "create_instacart_cart": create_instacart_cart,
        "create_recipe_page": create_recipe_page,
        "get_weekly_staples": get_weekly_staples,
        "add_weekly_staples": add_weekly_staples,
        "remove_weekly_staples": remove_weekly_staples,
    }
    result = handlers.get(tool_name, lambda a: {"error": f"Unknown tool: {tool_name}"})(args)
    return {"content": [{"type": "text", "text": json.dumps(result, cls=DecimalEncoder, default=str)}]}
