import os
from uuid import UUID
from typing import Callable, Coroutine, Any

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase._async.client import AsyncClient, create_client
from supabase.lib.client_options import ClientOptions

from .auth import AuthUser, OrgMemberContext, verify_supabase_jwt, ROLE_WEIGHTS

security = HTTPBearer()

async def get_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Extracts the Bearer token from the HTTP Authorization header."""
    return credentials.credentials

async def get_current_user(token: str = Depends(get_token)) -> AuthUser:
    """Validates the JWT and returns the AuthUser model."""
    return verify_supabase_jwt(token)

async def get_db(token: str = Depends(get_token)) -> AsyncClient:
    """
    Provides a Supabase AsyncClient initialized with the user's JWT.
    This ensures that all queries executed with this client respect PostgreSQL RLS policies.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_anon_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: Missing Supabase credentials."
        )

    options = ClientOptions(headers={"Authorization": f"Bearer {token}"})
    client = await create_client(supabase_url, supabase_anon_key, options=options)
    return client

async def get_service_db() -> AsyncClient:
    """
    Provides a Supabase AsyncClient initialized with the Service Role Key.
    This BYPASSES RLS. It should ONLY be used for internal agent pipeline writes 
    or background tasks, NEVER for frontend-facing queries.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_service_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: Missing Supabase Service credentials."
        )

    client = await create_client(supabase_url, supabase_service_key)
    return client

async def get_org_context(
    x_organization_id: UUID = Header(..., alias="X-Organization-Id"),
    user: AuthUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db)
) -> OrgMemberContext:
    """
    Resolves the organization context by querying the database to ensure the user
    is a member of the requested organization and retrieves their role.
    """
    try:
        response = await db.table("organization_members") \
            .select("role") \
            .eq("organization_id", str(x_organization_id)) \
            .eq("user_id", str(user.id)) \
            .single() \
            .execute()
        
        data = response.data
        if not data:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this organization."
            )
            
        role = data.get("role")
        if not role:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid role assigned."
            )

        return OrgMemberContext(
            user=user,
            organization_id=x_organization_id,
            role=role
        )
    except Exception as e:
        # Handle cases where single() fails because no rows are returned (or multiple, though constrained)
        if hasattr(e, "code") and e.code == "PGRST116": # PostgREST error for exactly one row not found
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this organization."
            )
        # Re-raise HTTPExceptions
        if isinstance(e, HTTPException):
            raise e
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error verifying membership: {str(e)}"
        )

def require_role(min_role: str) -> Callable[..., Coroutine[Any, Any, OrgMemberContext]]:
    """
    Dependency factory that returns a dependency function to check if the current
    user has at least the required role in the organization.
    """
    if min_role not in ROLE_WEIGHTS:
        raise ValueError(f"Invalid role defined in endpoint requirement: {min_role}")

    async def role_checker(ctx: OrgMemberContext = Depends(get_org_context)) -> OrgMemberContext:
        user_role_weight = ROLE_WEIGHTS.get(ctx.role, -1)
        required_role_weight = ROLE_WEIGHTS[min_role]

        if user_role_weight < required_role_weight:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Requires at least '{min_role}' role."
            )
        
        return ctx

    return role_checker
