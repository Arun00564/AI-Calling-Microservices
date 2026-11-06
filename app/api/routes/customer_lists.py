import json

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession


from app.db.database import get_db
from app.db.models.user_details import UserDetails
from app.api.dependencies import get_current_user
from app.services.customer_list import CustomerListService
from app.schemas.customer_list import ManualCustomerListRequest

import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/customer-lists",
    tags=["Customer Lists"],
)


@router.post("/import")
async def import_customer_list(
    name: str = Form(...),
    file: UploadFile = File(...),
    tags: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    allowed_extensions = (".xlsx", ".xls", ".csv")

    if not file.filename or not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail="Only XLSX, XLS and CSV files are supported.",
        )

    file_content = await file.read()

    if not file_content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    parsed_tags = None

    if tags:
        try:
            parsed_tags = json.loads(tags)

            if not isinstance(parsed_tags, list) or not all(
                isinstance(tag, str) for tag in parsed_tags
            ):
                raise ValueError()

        except (ValueError, json.JSONDecodeError):
            raise HTTPException(
                status_code=400,
                detail="Tags must be a JSON array of strings.",
            )

    service = CustomerListService(
        db=db,
        current_user=current_user,
    )

    try:
        result = await service.import_contacts(
            name=name.strip(),
            file_name=file.filename,
            file_content=file_content,
            tags=parsed_tags,
        )

        return {
            "status": 200,
            "success": True,
            "message": "Customer list imported successfully.",
            "data": result,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception:
        await db.rollback()
        logger.exception("Customer list import failed")
        raise HTTPException(
            status_code=500,
            detail="Unable to import customer list.",
        )


@router.post("/manual")
async def create_manual_customer_list(
    request: ManualCustomerListRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):

    service = CustomerListService(
        db=db,
        current_user=current_user,
    )

    try:
        result = await service.create_manual_list(
            name=request.name,
            contacts=[contact.model_dump() for contact in request.contacts],
            tags=request.tags,
        )

        return {
            "status": 200,
            "success": True,
            "message": "Customer list created successfully.",
            "data": result,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to create customer list.",
        )


@router.get("/")
async def get_customer_lists(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
    source: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):

    service = CustomerListService(
        db=db,
        current_user=current_user,
    )

    result = await service.get_customer_lists(
        page=page,
        page_size=page_size,
        search=search,
        source=source,
        status=status,
    )

    return {
        "status": 200,
        "success": True,
        "message": "Customer lists fetched successfully.",
        "data": result,
    }


@router.get("/{list_id}/contacts")
async def get_customer_list_contacts(
    list_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):

    service = CustomerListService(
        db=db,
        current_user=current_user,
    )

    try:
        result = await service.get_customer_list_contacts(
            list_id=list_id,
            page=page,
            page_size=page_size,
            search=search,
            status=status,
        )

        return {
            "status": 200,
            "success": True,
            "message": "Customer list contacts fetched successfully.",
            "data": result,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@router.get("/contacts/all")
async def get_all_contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
    status: str | None = Query(None),
    call_status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    service = CustomerListService(db=db, current_user=current_user)

    result = await service.get_all_contacts(
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        call_status=call_status,
    )

    return {
        "status": 200,
        "success": True,
        "message": "Contacts fetched successfully.",
        "data": result,
    }


@router.get("/contacts/{customer_id}/call-history")
async def get_customer_call_history(
    customer_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: UserDetails = Depends(get_current_user),
):
    service = CustomerListService(db=db, current_user=current_user)

    try:
        result = await service.get_customer_call_history(
            customer_id=customer_id,
            page=page,
            page_size=page_size,
        )

        return {
            "status": 200,
            "success": True,
            "message": "Customer call history fetched successfully.",
            "data": result,
        }

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
