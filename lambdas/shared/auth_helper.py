"""
Shared auth validation for EZ Meals MCP Lambdas.
Validates Cognito access tokens and resolves account links.
"""
import boto3
import json

COGNITO_REGION = "us-west-1"
USER_POOL_ID = "us-west-1_c6QDYtV20"
ROLE_ARN = "arn:aws:iam::970547358447:role/IsengardAccount-DynamoDBAccess"
ACCOUNT_LINK_TABLE = "AccountLink-ryvykzwfevawxbpf5nmynhgtea-dev"
DB_REGION = "us-west-1"

_cognito = None
_link_table = None


def get_cognito():
    global _cognito
    if not _cognito:
        _cognito = boto3.client("cognito-idp", region_name=COGNITO_REGION)
    return _cognito


def _get_link_table():
    global _link_table
    if not _link_table:
        sts = boto3.client("sts")
        creds = sts.assume_role(RoleArn=ROLE_ARN, RoleSessionName="mcp-auth")["Credentials"]
        dynamodb = boto3.resource("dynamodb", region_name=DB_REGION,
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"])
        _link_table = dynamodb.Table(ACCOUNT_LINK_TABLE)
    return _link_table


def _resolve_effective_user_id(user_id):
    """Check if this user is linked to a primary account. Returns primaryUserId or own user_id."""
    try:
        table = _get_link_table()
        resp = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr("linkedUserId").eq(user_id)
        )
        items = resp.get("Items", [])
        if items:
            return items[0].get("primaryUserId", user_id)
    except Exception:
        pass
    return user_id


def validate_token(auth_token):
    """Validate a Cognito access token. Returns user info or None."""
    if not auth_token:
        return None
    try:
        resp = get_cognito().get_user(AccessToken=auth_token)
        email = ""
        sub = ""
        for attr in resp.get("UserAttributes", []):
            if attr["Name"] == "email":
                email = attr["Value"]
            elif attr["Name"] == "sub":
                sub = attr["Value"]
        raw_user_id = sub or resp["Username"]
        effective_user_id = _resolve_effective_user_id(raw_user_id)
        return {
            "username": resp["Username"],
            "email": email,
            "user_id": effective_user_id,
            "raw_user_id": raw_user_id,
            "is_linked": effective_user_id != raw_user_id,
        }
    except Exception:
        return None


def require_auth(args):
    """Check auth_token in args. Returns (user_info, error_response).
    If authenticated: (user_info, None) — user_id is the effective (primary) ID
    If guest: (None, error_dict)
    """
    token = args.get("auth_token", "")
    if not token:
        return None, {
            "error": "authentication_required",
            "message": "This tool requires a free EZ Meals account.",
            "action": "Call the login tool with your email and password to get an auth_token. No account? Call signup first — it's completely free.",
            "guest_tools": ["search_recipes", "browse_cuisines", "signup", "confirm_signup", "login"]
        }
    
    user = validate_token(token)
    if not user:
        return None, {
            "error": "invalid_token",
            "message": "Your auth_token is invalid or expired. Call the login tool to get a fresh token."
        }
    
    return user, None
