"""
EZ Meals MCP — Shopping Lambda
Tools: get_shopping_list, create_instacart_cart
Consolidates ingredients across recipes and creates Instacart checkout URLs.
"""
import json
import os
import boto3
import urllib.request
import urllib.parse
from decimal import Decimal
from fractions import Fraction

ROLE_ARN = "arn:aws:iam::970547358447:role/CrossAccountDynamoDBWriter"
TABLE_NAME = "MenuItemData-ryvykzwfevawxbpf5nmynhgtea-dev"
DB_REGION = "us-west-1"
INSTACART_API_KEY = os.environ.get("INSTACART_API_KEY", "")
INSTACART_BASE_URL = os.environ.get("INSTACART_BASE_URL", "https://connect.dev.instacart.tools/idp/v1")
IMPACT_PARTNER_ID = os.environ.get("IMPACT_PARTNER_ID", "")


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o) if o % 1 else int(o)
        return super().default(o)


def get_table():
    sts = boto3.client("sts")
    creds = sts.assume_role(RoleArn=ROLE_ARN, RoleSessionName="mcp-shopping")["Credentials"]
    dynamodb = boto3.resource(
        "dynamodb", region_name=DB_REGION,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"]
    )
    return dynamodb.Table(TABLE_NAME)


def parse_quantity(qty_str):
    """Parse fraction strings like '1 1/2' to float."""
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
    """Fetch ingredient_objects for multiple recipes."""
    table = get_table()
    all_ingredients = []
    
    for rid in recipe_ids:
        resp = table.get_item(Key={"id": rid})
        item = resp.get("Item")
        if not item:
            continue
        
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
                "recipe_id": rid,
            })
    
    return all_ingredients


def consolidate_ingredients(ingredients, exclude_categories=None, exclude_ingredients=None):
    """Consolidate duplicate ingredients, aggregate quantities."""
    exclude_cats = set(c.lower() for c in (exclude_categories or []))
    exclude_ings = set(i.lower() for i in (exclude_ingredients or []))
    
    consolidated = {}
    for ing in ingredients:
        name = ing["ingredient_name"]
        if name.lower() in exclude_ings:
            continue
        if ing["category"].lower() in exclude_cats:
            continue
        
        key = f"{name.lower()}|{ing['unit'].lower()}"
        if key in consolidated:
            existing_qty = parse_quantity(consolidated[key]["quantity"])
            new_qty = parse_quantity(ing["quantity"])
            total = existing_qty + new_qty
            consolidated[key]["quantity"] = str(total) if total else ""
        else:
            consolidated[key] = {
                "ingredient_name": name,
                "quantity": ing["quantity"],
                "unit": ing["unit"],
                "category": ing["category"],
                "note": ing.get("note", ""),
            }
    
    return list(consolidated.values())


def get_shopping_list(args):
    recipe_ids = args.get("recipe_ids", "")
    if isinstance(recipe_ids, str):
        recipe_ids = [r.strip() for r in recipe_ids.split(",") if r.strip()]
    if not recipe_ids:
        return {"error": "recipe_ids is required"}
    
    exclude_cats = args.get("exclude_categories", "")
    if isinstance(exclude_cats, str):
        exclude_cats = [c.strip() for c in exclude_cats.split(",") if c.strip()]
    exclude_ings = args.get("exclude_ingredients", "")
    if isinstance(exclude_ings, str):
        exclude_ings = [i.strip() for i in exclude_ings.split(",") if i.strip()]
    
    ingredients = get_ingredients_for_recipes(recipe_ids)
    consolidated = consolidate_ingredients(ingredients, exclude_cats, exclude_ings)
    
    # Group by category
    by_category = {}
    for ing in consolidated:
        cat = ing["category"] or "Other"
        by_category.setdefault(cat, []).append(ing)
    
    return {
        "shopping_list": by_category,
        "total_items": len(consolidated),
        "recipe_count": len(recipe_ids),
    }


def create_instacart_cart(args):
    recipe_ids = args.get("recipe_ids", "")
    if isinstance(recipe_ids, str):
        recipe_ids = [r.strip() for r in recipe_ids.split(",") if r.strip()]
    if not recipe_ids:
        return {"error": "recipe_ids is required"}
    
    title = args.get("title", "EZ Meals Shopping List")
    exclude_cats = args.get("exclude_categories", "")
    if isinstance(exclude_cats, str):
        exclude_cats = [c.strip() for c in exclude_cats.split(",") if c.strip()]
    exclude_ings = args.get("exclude_ingredients", "")
    if isinstance(exclude_ings, str):
        exclude_ings = [i.strip() for i in exclude_ings.split(",") if i.strip()]
    additional_items = args.get("additional_items", "")
    if isinstance(additional_items, str):
        additional_items = [i.strip() for i in additional_items.split(",") if i.strip()]
    
    # Get and consolidate ingredients
    ingredients = get_ingredients_for_recipes(recipe_ids)
    consolidated = consolidate_ingredients(ingredients, exclude_cats, exclude_ings)
    
    # Build Instacart line_items
    line_items = []
    for ing in consolidated:
        item = {"name": ing["ingredient_name"].lower()}
        
        # Display text
        parts = []
        if ing["quantity"]:
            parts.append(ing["quantity"])
        if ing["unit"]:
            parts.append(ing["unit"])
        parts.append(ing["ingredient_name"])
        if ing["note"]:
            parts.append(f"({ing['note']})")
        item["display_text"] = " ".join(parts)
        
        # Measurements
        qty = parse_quantity(ing["quantity"])
        if qty > 0 and ing["unit"]:
            item["measurements"] = [{"quantity": qty, "unit": ing["unit"]}]
        
        line_items.append(item)
    
    # Add additional items
    for extra in additional_items:
        line_items.append({"name": extra.lower()})
    
    # Call Instacart API
    body = json.dumps({
        "title": title,
        "link_type": "shopping_list",
        "line_items": line_items,
        "landing_page_configuration": {"enable_pantry_items": True}
    }).encode("utf-8")
    
    req = urllib.request.Request(
        f"{INSTACART_BASE_URL}/products/products_link",
        data=body,
        headers={
            "Authorization": f"Bearer {INSTACART_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            url = data.get("products_link_url", "")
            
            # Append affiliate params if configured
            if IMPACT_PARTNER_ID:
                sep = "&" if "?" in url else "?"
                url += f"{sep}utm_campaign=instacart-idp&utm_medium=affiliate&utm_source=instacart_idp&utm_term=partnertype-mediapartner&utm_content=campaignid-20313_partnerid-{IMPACT_PARTNER_ID}"
            
            return {
                "instacart_url": url,
                "ingredient_count": len(line_items),
                "title": title,
            }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        return {"error": f"Instacart API error ({e.code}): {error_body}"}
    except Exception as e:
        return {"error": f"Failed to create Instacart cart: {str(e)}"}


def lambda_handler(event, context):
    """MCP Lambda handler."""
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
    
    logging.info(f"TOOL: {tool_name}, ARGS: {json.dumps(args, default=str)}")

    if tool_name == "get_shopping_list":
        result = get_shopping_list(args)
    elif tool_name == "create_instacart_cart":
        result = create_instacart_cart(args)
    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return {"content": [{"type": "text", "text": json.dumps(result, cls=DecimalEncoder, default=str)}]}
