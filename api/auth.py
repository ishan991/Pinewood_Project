from datetime import datetime, timedelta, timezone

import jwt

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from users import users


# --------------------------------------------------
# Password hashing
# --------------------------------------------------

password_hash = PasswordHash.recommended()


# --------------------------------------------------
# JWT settings
# --------------------------------------------------

SECRET_KEY = "pinewood-secret-key"
ALGORITHM = "HS256"


# --------------------------------------------------
# OAuth2 token reader
# --------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token"
)


# --------------------------------------------------
# Authenticate username and password
# --------------------------------------------------

def authenticate_user(username: str, password: str):

    # Find user in users dictionary
    user = users.get(username)

    # Username does not exist
    if user is None:
        return None

    # Verify entered password against stored hash
    password_is_correct = password_hash.verify(
        password,
        user["hashed_password"]
    )

    # Password is incorrect
    if not password_is_correct:
        return None

    # Username and password are correct
    return user


# --------------------------------------------------
# Create JWT access token
# --------------------------------------------------

def create_access_token(username: str, role: str):

    # Token will expire after 30 minutes
    expire_time = (
        datetime.now(timezone.utc)
        + timedelta(minutes=30)
    )

    # Data stored inside JWT
    token_data = {
        "sub": username,
        "role": role,
        "exp": expire_time
    }

    # Create signed JWT
    token = jwt.encode(
        token_data,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token


# --------------------------------------------------
# Validate JWT and identify current user
# --------------------------------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme)
):

    # Error returned when token is missing/invalid/expired
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={
            "WWW-Authenticate": "Bearer"
        }
    )

    try:

        # Decode JWT
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        # Get username stored in token
        username = payload.get("sub")

        # Token does not contain username
        if username is None:
            raise credentials_exception

    except InvalidTokenError:

        # Invalid signature, expired token, malformed token, etc.
        raise credentials_exception

    # Check user still exists
    user = users.get(username)

    if user is None:
        raise credentials_exception

    return user


def require_admin(
    current_user=Depends(get_current_user)
):

    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return current_user