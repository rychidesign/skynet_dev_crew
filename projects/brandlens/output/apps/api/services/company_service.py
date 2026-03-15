from supabase._async.client import AsyncClient
from fastapi import HTTPException, status
from models.company import CompanyCreate, CompanyUpdate

async def get_companies(db: AsyncClient, organization_id: str) -> list[dict]:
    response = await db.table("companies") \
        .select("*") \
        .eq("organization_id", organization_id) \
        .execute()
    return response.data

async def get_company(db: AsyncClient, organization_id: str, company_id: str) -> dict:
    response = await db.table("companies") \
        .select("*") \
        .eq("organization_id", organization_id) \
        .eq("id", company_id) \
        .execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    return response.data[0]

async def create_company(db: AsyncClient, organization_id: str, company_data: CompanyCreate) -> dict:
    payload = company_data.model_dump()
    payload["organization_id"] = organization_id
    
    response = await db.table("companies") \
        .insert(payload) \
        .execute()
        
    if not response.data:
         raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create company"
        )
    return response.data[0]

async def update_company(db: AsyncClient, organization_id: str, company_id: str, company_data: CompanyUpdate) -> dict:
    update_data = company_data.model_dump(exclude_unset=True)
    if not update_data:
        # Nothing to update, just return the existing
        return await get_company(db, organization_id, company_id)

    response = await db.table("companies") \
        .update(update_data) \
        .eq("organization_id", organization_id) \
        .eq("id", company_id) \
        .execute()
        
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    return response.data[0]

async def delete_company(db: AsyncClient, organization_id: str, company_id: str) -> None:
    response = await db.table("companies") \
        .delete() \
        .eq("organization_id", organization_id) \
        .eq("id", company_id) \
        .execute()
        
    if not response.data:
         raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    return None
