"""
会话管理路由
处理会话的创建、列表、删除等操作
"""

import uuid
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_database
from infra.database import DatabaseManager


router = APIRouter()


# ============ 请求/响应模型 ============

class SessionCreate(BaseModel):
    """创建会话请求"""
    session_id: Optional[str] = Field(None, description="可选的会话 ID，不提供则自动生成")
    title: Optional[str] = Field(None, description="会话标题")
    metadata: Optional[dict] = Field(default_factory=dict, description="会话元数据")


class SessionUpdate(BaseModel):
    """更新会话请求"""
    title: Optional[str] = Field(None, description="会话标题")
    metadata: Optional[dict] = Field(None, description="会话元数据")


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    metadata: Optional[dict] = None


class SessionListResponse(BaseModel):
    """会话列表响应"""
    sessions: list[SessionInfo]
    total: int


class SessionCreateResponse(BaseModel):
    """创建会话响应"""
    session_id: str
    message: str


class DeleteResponse(BaseModel):
    """删除响应"""
    success: bool
    message: str


# ============ 路由处理 ============

@router.get("/list", response_model=SessionListResponse)
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    db: DatabaseManager = Depends(get_database)
):
    """
    获取会话列表

    返回按更新时间倒序排列的会话列表，每个会话包含标题（第一条用户消息的摘要）
    """
    sessions = db.list_sessions(limit=limit, offset=offset)

    session_list = [
        SessionInfo(
            session_id=s["session_id"],
            title=s.get("title", "新对话"),
            created_at=s["created_at"],
            updated_at=s["updated_at"],
            metadata=s.get("metadata"),
        )
        for s in sessions
    ]

    return SessionListResponse(
        sessions=session_list,
        total=len(session_list)
    )


@router.get("/search", response_model=SessionListResponse)
async def search_sessions(
    keyword: str = Query(..., min_length=1, description="搜索关键字"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: DatabaseManager = Depends(get_database)
):
    """
    按会话名称模糊搜索会话

    支持搜索会话标题和第一条用户消息内容
    """
    sessions = db.search_sessions(keyword=keyword, limit=limit, offset=offset)

    session_list = [
        SessionInfo(
            session_id=s["session_id"],
            title=s.get("title", "新对话"),
            created_at=s["created_at"],
            updated_at=s["updated_at"],
            metadata=s.get("metadata"),
        )
        for s in sessions
    ]

    return SessionListResponse(
        sessions=session_list,
        total=len(session_list)
    )


@router.post("/create", response_model=SessionCreateResponse)
async def create_session(
    request: SessionCreate = None,
    db: DatabaseManager = Depends(get_database)
):
    """
    创建新会话

    如果不提供 session_id，将自动生成 UUID
    """
    if request is None:
        request = SessionCreate()

    session_id = request.session_id or str(uuid.uuid4())

    try:
        session = db.create_session(
            session_id=session_id,
            title=request.title,
            metadata=request.metadata
        )
        return SessionCreateResponse(
            session_id=session["session_id"],
            message="会话创建成功"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session(
    session_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """
    获取单个会话信息
    """
    try:
        session = db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        return SessionInfo(
            session_id=session["session_id"],
            title=session.get("title") or "新对话",
            created_at=session["created_at"],
            updated_at=session["updated_at"],
            metadata=session.get("metadata"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话失败: {str(e)}")


@router.put("/{session_id}", response_model=SessionInfo)
async def update_session(
    session_id: str,
    request: SessionUpdate,
    db: DatabaseManager = Depends(get_database)
):
    """
    修改会话信息

    可以修改会话标题和元数据
    """
    try:
        # 检查会话是否存在
        session = db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 更新会话
        success = db.update_session(
            session_id=session_id,
            title=request.title,
            metadata=request.metadata
        )

        if not success:
            raise HTTPException(status_code=500, detail="更新会话失败")

        # 获取更新后的会话
        updated_session = db.get_session(session_id)
        return SessionInfo(
            session_id=updated_session["session_id"],
            title=updated_session.get("title") or "新对话",
            created_at=updated_session["created_at"],
            updated_at=updated_session["updated_at"],
            metadata=updated_session.get("metadata"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新会话失败: {str(e)}")


@router.delete("/{session_id}", response_model=DeleteResponse)
async def delete_session(
    session_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """
    删除会话及其所有聊天历史
    """
    try:
        success = db.delete_session(session_id)
        if success:
            return DeleteResponse(success=True, message="会话删除成功")
        else:
            return DeleteResponse(success=False, message="会话不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")
