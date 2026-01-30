"""
任务状态管理器
管理正在进行的生成任务和上传任务状态

解决问题：
- P0-1: 全局任务状态在多 worker 场景失效
- P0-2: 并发请求竞态条件

设计：
- 抽象接口支持内存和 Redis 两种后端
- 内存模式用于单 worker 部署（默认）
- Redis 模式用于多 worker 部署（可选）
- 提供原子操作防止竞态条件
- 支持任务超时自动清理
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

from .config import get_config

logger = logging.getLogger(__name__)


class AcquireResult(Enum):
    """任务获取结果"""
    SUCCESS = "success"
    SESSION_BUSY = "session_busy"      # 同会话已有活跃任务
    SYSTEM_BUSY = "system_busy"        # 系统繁忙，超过最大并发


@dataclass
class AcquireTaskResponse:
    """acquire_task 返回值"""
    result: AcquireResult
    task_id: Optional[str] = None


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    session_id: str
    status: str  # pending, processing, completed, failed, cancelled
    cancel_requested: bool = False
    progress: int = 0
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    task_ref: Optional[asyncio.Task] = None  # 仅内存模式使用


class TaskManagerBase(ABC):
    """任务管理器抽象基类"""

    @abstractmethod
    async def acquire_task(self, session_id: str, task_id: Optional[str] = None) -> AcquireTaskResponse:
        """
        尝试获取任务锁

        如果该 session 已有活跃任务，返回 SESSION_BUSY
        如果系统繁忙（超过最大并发），返回 SYSTEM_BUSY
        否则创建任务并返回 SUCCESS 和 task_id

        Args:
            session_id: 会话 ID
            task_id: 可选的任务 ID，不提供则自动生成

        Returns:
            AcquireTaskResponse，包含结果状态和可选的 task_id
        """
        pass

    @abstractmethod
    async def release_task(self, session_id: str) -> bool:
        """
        释放任务锁

        Args:
            session_id: 会话 ID

        Returns:
            是否成功释放
        """
        pass

    @abstractmethod
    async def set_cancel_flag(self, session_id: str) -> bool:
        """
        设置取消标志

        Args:
            session_id: 会话 ID

        Returns:
            是否成功设置（任务存在时才成功）
        """
        pass

    @abstractmethod
    async def check_cancel_flag(self, session_id: str) -> bool:
        """
        检查取消标志

        Args:
            session_id: 会话 ID

        Returns:
            是否已请求取消
        """
        pass

    @abstractmethod
    async def is_task_active(self, session_id: str) -> bool:
        """
        检查是否有活跃任务

        Args:
            session_id: 会话 ID

        Returns:
            是否有活跃任务
        """
        pass

    @abstractmethod
    async def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        """
        获取任务信息

        Args:
            task_id: 任务 ID

        Returns:
            任务信息，不存在则返回 None
        """
        pass

    @abstractmethod
    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: int = 0,
        message: str = "",
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        更新任务状态

        Args:
            task_id: 任务 ID
            status: 新状态
            progress: 进度 (0-100)
            message: 状态消息
            result: 结果数据
            error: 错误信息

        Returns:
            是否更新成功
        """
        pass

    @abstractmethod
    async def register_asyncio_task(self, session_id: str, task: asyncio.Task) -> bool:
        """
        注册 asyncio.Task 引用（用于取消）

        Args:
            session_id: 会话 ID
            task: asyncio.Task 实例

        Returns:
            是否注册成功
        """
        pass

    @abstractmethod
    async def get_asyncio_task(self, session_id: str) -> Optional[asyncio.Task]:
        """
        获取 asyncio.Task 引用

        Args:
            session_id: 会话 ID

        Returns:
            asyncio.Task 实例，不存在则返回 None
        """
        pass

    @abstractmethod
    async def cleanup_expired_tasks(self, timeout_seconds: int = 300) -> int:
        """
        清理超时的任务

        Args:
            timeout_seconds: 超时时间（秒），默认 5 分钟

        Returns:
            清理的任务数量
        """
        pass

    @abstractmethod
    async def clear_all_tasks(self) -> int:
        """
        清理所有任务（用于应用启动时重置状态）

        Returns:
            清理的任务数量
        """
        pass

    @abstractmethod
    async def get_active_tasks_info(self) -> List[Dict[str, Any]]:
        """
        获取所有活跃任务的信息

        Returns:
            活跃任务信息列表
        """
        pass


