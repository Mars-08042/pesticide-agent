"""
对话路由
处理聊天消息的发送、流式响应、历史记录查询
支持异步执行和状态持久化，实现中断恢复和重新生成

重构后支持两种配方模式：
- generation: 配方生成
- optimization: 配方优化
"""

import asyncio
import logging
from typing import Optional, List, Literal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from langchain_core.messages import HumanMessage

from api.dependencies import get_database, get_agent, is_checkpointer_available
from api.streaming import SSEEventBuilder, StateUpdateProcessor
from api.persistence import save_user_message, save_assistant_message
from api.execution import (
    execute_with_checkpointer_and_queue,
    execute_without_checkpointer_and_queue,
    stream_answer,
)
from infra.database import DatabaseManager
from infra.task_manager import get_task_manager, AcquireResult
from infra.config import get_config
from infra.event_manager import get_event_manager
from agent.graph import PesticideAgent, AgentState


logger = logging.getLogger(__name__)

router = APIRouter()


# ============ 请求/响应模型 ============

# 优化目标类型
OptimizationTarget = Literal["cost", "performance", "stability", "substitution"]


class ChatRequest(BaseModel):
    """聊天请求 - 配方专用版"""
    session_id: str = Field(..., description="会话 ID")
    query: str = Field(..., description="用户问题", min_length=1)
    kb_ids: Optional[List[str]] = Field(
        default=None,
        description="知识库文档 ID 列表，用于限定检索范围。为空则使用全部活动文档"
    )
    route_mode: Literal["auto", "generation", "optimization"] = Field(
        default="auto",
        description="路由模式：auto=自动判断，generation=配方生成，optimization=配方优化"
    )
    original_recipe: Optional[str] = Field(
        default=None,
        description="原始配方文本（优化模式必填）"
    )
    optimization_targets: Optional[List[OptimizationTarget]] = Field(
        default=None,
        description="优化目标列表（优化模式使用）"
    )

    @model_validator(mode='after')
    def validate_optimization_mode(self):
        """验证优化模式的必填字段"""
        if self.route_mode == 'optimization':
            if not self.original_recipe or not self.original_recipe.strip():
                raise ValueError('优化模式需要提供原始配方')
            if not self.optimization_targets or len(self.optimization_targets) == 0:
                raise ValueError('优化模式需要至少指定一个优化目标')
        return self


class StopRequest(BaseModel):
    """停止生成请求"""
    session_id: str = Field(..., description="会话 ID")


class StopResponse(BaseModel):
    """停止生成响应"""
    success: bool
    message: str


class RegenerateRequest(BaseModel):
    """重新生成请求"""
    session_id: str = Field(..., description="会话 ID")
    message_id: Optional[int] = Field(None, description="要重新生成的消息 ID (可选，默认为最后一条)")


class ChatMessage(BaseModel):
    """聊天消息"""
    id: int
    role: str
    content: str
    message_type: str = "text"
    thinking: Optional[str] = None
    steps: Optional[list] = None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    """聊天历史响应"""
    messages: list[ChatMessage]
    has_more: bool


class DeleteHistoryResponse(BaseModel):
    """删除历史响应"""
    success: bool
    deleted_count: int
    message: str


class TasksInfoResponse(BaseModel):
    """活跃任务信息响应"""
    active_count: int
    max_concurrent: int
    tasks: list


class ClearTasksResponse(BaseModel):
    """清理任务响应"""
    success: bool
    cleared_count: int
    message: str


# ============ SSE 事件生成器 ============

