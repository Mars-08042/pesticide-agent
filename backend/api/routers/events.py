"""
SSE 事件推送路由
用于向前端推送实时事件（如知识库状态变化）
"""

import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from infra.event_manager import get_event_manager, Event


router = APIRouter()


@router.get("/stream")
async def event_stream():
    """
    SSE 事件流端点

    前端通过 EventSource 连接此端点，接收实时事件推送。
    支持的事件类型:
    - kb_status_changed: 知识库状态变化
    """

    async def generate():
        event_manager = get_event_manager()
        queue = await event_manager.subscribe()

        try:
            # 发送初始连接成功消息
            yield f"event: connected\ndata: {json.dumps({'message': 'SSE connected'})}\n\n"

            while True:
                try:
                    # 等待事件，超时后发送心跳
                    event: Event = await asyncio.wait_for(
                        queue.get(),
                        timeout=30.0
                    )

                    # 发送事件
                    event_data = {
                        "type": event.type,
                        "data": event.data,
                        "timestamp": event.timestamp
                    }
                    yield f"event: {event.type}\ndata: {json.dumps(event_data)}\n\n"

                except asyncio.TimeoutError:
                    # 发送心跳保持连接
                    yield f"event: heartbeat\ndata: {json.dumps({'ping': 'pong'})}\n\n"

        except asyncio.CancelledError:
            pass
        finally:
            await event_manager.unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        }
    )