class InMemoryTaskManager(TaskManagerBase):
    """
    内存任务管理器

    适用于单 worker 部署。使用 asyncio.Lock 保证原子操作。

    注意：多 worker 部署时此实现无效，请使用 Redis 后端。
    """

    def __init__(self, max_concurrent: int = 3):
        # session_id -> TaskInfo
        self._tasks: Dict[str, TaskInfo] = {}
        # task_id -> session_id (反向索引)
        self._task_to_session: Dict[str, str] = {}
        # 锁，保证原子操作
        self._lock = asyncio.Lock()
        # 最大并发数
        self._max_concurrent = max_concurrent

    async def acquire_task(self, session_id: str, task_id: Optional[str] = None) -> AcquireTaskResponse:
        async with self._lock:
            # 1. 检查同会话冲突
            if session_id in self._tasks:
                existing = self._tasks[session_id]
                if existing.status in ("pending", "processing"):
                    logger.warning(f"会话 {session_id} 已有活跃任务，拒绝并发请求")
                    return AcquireTaskResponse(result=AcquireResult.SESSION_BUSY)

            # 2. 检查全局并发限制
            active_count = sum(
                1 for t in self._tasks.values()
                if t.status in ("pending", "processing")
            )
            if active_count >= self._max_concurrent:
                logger.warning(f"系统繁忙，活跃任务数 {active_count} >= {self._max_concurrent}")
                return AcquireTaskResponse(result=AcquireResult.SYSTEM_BUSY)

            # 3. 生成任务 ID
            if task_id is None:
                import uuid
                task_id = str(uuid.uuid4())

            # 4. 创建任务
            task_info = TaskInfo(
                task_id=task_id,
                session_id=session_id,
                status="processing"
            )
            self._tasks[session_id] = task_info
            self._task_to_session[task_id] = session_id

            logger.info(f"创建任务 {task_id} (session: {session_id})")
            return AcquireTaskResponse(result=AcquireResult.SUCCESS, task_id=task_id)

    async def release_task(self, session_id: str) -> bool:
        async with self._lock:
            if session_id not in self._tasks:
                return False

            task_info = self._tasks[session_id]
            del self._tasks[session_id]
            if task_info.task_id in self._task_to_session:
                del self._task_to_session[task_info.task_id]

            logger.info(f"释放任务 {task_info.task_id} (session: {session_id})")
            return True

    async def set_cancel_flag(self, session_id: str) -> bool:
        async with self._lock:
            if session_id not in self._tasks:
                return False

            self._tasks[session_id].cancel_requested = True
            logger.info(f"设置取消标志 (session: {session_id})")
            return True

    async def check_cancel_flag(self, session_id: str) -> bool:
        # 读取操作可以不加锁
        task_info = self._tasks.get(session_id)
        if task_info is None:
            return False
        return task_info.cancel_requested

    async def is_task_active(self, session_id: str) -> bool:
        task_info = self._tasks.get(session_id)
        if task_info is None:
            return False
        return task_info.status in ("pending", "processing")

    async def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        session_id = self._task_to_session.get(task_id)
        if session_id is None:
            return None
        return self._tasks.get(session_id)

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: int = 0,
        message: str = "",
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        session_id = self._task_to_session.get(task_id)
        if session_id is None:
            return False

        task_info = self._tasks.get(session_id)
        if task_info is None:
            return False

        task_info.status = status
        task_info.progress = progress
        task_info.message = message
        if result is not None:
            task_info.result = result
        if error is not None:
            task_info.error = error

        return True

    async def register_asyncio_task(self, session_id: str, task: asyncio.Task) -> bool:
        if session_id not in self._tasks:
            return False
        self._tasks[session_id].task_ref = task
        return True

    async def get_asyncio_task(self, session_id: str) -> Optional[asyncio.Task]:
        task_info = self._tasks.get(session_id)
        if task_info is None:
            return None
        return task_info.task_ref

    async def cleanup_expired_tasks(self, timeout_seconds: int = 300) -> int:
        """清理超时的任务"""
        async with self._lock:
            now = datetime.now()
            expired_sessions = []

            for session_id, task_info in self._tasks.items():
                if task_info.status in ("pending", "processing"):
                    age = (now - task_info.created_at).total_seconds()
                    if age > timeout_seconds:
                        expired_sessions.append(session_id)
                        logger.warning(f"任务超时，准备清理: session={session_id}, age={age:.1f}s")

            # 清理过期任务
            for session_id in expired_sessions:
                task_info = self._tasks.pop(session_id, None)
                if task_info and task_info.task_id in self._task_to_session:
                    del self._task_to_session[task_info.task_id]

            if expired_sessions:
                logger.info(f"清理了 {len(expired_sessions)} 个超时任务")

            return len(expired_sessions)

    async def clear_all_tasks(self) -> int:
        """清理所有任务"""
        async with self._lock:
            count = len(self._tasks)
            self._tasks.clear()
            self._task_to_session.clear()
            logger.info(f"清理了所有任务，共 {count} 个")
            return count

    async def get_active_tasks_info(self) -> List[Dict[str, Any]]:
        """获取所有活跃任务的信息"""
        result = []
        now = datetime.now()
        for session_id, task_info in self._tasks.items():
            if task_info.status in ("pending", "processing"):
                result.append({
                    "session_id": session_id,
                    "task_id": task_info.task_id,
                    "status": task_info.status,
                    "created_at": task_info.created_at.isoformat(),
                    "age_seconds": (now - task_info.created_at).total_seconds()
                })
        return result