async def generate_sse_events(
    session_id: str,
    query: str,
    agent: PesticideAgent,
    db: DatabaseManager,
    kb_ids: Optional[List[str]] = None,
    use_checkpointer: bool = True,
    skip_user_message: bool = False,
    route_mode: str = "generation",
    original_recipe: Optional[str] = None,
    optimization_targets: Optional[List[str]] = None
):
    """
    生成 SSE 事件流

    Args:
        session_id: 会话 ID
        query: 用户问题
        agent: Agent 实例
        db: 数据库管理器
        kb_ids: 知识库文档 ID 列表
        use_checkpointer: 是否使用 checkpointer
        skip_user_message: 是否跳过保存用户消息（重新生成时使用）
        route_mode: 路由模式（generation/optimization）
        original_recipe: 原始配方文本（优化模式使用）
        optimization_targets: 优化目标列表（优化模式使用）

    Yields:
        SSE 格式的事件字符串
    """
    task_manager = get_task_manager()
    event_manager = get_event_manager()
    processor = StateUpdateProcessor()
    cancelled = False

    # 创建会话步骤队列
    step_queue = await event_manager.create_session_step_queue(session_id)

    try:
        # 保存用户消息
        if not skip_user_message:
            save_user_message(db, session_id, query)

        # 构建初始状态
        initial_state: AgentState = {
            "messages": [HumanMessage(content=query)],
            "intent": "",
            "entities": {},
            "steps": [],
            "kb_ids": kb_ids,
            "session_id": session_id,
            "route_mode": route_mode,
            "original_recipe": original_recipe,
            "optimization_targets": optimization_targets or [],
        }

        config = {"configurable": {"thread_id": session_id}}

        # 执行图
        if use_checkpointer and is_checkpointer_available():
            async for event in execute_with_checkpointer_and_queue(
                agent, db, initial_state, config, processor, session_id, task_manager, step_queue
            ):
                if event == "__cancelled__":
                    cancelled = True
                    break
                yield event
        else:
            async for event in execute_without_checkpointer_and_queue(
                agent, initial_state, config, processor, session_id, task_manager, step_queue
            ):
                if event == "__cancelled__":
                    cancelled = True
                    break
                yield event

        # 发送答案（打字机效果）
        if processor.final_answer and not cancelled:
            async for event in stream_answer(processor.final_answer, session_id, task_manager):
                if event == "__cancelled__":
                    cancelled = True
                    break
                yield event

        # 发送完成或取消事件
        if cancelled:
            yield SSEEventBuilder.cancelled_event()
        else:
            yield SSEEventBuilder.done_event(processor.final_answer)

            # 保存助手回复
            save_assistant_message(
                db, session_id, processor.final_answer,
                thinking=processor.get_thinking_content(),
                steps=processor.all_steps
            )

    except asyncio.CancelledError:
        yield SSEEventBuilder.cancelled_event("请求已取消")
        raise

    except Exception as e:
        yield SSEEventBuilder.error_event(str(e), type(e).__name__)

    finally:
        await event_manager.remove_session_step_queue(session_id)


# ============ 路由处理 ============

@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    agent: PesticideAgent = Depends(get_agent),
    db: DatabaseManager = Depends(get_database)
):
    """
    流式对话接口

    使用 Server-Sent Events (SSE) 实时推送 Agent 的思考过程、工具调用和最终回答。

    SSE 事件类型:
    - router: 意图路由
    - thought: 思考过程
    - tool_req: 工具调用请求
    - tool_res: 工具返回结果
    - decision: 决策判断
    - answer: 最终回答
    - error: 错误信息
    - done: 完成标记
    - cancelled: 请求被取消
    """
    task_manager = get_task_manager()

    # 尝试获取任务锁
    acquire_response = await task_manager.acquire_task(request.session_id)

    if acquire_response.result == AcquireResult.SESSION_BUSY:
        raise HTTPException(
            status_code=409,
            detail="该会话有正在进行的请求，请等待完成或取消后重试"
        )
    elif acquire_response.result == AcquireResult.SYSTEM_BUSY:
        raise HTTPException(
            status_code=503,
            detail="系统繁忙，请稍后重试"
        )

    async def stream_generator():
        try:
            current_task = asyncio.current_task()
            await task_manager.register_asyncio_task(request.session_id, current_task)

            async for event in generate_sse_events(
                session_id=request.session_id,
                query=request.query,
                agent=agent,
                db=db,
                kb_ids=request.kb_ids,
                route_mode=request.route_mode,
                original_recipe=request.original_recipe,
                optimization_targets=request.optimization_targets
            ):
                yield event
        finally:
            await task_manager.release_task(request.session_id)

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/stop", response_model=StopResponse)
async def stop_generation(request: StopRequest):
    """停止生成"""
    task_manager = get_task_manager()
    session_id = request.session_id

    if not await task_manager.is_task_active(session_id):
        return StopResponse(success=False, message="没有正在进行的生成任务")

    await task_manager.set_cancel_flag(session_id)

    task = await task_manager.get_asyncio_task(session_id)
    if task and not task.done():
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    return StopResponse(success=True, message="已停止生成")


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str = Query(..., description="会话 ID"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    before_id: Optional[int] = Query(None, description="在此 ID 之前的消息（用于分页）"),
    db: DatabaseManager = Depends(get_database)
):
    """获取聊天历史（分页）"""
    messages, has_more = db.get_chat_history(
        session_id=session_id,
        limit=limit,
        before_id=before_id
    )

    chat_messages = [
        ChatMessage(
            id=m["id"],
            role=m["role"],
            content=m["content"],
            message_type=m.get("message_type", "text"),
            thinking=m.get("thinking"),
            steps=m.get("metadata", {}).get("steps"),
            created_at=m["created_at"]
        )
        for m in messages
    ]

    return ChatHistoryResponse(messages=chat_messages, has_more=has_more)


