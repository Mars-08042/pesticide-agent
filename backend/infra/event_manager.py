"""
全局事件管理器
用于在后端组件之间以及向前端推送事件

支持的事件类型:
- kb_status_changed: 知识库状态变化（indexing -> active/error）
- step: Agent 执行步骤事件（用于实时推送子图步骤）
"""

import asyncio
import json
from typing import Dict, Any, Set, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """事件数据"""
    type: str
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class EventManager:
    """
    全局事件管理器

    使用 asyncio.Queue 实现事件分发
    支持多个订阅者同时监听
    支持会话级别的步骤事件队列（用于子图实时推送）
    """

    def __init__(self):
        # 订阅者队列集合
        self._subscribers: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        # 会话级别的步骤事件队列
        self._session_step_queues: Dict[str, asyncio.Queue] = {}
        self._session_lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        """
        订阅事件

        Returns:
            事件队列，调用者需要从中读取事件
        """
        queue = asyncio.Queue()
        async with self._lock:
            self._subscribers.add(queue)
        logger.debug(f"新订阅者加入，当前订阅者数: {len(self._subscribers)}")
        return queue

    async def unsubscribe(self, queue: asyncio.Queue):
        """
        取消订阅

        Args:
            queue: 要移除的事件队列
        """
        async with self._lock:
            self._subscribers.discard(queue)
        logger.debug(f"订阅者离开，当前订阅者数: {len(self._subscribers)}")

    async def publish(self, event_type: str, data: Dict[str, Any]):
        """
        发布事件

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        event = Event(type=event_type, data=data)

        async with self._lock:
            subscribers = list(self._subscribers)

        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("事件队列已满，丢弃事件")

        logger.info(f"发布事件: {event_type}, 订阅者数: {len(subscribers)}")

    # ============ 会话级别步骤事件队列 ============

    async def create_session_step_queue(self, session_id: str) -> asyncio.Queue:
        """
        创建会话级别的步骤事件队列

        Args:
            session_id: 会话 ID

        Returns:
            事件队列
        """
        async with self._session_lock:
            if session_id in self._session_step_queues:
                # 清空旧队列
                old_queue = self._session_step_queues[session_id]
                while not old_queue.empty():
                    try:
                        old_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
            queue = asyncio.Queue()
            self._session_step_queues[session_id] = queue
            logger.debug(f"创建会话步骤队列: {session_id}")
            return queue

    async def get_session_step_queue(self, session_id: str) -> Optional[asyncio.Queue]:
        """
        获取会话级别的步骤事件队列

        Args:
            session_id: 会话 ID

        Returns:
            事件队列，如果不存在则返回 None
        """
        async with self._session_lock:
            return self._session_step_queues.get(session_id)

    async def remove_session_step_queue(self, session_id: str):
        """
        移除会话级别的步骤事件队列

        Args:
            session_id: 会话 ID
        """
        async with self._session_lock:
            if session_id in self._session_step_queues:
                del self._session_step_queues[session_id]
                logger.debug(f"移除会话步骤队列: {session_id}")

    async def push_session_step(self, session_id: str, step: Dict[str, Any]):
        """
        推送步骤事件到会话队列

        Args:
            session_id: 会话 ID
            step: 步骤数据
        """
        async with self._session_lock:
            queue = self._session_step_queues.get(session_id)

        if queue:
            try:
                queue.put_nowait(step)
                logger.debug(f"推送步骤事件到会话 {session_id}: {step.get('type', 'unknown')}")
            except asyncio.QueueFull:
                logger.warning(f"会话 {session_id} 步骤队列已满，丢弃事件")
        else:
            logger.debug(f"会话 {session_id} 没有活跃的步骤队列")

    def push_session_step_sync(self, session_id: str, step: Dict[str, Any]):
        """
        同步推送步骤事件（用于非异步上下文）

        Args:
            session_id: 会话 ID
            step: 步骤数据
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.push_session_step(session_id, step))
        except RuntimeError:
            # 没有运行中的事件循环
            pass

    def publish_sync(self, event_type: str, data: Dict[str, Any]):
        """
        同步发布事件（用于非异步上下文）

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish(event_type, data))
        except RuntimeError:
            # 没有运行中的事件循环，创建新的
            asyncio.run(self.publish(event_type, data))


# 全局事件管理器实例
_event_manager: Optional[EventManager] = None


def get_event_manager() -> EventManager:
    """获取全局事件管理器实例"""
    global _event_manager
    if _event_manager is None:
        _event_manager = EventManager()
    return _event_manager


# 便捷函数
async def publish_event(event_type: str, data: Dict[str, Any]):
    """发布事件的便捷函数"""
    await get_event_manager().publish(event_type, data)


def publish_event_sync(event_type: str, data: Dict[str, Any]):
    """同步发布事件的便捷函数"""
    get_event_manager().publish_sync(event_type, data)