class RedisTaskManager(TaskManagerBase):
    """
    Redis 任务管理器

    适用于多 worker 部署。使用 Redis 原子操作保证一致性。

    注意：需要安装 redis 包：pip install redis
    """

    def __init__(self, redis_url: str, expire_seconds: int = 3600, max_concurrent: int = 3):
        self._redis_url = redis_url
        self._expire_seconds = expire_seconds
        self._max_concurrent = max_concurrent
        self._redis = None
        self._local_tasks: Dict[str, asyncio.Task] = {}  # 本地 asyncio.Task 引用

    async def _get_redis(self):
        """懒加载 Redis 连接"""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(self._redis_url)
            except ImportError:
                raise ImportError("Redis 后端需要安装 redis 包：pip install redis")
        return self._redis

    def _task_key(self, session_id: str) -> str:
        return f"task:session:{session_id}"

    def _cancel_key(self, session_id: str) -> str:
        return f"task:cancel:{session_id}"

    def _info_key(self, task_id: str) -> str:
        return f"task:info:{task_id}"

    async def acquire_task(self, session_id: str, task_id: Optional[str] = None) -> AcquireTaskResponse:
        redis = await self._get_redis()

        if task_id is None:
            import uuid
            task_id = str(uuid.uuid4())

        # 1. 使用 SETNX 检查同会话冲突
        key = self._task_key(session_id)
        acquired = await redis.set(key, task_id, nx=True, ex=self._expire_seconds)

        if not acquired:
            logger.warning(f"会话 {session_id} 已有活跃任务，拒绝并发请求")
            return AcquireTaskResponse(result=AcquireResult.SESSION_BUSY)

        # 2. 检查全局并发限制
        counter_key = "task:global:counter"
        current_count = await redis.incr(counter_key)

        if current_count > self._max_concurrent:
            # 回滚：删除已获取的锁，减少计数
            await redis.delete(key)
            await redis.decr(counter_key)
            logger.warning(f"系统繁忙，活跃任务数 {current_count} > {self._max_concurrent}")
            return AcquireTaskResponse(result=AcquireResult.SYSTEM_BUSY)

        # 3. 存储任务信息
        import json
        info = {
            "task_id": task_id,
            "session_id": session_id,
            "status": "processing",
            "progress": 0,
            "message": "",
            "created_at": datetime.now().isoformat()
        }
        await redis.set(self._info_key(task_id), json.dumps(info), ex=self._expire_seconds)

        logger.info(f"创建任务 {task_id} (session: {session_id})")
        return AcquireTaskResponse(result=AcquireResult.SUCCESS, task_id=task_id)

    async def release_task(self, session_id: str) -> bool:
        redis = await self._get_redis()

        key = self._task_key(session_id)
        task_id = await redis.get(key)

        if task_id is None:
            return False

        # 删除相关键
        await redis.delete(key)
        await redis.delete(self._cancel_key(session_id))
        await redis.delete(self._info_key(task_id.decode() if isinstance(task_id, bytes) else task_id))

        # 减少全局计数器
        counter_key = "task:global:counter"
        await redis.decr(counter_key)

        # 清理本地 Task 引用
        self._local_tasks.pop(session_id, None)

        logger.info(f"释放任务 (session: {session_id})")
        return True

    async def set_cancel_flag(self, session_id: str) -> bool:
        redis = await self._get_redis()

        # 检查任务是否存在
        if not await redis.exists(self._task_key(session_id)):
            return False

        await redis.set(self._cancel_key(session_id), "1", ex=self._expire_seconds)
        logger.info(f"设置取消标志 (session: {session_id})")
        return True

    async def check_cancel_flag(self, session_id: str) -> bool:
        redis = await self._get_redis()
        result = await redis.get(self._cancel_key(session_id))
        return result == b"1"

    async def is_task_active(self, session_id: str) -> bool:
        redis = await self._get_redis()
        return await redis.exists(self._task_key(session_id))

    async def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        redis = await self._get_redis()
        import json

        data = await redis.get(self._info_key(task_id))
        if data is None:
            return None

        info = json.loads(data)
        return TaskInfo(
            task_id=info["task_id"],
            session_id=info["session_id"],
            status=info["status"],
            progress=info.get("progress", 0),
            message=info.get("message", ""),
            result=info.get("result"),
            error=info.get("error"),
            created_at=datetime.fromisoformat(info["created_at"])
        )

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: int = 0,
        message: str = "",
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        redis = await self._get_redis()
        import json

        key = self._info_key(task_id)
        data = await redis.get(key)
        if data is None:
            return False

        info = json.loads(data)
        info["status"] = status
        info["progress"] = progress
        info["message"] = message
        if result is not None:
            info["result"] = result
        if error is not None:
            info["error"] = error

        await redis.set(key, json.dumps(info), ex=self._expire_seconds)
        return True

    async def register_asyncio_task(self, session_id: str, task: asyncio.Task) -> bool:
        # asyncio.Task 无法序列化，只能存储在本地
        # 这意味着跨 worker 的取消功能仍然有限制
        self._local_tasks[session_id] = task
        return True

    async def get_asyncio_task(self, session_id: str) -> Optional[asyncio.Task]:
        return self._local_tasks.get(session_id)

    async def cleanup_expired_tasks(self, timeout_seconds: int = 300) -> int:
        """清理超时的任务（Redis 有自动过期，这里主要处理计数器）"""
        # Redis 的 key 有过期时间，不需要手动清理
        # 但需要确保计数器正确
        redis = await self._get_redis()
        counter_key = "task:global:counter"

        # 获取当前计数
        count_str = await redis.get(counter_key)
        if count_str:
            count = int(count_str)
            if count < 0:
                # 修正负数计数
                await redis.set(counter_key, 0)
                logger.warning(f"修正负数计数器: {count} -> 0")

        return 0

    async def clear_all_tasks(self) -> int:
        """清理所有任务"""
        redis = await self._get_redis()

        # 清理全局计数器
        counter_key = "task:global:counter"
        await redis.set(counter_key, 0)

        # 清理本地任务引用
        count = len(self._local_tasks)
        self._local_tasks.clear()

        logger.info(f"重置 Redis 任务管理器，清理了 {count} 个本地任务引用")
        return count

    async def get_active_tasks_info(self) -> List[Dict[str, Any]]:
        """获取所有活跃任务的信息（仅本地引用）"""
        result = []
        for session_id, task in self._local_tasks.items():
            result.append({
                "session_id": session_id,
                "task_done": task.done() if task else True,
            })
        return result


# 全局任务管理器实例
_task_manager: Optional[TaskManagerBase] = None


def get_task_manager() -> TaskManagerBase:
    """
    获取任务管理器实例

    根据配置自动选择内存或 Redis 后端
    """
    global _task_manager

    if _task_manager is None:
        config = get_config()
        tm_config = config.task_manager

        if tm_config.backend == "redis":
            logger.info("使用 Redis 任务管理器")
            _task_manager = RedisTaskManager(
                redis_url=tm_config.redis_url,
                expire_seconds=tm_config.task_expire_seconds,
                max_concurrent=tm_config.max_concurrent_tasks
            )
        else:
            logger.info("使用内存任务管理器（仅支持单 worker）")
            _task_manager = InMemoryTaskManager(
                max_concurrent=tm_config.max_concurrent_tasks
            )

    return _task_manager


def reset_task_manager():
    """重置任务管理器（主要用于测试）"""
    global _task_manager
    _task_manager = None
