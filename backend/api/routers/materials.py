"""
原药与助剂管理路由
提供原药 / 助剂的增删改查、分页查询与筛选能力
"""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, StringConstraints

from api.dependencies import get_database
from infra.database import DatabaseManager


router = APIRouter()

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ALLOWED_PAGE_SIZES = {10, 20, 50, 100}


class DeleteResponse(BaseModel):
    """删除响应"""

    success: bool
    message: str


class PaginationMeta(BaseModel):
    """分页元数据"""

    total: int
    page: int
    page_size: int
    total_pages: int


class PesticidePayload(BaseModel):
    """原药创建 / 更新请求"""

    name_cn: NonEmptyStr = Field(..., description="中文名")
    name_en: NonEmptyStr = Field(..., description="英文名")
    aliases: NonEmptyStr = Field(..., description="别名")
    chemical_class: NonEmptyStr = Field(..., description="化学分类")
    cas_number: NonEmptyStr = Field(..., description="CAS 号")
    molecular_info: NonEmptyStr = Field(..., description="分子信息")
    physicochemical: NonEmptyStr = Field(..., description="理化性质")
    bioactivity: NonEmptyStr = Field(..., description="生物活性")
    toxicology: NonEmptyStr = Field(..., description="毒理学")
    resistance_risk: NonEmptyStr = Field(..., description="抗性风险")
    first_aid: NonEmptyStr = Field(..., description="急救措施")
    safety_notes: NonEmptyStr = Field(..., description="安全注意事项")


class PesticideListItem(BaseModel):
    """原药列表项"""

    id: int
    name_cn: str
    name_en: Optional[str] = None
    aliases: Optional[str] = None
    chemical_class: Optional[str] = None
    cas_number: Optional[str] = None
    molecular_info: Optional[str] = None
    created_at: datetime


class PesticideInfo(PesticideListItem):
    """原药详情"""

    physicochemical: Optional[str] = None
    bioactivity: Optional[str] = None
    toxicology: Optional[str] = None
    resistance_risk: Optional[str] = None
    first_aid: Optional[str] = None
    safety_notes: Optional[str] = None
    updated_at: datetime


class PesticideListResponse(PaginationMeta):
    """原药分页响应"""

    items: list[PesticideListItem]


class PesticideOptionsResponse(BaseModel):
    """原药筛选选项"""

    chemical_classes: list[str]


class AdjuvantPayload(BaseModel):
    """助剂创建 / 更新请求"""

    formulation_type: NonEmptyStr = Field(..., description="剂型")
    product_name: NonEmptyStr = Field(..., description="商品名")
    function: NonEmptyStr = Field(..., description="功能")
    adjuvant_type: NonEmptyStr = Field(..., description="助剂类型")
    appearance: NonEmptyStr = Field(..., description="外观")
    ph_range: NonEmptyStr = Field(..., description="pH 范围")
    remarks: NonEmptyStr = Field(..., description="备注")
    company: NonEmptyStr = Field(..., description="公司")


class AdjuvantListItem(BaseModel):
    """助剂列表项"""

    id: int
    formulation_type: str
    product_name: str
    function: Optional[str] = None
    adjuvant_type: Optional[str] = None
    appearance: Optional[str] = None
    ph_range: Optional[str] = None
    remarks: Optional[str] = None
    company: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AdjuvantListResponse(PaginationMeta):
    """助剂分页响应"""

    items: list[AdjuvantListItem]


class AdjuvantOptionsResponse(BaseModel):
    """助剂筛选选项"""

    formulation_types: list[str]
    functions: list[str]
    companies: list[str]


def _ensure_page_size(page_size: int) -> None:
    if page_size not in ALLOWED_PAGE_SIZES:
        allowed = "、".join(str(size) for size in sorted(ALLOWED_PAGE_SIZES))
        raise HTTPException(status_code=422, detail=f"page_size 仅支持 {allowed}")