@router.delete("/history", response_model=DeleteHistoryResponse)
async def delete_chat_history(
    session_id: str = Query(..., description="会话 ID"),
    db: DatabaseManager = Depends(get_database)
):
    """清空会话的聊天历史"""
    try:
        deleted_count = db.clear_chat_history(session_id)
        return DeleteHistoryResponse(
            success=True,
            deleted_count=deleted_count,
            message=f"已删除 {deleted_count} 条消息"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空历史失败: {str(e)}")


@router.post("/regenerate")
async def regenerate_response(
    request: RegenerateRequest,
    agent: PesticideAgent = Depends(get_agent),
    db: DatabaseManager = Depends(get_database)
):
    """重新生成回答"""
    task_manager = get_task_manager()

    acquire_response = await task_manager.acquire_task(request.session_id)

    if acquire_response.result == AcquireResult.SESSION_BUSY:
        raise HTTPException(
            status_code=409,
            detail="该会话有正在进行的请求，请等待完成或取消后重试"
        )
    elif acquire_response.result == AcquireResult.SYSTEM_BUSY:
        raise HTTPException(status_code=503, detail="系统繁忙，请稍后重试")

    try:
        user_query, target_message_id = await _find_regenerate_target(
            db, request.session_id, request.message_id
        )

        db.delete_message(target_message_id)

        async def stream_generator():
            try:
                current_task = asyncio.current_task()
                await task_manager.register_asyncio_task(request.session_id, current_task)

                async for event in generate_sse_events(
                    session_id=request.session_id,
                    query=user_query,
                    agent=agent,
                    db=db,
                    use_checkpointer=True,
                    skip_user_message=True
                ):
                    yield event
            finally:
                await task_manager.release_task(request.session_id)

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    except HTTPException:
        await task_manager.release_task(request.session_id)
        raise
    except Exception as e:
        await task_manager.release_task(request.session_id)
        raise HTTPException(status_code=500, detail=f"重新生成失败: {str(e)}")


async def _find_regenerate_target(
    db: DatabaseManager,
    session_id: str,
    message_id: Optional[int]
) -> tuple[str, int]:
    """查找重新生成的目标消息和对应的用户问题"""
    batch_size = 50
    before_id = None
    all_messages = []

    while True:
        messages, has_more = db.get_chat_history(
            session_id=session_id,
            limit=batch_size,
            before_id=before_id
        )

        if not messages:
            break

        all_messages = messages + all_messages
        before_id = messages[0]["id"]

        if message_id:
            found = any(m["id"] == message_id for m in messages)
            if found:
                break

        if not has_more:
            break

    if not all_messages:
        raise HTTPException(status_code=404, detail="未找到聊天历史")

    if message_id:
        target_msg = None
        target_idx = -1
        for idx, msg in enumerate(all_messages):
            if msg["id"] == message_id:
                target_msg = msg
                target_idx = idx
                break

        if not target_msg:
            raise HTTPException(status_code=404, detail="未找到指定消息")

        if target_msg["role"] != "assistant":
            raise HTTPException(status_code=400, detail="只能重新生成助手的回复")
    else:
        target_idx = -1
        for idx in range(len(all_messages) - 1, -1, -1):
            if all_messages[idx]["role"] == "assistant":
                target_idx = idx
                break

        if target_idx == -1:
            raise HTTPException(status_code=404, detail="未找到助手回复")

        message_id = all_messages[target_idx]["id"]

    user_query = None
    for idx in range(target_idx - 1, -1, -1):
        if all_messages[idx]["role"] == "user":
            user_query = all_messages[idx]["content"]
            break

    if not user_query:
        raise HTTPException(status_code=400, detail="未找到对应的用户问题")

    return user_query, message_id


# ============ 任务管理接口 ============

@router.get("/tasks", response_model=TasksInfoResponse)
async def get_active_tasks():
    """获取当前活跃任务信息"""
    task_manager = get_task_manager()
    tasks_info = await task_manager.get_active_tasks_info()
    config = get_config()

    return TasksInfoResponse(
        active_count=len(tasks_info),
        max_concurrent=config.task_manager.max_concurrent_tasks,
        tasks=tasks_info
    )


@router.delete("/tasks", response_model=ClearTasksResponse)
async def clear_all_tasks():
    """清理所有任务"""
    task_manager = get_task_manager()
    cleared_count = await task_manager.clear_all_tasks()

    return ClearTasksResponse(
        success=True,
        cleared_count=cleared_count,
        message=f"已清理 {cleared_count} 个任务"
    )
