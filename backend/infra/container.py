"""
依赖注入容器
集中管理所有共享资源的生命周期，提供统一的依赖获取接口

职责：
- 单例管理：确保全局共享资源只初始化一次
- 延迟初始化：按需创建实例，避免启动时加载所有依赖
- 生命周期管理：提供初始化和清理方法
"""

from typing import Optional, TYPE_CHECKING

# 类型导入（避免循环依赖）
if TYPE_CHECKING:
    from .database import DatabaseManager
    from .llm import LLMClient, EmbeddingClient, RerankClient
    from .event_manager import EventManager
    from .task_manager import TaskManager
    from agent.graph import PesticideAgent


class Container:
    """
    依赖注入容器

    使用示例：
        container = get_container()
        db = container.db_manager
        llm = container.llm_client
    """

    _instance: Optional["Container"] = None

    def __init__(self):
        # 数据库
        self._db_manager: Optional["DatabaseManager"] = None

        # LLM 客户端
        self._llm_client: Optional["LLMClient"] = None
        self._embedding_client: Optional["EmbeddingClient"] = None
        self._rerank_client: Optional["RerankClient"] = None

        # 事件管理器
        self._event_manager: Optional["EventManager"] = None

        # 任务管理器
        self._task_manager: Optional["TaskManager"] = None

        # Agent
        self._agent: Optional["PesticideAgent"] = None

        # Checkpointer 可用性标志
        self._checkpointer_available: bool = False

        # 初始化状态
        self._initialized: bool = False

    @classmethod
    def get_instance(cls) -> "Container":
        """获取容器单例"""
        if cls._instance is None:
            cls._instance = Container()
        return cls._instance

    @classmethod
    def reset(cls):
        """重置容器（主要用于测试）"""
        cls._instance = None

    # ============ 属性访问器 ============

    @property
    def db_manager(self) -> "DatabaseManager":
        """获取数据库管理器"""
        if self._db_manager is None:
            from .database import get_db_manager
            self._db_manager = get_db_manager()
        return self._db_manager

    @property
    def llm_client(self) -> "LLMClient":
        """获取 LLM 客户端"""
        if self._llm_client is None:
            from .llm import get_llm_client
            self._llm_client = get_llm_client()
        return self._llm_client

    @property
    def embedding_client(self) -> "EmbeddingClient":
        """获取 Embedding 客户端"""
        if self._embedding_client is None:
            from .llm import get_embedding_client
            self._embedding_client = get_embedding_client()
        return self._embedding_client

    @property
    def rerank_client(self) -> "RerankClient":
        """获取 Rerank 客户端"""
        if self._rerank_client is None:
            from .llm import get_rerank_client
            self._rerank_client = get_rerank_client()
        return self._rerank_client

    @property
    def event_manager(self) -> "EventManager":
        """获取事件管理器"""
        if self._event_manager is None:
            from .event_manager import get_event_manager
            self._event_manager = get_event_manager()
        return self._event_manager

    @property
    def task_manager(self) -> "TaskManager":
        """获取任务管理器"""
        if self._task_manager is None:
            from .task_manager import get_task_manager
            self._task_manager = get_task_manager()
        return self._task_manager

    @property
    def agent(self) -> "PesticideAgent":
        """获取 Agent 实例"""
        if self._agent is None:
            from agent.graph import get_pesticide_agent
            self._agent = get_pesticide_agent()
        return self._agent

    @property
    def checkpointer_available(self) -> bool:
        """Checkpointer 是否可用"""
        return self._checkpointer_available

    @property
    def initialized(self) -> bool:
        """容器是否已初始化"""
        return self._initialized

    # ============ 生命周期方法 ============

    async def initialize(self):
        """
        初始化容器

        在应用启动时调用，初始化所有必要的资源
        """
        if self._initialized:
            return

        from .logging_config import setup_logging, restore_logging, get_logger

        # 初始化日志
        setup_logging()
        logger = get_logger(__name__)
        logger.info("正在初始化依赖容器...")

        # 清理残留任务
        cleared_count = await self.task_manager.clear_all_tasks()
        if cleared_count > 0:
            logger.info(f"启动时清理了 {cleared_count} 个残留任务")

        # 初始化数据库
        try:
            self.db_manager.init_database()
            logger.info("数据库初始化完成")
        except Exception as e:
            logger.warning(f"数据库初始化警告: {e}")

        # 检查 checkpointer 可用性
        self._checkpointer_available = await self._check_checkpointer_availability(logger)

        # 预热 Agent
        _ = self.agent
        logger.info("Agent 初始化完成")

        # 恢复日志设置
        restore_logging()

        self._initialized = True
        logger.info("依赖容器初始化完成")

    async def _check_checkpointer_availability(self, logger) -> bool:
        """检查 checkpointer 是否可用"""
        from .database import HAS_ASYNC_CHECKPOINTER

        if not HAS_ASYNC_CHECKPOINTER:
            logger.warning(
                "AsyncPostgresSaver 不可用，将使用无状态模式。"
                "如需状态持久化，请安装: pip install langgraph-checkpoint-postgres psycopg[pool]"
            )
            return False

        try:
            await self.db_manager.setup_checkpointer_tables()
            async with self.db_manager.get_checkpointer() as cp:
                pass
            logger.info("Checkpointer 可用")
            return True
        except Exception as e:
            logger.warning(f"Checkpointer 不可用，将使用无状态模式: {e}")
            return False

    async def cleanup(self):
        """
        清理容器资源

        在应用关闭时调用
        """
        from .logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("正在清理依赖容器...")

        self._db_manager = None
        self._llm_client = None
        self._embedding_client = None
        self._rerank_client = None
        self._event_manager = None
        self._task_manager = None
        self._agent = None
        self._checkpointer_available = False
        self._initialized = False


# ============ 便捷函数 ============

def get_container() -> Container:
    """获取依赖容器实例"""
    return Container.get_instance()