def _trim_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _total_pages(total: int, page_size: int) -> int:
    return max(1, (total + page_size - 1) // page_size)


@router.get("/pesticides/options", response_model=PesticideOptionsResponse)
async def get_pesticide_options(
    db: DatabaseManager = Depends(get_database)
):
    """获取原药筛选选项"""
    return PesticideOptionsResponse(
        chemical_classes=db.list_pesticide_classes()
    )


@router.get("/pesticides", response_model=PesticideListResponse)
async def list_pesticides(
    keyword: Optional[str] = Query(None, description="关键词，匹配中文名/英文名/别名"),
    chemical_class: Optional[str] = Query(None, description="化学分类"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    db: DatabaseManager = Depends(get_database)
):
    """分页查询原药"""
    _ensure_page_size(page_size)

    items, total = db.search_pesticides(
        keyword=_trim_optional(keyword),
        chemical_class=_trim_optional(chemical_class),
        page=page,
        page_size=page_size,
    )

    return PesticideListResponse(
        items=[PesticideListItem(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=_total_pages(total, page_size),
    )


@router.post(
    "/pesticides",
    response_model=PesticideInfo,
    status_code=status.HTTP_201_CREATED,
)
async def create_pesticide(
    request: PesticidePayload,
    db: DatabaseManager = Depends(get_database)
):
    """新增原药"""
    duplicate = db.get_pesticide_by_name(request.name_cn)
    if duplicate:
        raise HTTPException(status_code=409, detail=f"原药“{request.name_cn}”已存在")

    try:
        pesticide_id = db.create_pesticide(**request.model_dump())
        pesticide = db.get_pesticide(pesticide_id)
        if not pesticide:
            raise HTTPException(status_code=500, detail="创建原药后未能读取详情")
        return PesticideInfo(**pesticide)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"创建原药失败: {exc}") from exc


@router.get("/pesticides/{pesticide_id}", response_model=PesticideInfo)
async def get_pesticide(
    pesticide_id: int,
    db: DatabaseManager = Depends(get_database)
):
    """获取原药详情"""
    try:
        pesticide = db.get_pesticide(pesticide_id)
        if not pesticide:
            raise HTTPException(status_code=404, detail="原药不存在")
        return PesticideInfo(**pesticide)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取原药失败: {exc}") from exc


@router.put("/pesticides/{pesticide_id}", response_model=PesticideInfo)
async def update_pesticide(
    pesticide_id: int,
    request: PesticidePayload,
    db: DatabaseManager = Depends(get_database)
):
    """更新原药"""
    try:
        existing = db.get_pesticide(pesticide_id)
        if not existing:
            raise HTTPException(status_code=404, detail="原药不存在")

        duplicate = db.get_pesticide_by_name(request.name_cn)
        if duplicate and duplicate["id"] != pesticide_id:
            raise HTTPException(status_code=409, detail=f"原药“{request.name_cn}”已存在")

        success = db.update_pesticide(pesticide_id=pesticide_id, **request.model_dump())
        if not success:
            raise HTTPException(status_code=500, detail="更新原药失败")

        updated = db.get_pesticide(pesticide_id)
        if not updated:
            raise HTTPException(status_code=500, detail="更新原药后未能读取详情")
        return PesticideInfo(**updated)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"更新原药失败: {exc}") from exc


@router.delete("/pesticides/{pesticide_id}", response_model=DeleteResponse)
async def delete_pesticide(
    pesticide_id: int,
    db: DatabaseManager = Depends(get_database)
):
    """删除原药"""
    try:
        success = db.delete_pesticide(pesticide_id)
        if not success:
            raise HTTPException(status_code=404, detail="原药不存在")
        return DeleteResponse(success=True, message="原药删除成功")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除原药失败: {exc}") from exc


@router.get("/adjuvants/options", response_model=AdjuvantOptionsResponse)
async def get_adjuvant_options(
    db: DatabaseManager = Depends(get_database)
):
    """获取助剂筛选选项"""
    return AdjuvantOptionsResponse(
        formulation_types=db.list_adjuvant_formulation_types(),
        functions=db.list_adjuvant_functions(),
        companies=db.list_adjuvant_companies(),
    )


@router.get("/adjuvants", response_model=AdjuvantListResponse)
async def list_adjuvants(
    keyword: Optional[str] = Query(None, description="关键词，匹配商品名"),
    formulation_type: Optional[str] = Query(None, description="剂型"),
    function: Optional[str] = Query(None, description="功能"),
    company: Optional[str] = Query(None, description="公司"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    db: DatabaseManager = Depends(get_database)
):
    """分页查询助剂"""
    _ensure_page_size(page_size)

    items, total = db.search_adjuvants(
        keyword=_trim_optional(keyword),
        formulation_type=_trim_optional(formulation_type),
        function=_trim_optional(function),
        company=_trim_optional(company),
        page=page,
        page_size=page_size,
    )

    return AdjuvantListResponse(
        items=[AdjuvantListItem(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=_total_pages(total, page_size),
    )


@router.post(
    "/adjuvants",
    response_model=AdjuvantListItem,
    status_code=status.HTTP_201_CREATED,
)
async def create_adjuvant(
    request: AdjuvantPayload,
    db: DatabaseManager = Depends(get_database)
):
    """新增助剂"""
    duplicate = db.get_adjuvant_by_product_name(request.product_name)
    if duplicate:
        raise HTTPException(status_code=409, detail=f"助剂“{request.product_name}”已存在")

    try:
        adjuvant_id = db.create_adjuvant(**request.model_dump())
        adjuvant = db.get_adjuvant(adjuvant_id)
        if not adjuvant:
            raise HTTPException(status_code=500, detail="创建助剂后未能读取详情")
        return AdjuvantListItem(**adjuvant)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"创建助剂失败: {exc}") from exc


@router.get("/adjuvants/{adjuvant_id}", response_model=AdjuvantListItem)
async def get_adjuvant(
    adjuvant_id: int,
    db: DatabaseManager = Depends(get_database)
):
    """获取助剂详情"""
    try:
        adjuvant = db.get_adjuvant(adjuvant_id)
        if not adjuvant:
            raise HTTPException(status_code=404, detail="助剂不存在")
        return AdjuvantListItem(**adjuvant)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取助剂失败: {exc}") from exc


@router.put("/adjuvants/{adjuvant_id}", response_model=AdjuvantListItem)
async def update_adjuvant(
    adjuvant_id: int,
    request: AdjuvantPayload,
    db: DatabaseManager = Depends(get_database)
):
    """更新助剂"""
    try:
        existing = db.get_adjuvant(adjuvant_id)
        if not existing:
            raise HTTPException(status_code=404, detail="助剂不存在")

        duplicate = db.get_adjuvant_by_product_name(request.product_name)
        if duplicate and duplicate["id"] != adjuvant_id:
            raise HTTPException(status_code=409, detail=f"助剂“{request.product_name}”已存在")

        success = db.update_adjuvant(adjuvant_id=adjuvant_id, **request.model_dump())
        if not success:
            raise HTTPException(status_code=500, detail="更新助剂失败")

        updated = db.get_adjuvant(adjuvant_id)
        if not updated:
            raise HTTPException(status_code=500, detail="更新助剂后未能读取详情")
        return AdjuvantListItem(**updated)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"更新助剂失败: {exc}") from exc


@router.delete("/adjuvants/{adjuvant_id}", response_model=DeleteResponse)
async def delete_adjuvant(
    adjuvant_id: int,
    db: DatabaseManager = Depends(get_database)
):
    """删除助剂"""
    try:
        success = db.delete_adjuvant(adjuvant_id)
        if not success:
            raise HTTPException(status_code=404, detail="助剂不存在")
        return DeleteResponse(success=True, message="助剂删除成功")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除助剂失败: {exc}") from exc
