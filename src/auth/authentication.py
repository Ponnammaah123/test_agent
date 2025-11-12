from fastapi import Depends, HTTPException, Header
import jwt
import os
import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from dotenv import load_dotenv

# Configuration
ALGORITHM = "RS256"


async def authenticate_user(authorization: str = Header(None)):
    """
    Dependency to authenticate the user based on the Authorization header.

    Args:
        authorization (str): The Authorization header containing the JWT token.

    Raises:
        HTTPException: If the token is missing, invalid, or expired.

    Returns:
        dict: Decoded token data if valid.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header is missing")
    # Check for 'Bearer ' prefix
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    token = authorization[7:]  # Strip the 'Bearer ' prefix
    try:
        # Load the public key from environment variables
        public_key = load_public_key_from_env("SECRET_KEY")
        # Decode and validate the token
        payload = jwt.decode(token, public_key, algorithms=[ALGORITHM], options={"verify_exp": True},leeway=30)
        # Validate required fields
        required_fields = ["type", "jti", "UserInfo", "appKey", "services", "appName", "industry", "exp"]
        for field in required_fields:
            if field not in payload:
                raise HTTPException(status_code=401, detail=f"Missing required field: {field}")

        # Check `type`
        if payload["type"] != "at":
            raise HTTPException(status_code=401, detail="Invalid token type")

        # Validate `UserInfo`
        user_info = payload["UserInfo"]
        if not user_info.get("id") or not user_info.get("email"):
            raise HTTPException(status_code=401, detail="Invalid UserInfo in token")

        # Validate `appKey`
        if not payload["appKey"]:
            raise HTTPException(status_code=401, detail="Invalid appKey in token")

        # Validate `services`
        if not isinstance(payload["services"], list) or not payload["services"]:
            raise HTTPException(status_code=401, detail="Invalid services in token")

        # Validate `industry` (UUID format check)
        if not isinstance(payload["industry"], str) or len(payload["industry"]) != 36:
            raise HTTPException(status_code=401, detail="Invalid industry in token")

        # Validate `appId` and `appName`
        if not payload.get("appId") or not payload.get("appName"):
            raise HTTPException(status_code=401, detail="Invalid appId or appName in token")

        # Validate `iat` and `exp`
        current_time = datetime.datetime.utcnow().timestamp()
        if payload["exp"] < current_time:
            raise HTTPException(status_code=401, detail="Token has expired")
        # Return the payload if all validations pass
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token validation error: {str(e)}")

def load_public_key_from_env(env_var_name: str) -> serialization.PublicFormat:
    """
    Loads and deserializes a public key from an environment variable.

    Args:
        env_var_name (str): The name of the environment variable containing the public key.

    Returns:
        serialization.PublicFormat: The loaded public key.

    Raises:
        ValueError: If the key cannot be deserialized or is in an incorrect format.
    """
    dotenv_path = os.path.join(os.path.dirname(__file__), "../config/.env")

        # Load the environment variables from the .env file
    load_dotenv(dotenv_path)
    key_data = os.getenv(env_var_name)
    if not key_data:
        raise ValueError(f"The environment variable '{env_var_name}' is not set or empty.")

    # Replace escaped line breaks with actual line breaks
    key_data = key_data.replace("\\n", "\n")

    try:
        public_key = serialization.load_pem_public_key(
            key_data.encode(),
            backend=default_backend()
        )
        # print("Public key loaded successfully!")
        return public_key
    except Exception as e:
        raise ValueError(f"Failed to load public key: {e}")

