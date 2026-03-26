"""
EZ Meals MCP — Auth Lambda
Tools: signup, login
Uses the existing EZ Meals Cognito User Pool for authentication.
"""
import json
import boto3

USER_POOL_ID = "us-west-1_c6QDYtV20"
CLIENT_ID = "46p8romfbtt87krtrsfv7cds3g"
COGNITO_REGION = "us-west-1"


def get_cognito():
    return boto3.client("cognito-idp", region_name=COGNITO_REGION)


def signup(args):
    email = args.get("email", "").strip()
    password = args.get("password", "").strip()
    
    if not email or not password:
        return {"error": "email and password are required"}
    if len(password) < 8:
        return {"error": "Password must be at least 8 characters"}
    
    client = get_cognito()
    
    try:
        resp = client.sign_up(
            ClientId=CLIENT_ID,
            Username=email,
            Password=password,
            UserAttributes=[
                {"Name": "email", "Value": email}
            ]
        )
        
        confirmed = resp.get("UserConfirmed", False)
        
        if confirmed:
            return {
                "status": "success",
                "message": f"Account created for {email}. You can now use the login tool.",
                "email": email
            }
        else:
            return {
                "status": "confirmation_required",
                "message": f"Account created for {email}. A verification code was sent to your email. Use the confirm_signup tool with the code.",
                "email": email
            }
    except client.exceptions.UsernameExistsException:
        return {"error": f"An account with {email} already exists. Use the login tool instead."}
    except client.exceptions.InvalidPasswordException as e:
        return {"error": f"Password doesn't meet requirements: {str(e)}"}
    except Exception as e:
        return {"error": f"Signup failed: {str(e)}"}


def confirm_signup(args):
    email = args.get("email", "").strip()
    code = args.get("code", "").strip()
    
    if not email or not code:
        return {"error": "email and code are required"}
    
    client = get_cognito()
    
    try:
        client.confirm_sign_up(
            ClientId=CLIENT_ID,
            Username=email,
            ConfirmationCode=code
        )
        return {
            "status": "success",
            "message": f"Email verified for {email}. You can now use the login tool."
        }
    except client.exceptions.CodeMismatchException:
        return {"error": "Invalid verification code. Please try again."}
    except client.exceptions.ExpiredCodeException:
        return {"error": "Verification code expired. Request a new one."}
    except Exception as e:
        return {"error": f"Confirmation failed: {str(e)}"}


def login(args):
    email = args.get("email", "").strip()
    password = args.get("password", "").strip()
    
    if not email or not password:
        return {"error": "email and password are required"}
    
    client = get_cognito()
    
    try:
        resp = client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": email,
                "PASSWORD": password
            }
        )
        
        auth_result = resp.get("AuthenticationResult", {})
        
        return {
            "status": "success",
            "message": f"Logged in as {email}. Pass the access_token as 'auth_token' parameter to all other tools for full access.",
            "access_token": auth_result.get("AccessToken", ""),
            "expires_in": auth_result.get("ExpiresIn", 3600),
            "usage": "Include auth_token in every tool call. Example: search_recipes(cuisine='Italian', auth_token='your-token-here')"
        }
    except client.exceptions.NotAuthorizedException:
        return {"error": "Incorrect email or password."}
    except client.exceptions.UserNotConfirmedException:
        return {"error": f"Email not verified for {email}. Check your email for a verification code and use the confirm_signup tool."}
    except client.exceptions.UserNotFoundException:
        return {"error": f"No account found for {email}. Use the signup tool to create one."}
    except Exception as e:
        return {"error": f"Login failed: {str(e)}"}


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
    
    # Don't log passwords
    safe_args = {k: v for k, v in args.items() if k != "password"}
    logging.info(f"TOOL: {tool_name}, ARGS: {safe_args}")

    if tool_name == "signup":
        result = signup(args)
    elif tool_name == "confirm_signup":
        result = confirm_signup(args)
    elif tool_name == "login":
        result = login(args)
    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
