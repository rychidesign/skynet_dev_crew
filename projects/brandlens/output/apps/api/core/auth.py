import jwt
from typing import Dict
from uuid import UUID
from pydantic import BaseModel
from fastapi import HTTPException, status
import os

# Define the role hierarchy mapping for comparison
ROLE_WEIGHTS: Dict[str, int] = {
    "viewer": 0,
    "analyst": 1,
    "admin": 2,
    "owner": 3
}

class AuthUser(BaseModel):
    id: UUID
    email: str

class OrgMemberContext(BaseModel):
    user: AuthUser
    organization_id: UUID
    role: str

def verify_supabase_jwt(token: str) -> AuthUser:
    """
    Verifies the Supabase JWT using the JWT secret.
    Extracts the 'sub' (user_id) and 'email' claims.
    Raises an HTTPException if the token is invalid, expired, or missing claims.
    """
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    
    if not jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: SUPABASE_JWT_SECRET is missing."
        )

    try:
        # Supabase uses HS256 algorithm by default
        payload = jwt.decode(
            token, 
            jwt_secret, 
            algorithms=["HS256"], 
            options={"verify_aud": False}
        )
        
        user_id_str = payload.get("sub")
        email = payload.get("email")

        if not user_id_str or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: missing 'sub' or 'email'.",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        return AuthUser(id=UUID(user_id_str), email=email)

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
