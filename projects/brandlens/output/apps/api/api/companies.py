from fastapi import APIRouter, Depends, status
from supabase._async.client import AsyncClient
from core.dependencies import get_db, require_role, OrgMemberContext
from models.company import CompanyResponse, CompanyCreate, CompanyUpdate
from services import company_service

router = APIRouter(prefix="/companies", tags=["companies"])

@router.get("/", response_model=list[CompanyResponse])
async def list_companies(
    db: AsyncClient = Depends(get_db),
    ctx: OrgMemberContext = Depends(require_role("viewer"))
):
    return await company_service.get_companies(db, str(ctx.organization_id))

@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: str,
    db: AsyncClient = Depends(get_db),
    ctx: OrgMemberContext = Depends(require_role("viewer"))
):
    return await company_service.get_company(db, str(ctx.organization_id), company_id)

@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    company_data: CompanyCreate,
    db: AsyncClient = Depends(get_db),
    ctx: OrgMemberContext = Depends(require_role("analyst"))
):
    return await company_service.create_company(db, str(ctx.organization_id), company_data)

@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: str,
    company_data: CompanyUpdate,
    db: AsyncClient = Depends(get_db),
    ctx: OrgMemberContext = Depends(require_role("analyst"))
):
    return await company_service.update_company(db, str(ctx.organization_id), company_id, company_data)

@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: str,
    db: AsyncClient = Depends(get_db),
    ctx: OrgMemberContext = Depends(require_role("analyst"))
):
    await company_service.delete_company(db, str(ctx.organization_id), company_id)
