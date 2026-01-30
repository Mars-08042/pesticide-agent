"""
依赖注入模块
管理数据库连接、Agent 实例等共享资源

修改：
- P1-6: 移除自动创建逻辑，未初始化时抛出明确异常
- P1-5: 在启动时检查 checkpointer 可用性
"""

from typing import Optional

from infra.database import DatabaseManager, get_db_manager, HAS_ASYNC_CHECKPOINTER
from infra.logging_config import setup_logging, restore_logging, get_logger
from infra.task_manager import get_task_manager
from agent.graph import PesticideAgent, get_pesticide_agent

logger = get_logger(__name__)


# 全局资源实例
_db_manager: Optional[DatabaseManager] = None
_agent: Optional[PesticideAgent] = None
_checkpointer_available: bool = False  # checkpointer 可用性标志


async def init_resources():
    """初始化共享资源"""
    global _db_manager, _agent, _checkpointer_available

    # 初始化日志
    setup_logging()
    logger.info("正在初始化资源...")

    # 清理残留任务（解决刷新页面后任务锁未释放的问题）
    task_manager = get_task_manager()
    cleared_count = await task_manager.clear_all_tasks()
    if cleared_count > 0:
        logger.info(f"启动时清理了 {cleared_count} 个残留任务")

    # 初始化数据库管理器
    _db_manager = get_db_manager()
    try:
        _db_manager.init_database()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.warning(f"数据库初始化警告: {e}")

    # 检查 checkpointer 可用性 (P1-5)
    _checkpointer_available = await _check_checkpointer_availability(_db_manager)

    # 初始化 Agent
    _agent = get_pesticide_agent()
    logger.info("Agent 初始化完成")

    # 恢复可能被第三方库修改的日志设置
    restore_logging()

    logger.info("资源初始化完成")


async def _check_checkpointer_availability(db: DatabaseManager) -> bool:
    """
    检查 checkpointer 是否可用

    在启动时进行检查，避免运行时出现意外错误
    """
    if not HAS_ASYNC_CHECKPOINTER:
        logger.warning(
            "AsyncPostgresSaver 不可用，将使用无状态模式。"
            "如需状态持久化，请安装: pip install langgraph-checkpoint-postgres psycopg[pool]"
        )
        return False

    try:
        # 先初始化 checkpointer 表（使用 autocommit 模式避免事务问题）
        await db.setup_checkpointer_tables()

        # 测试 checkpointer 连接
        async with db.get_checkpointer() as cp:
            pass
        logger.info("Checkpointer 可用")
        return True
    except Exception as e:
        logger.warning(f"Checkpointer 不可用，将使用无状态模式: {e}")
        return False


async def cleanup_resources():
    """清理共享资源"""
    global _db_manager, _agent, _checkpointer_available
    logger.info("正在清理资源...")
    _db_manager = None
    _agent = None
    _checkpointer_available = False


def get_database() -> DatabaseManager:
    """
    获取数据库管理器实例（依赖注入）

    修改 P1-6: 移除自动创建逻辑，未初始化时抛出明确异常
    """
    if _db_manager is None:
        raise RuntimeError(
            "数据库未初始化，请确保 init_resources() 已被调用。"
            "这通常意味着应用启动流程存在问题。"
        )
    return _db_manager


def get_agent() -> PesticideAgent:
    """
    获取 Agent 实例（依赖注入）

    修改 P1-6: 移除自动创建逻辑，未初始化时抛出明确异常
    """
    if _agent is None:
        raise RuntimeError(
            "Agent 未初始化，请确保 init_resources() 已被调用。"
            "这通常意味着应用启动流程存在问题。"
        )
    return _agent


def is_checkpointer_available() -> bool:
    """
    检查 checkpointer 是否可用

    供其他模块查询，决定是否使用状态持久化功能
    """
    return _checkpointer_available
