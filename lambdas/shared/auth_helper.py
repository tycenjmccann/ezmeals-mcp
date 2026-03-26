"""
Shared auth validation for EZ Meals MCP Lambdas.
Validates Cognito access tokens passed by agents.
"""
import boto3
import json

COGNITO_REGION = "us-west-1"
USER_POOL_ID = "us-west-1_c6QDYtV20"

_cognito = None

def get_cognito():
    global _cognito
    if not _cognito:
        _cognito = boto3.client("cognito-idp", region_name=COGNITO_REGION)
    return _cognito


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
        return {"username": resp["Username"], "email": email, "user_id": sub or resp["Username"]}
    except Exception:
        return None


def require_auth(args):
    """Check auth_token in args. Returns (user_info, error_response).
    If authenticated: (user_info, None)
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
