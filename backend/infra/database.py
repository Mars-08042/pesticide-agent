"""
数据库模块 - PostgreSQL + pgvector 连接和操作
支持 LangGraph Checkpointer 进行状态持久化

重构版本 - 支持:
- sessions 表支持标题修改
- recipe_chunks 用于配方检索
"""

import os
import uuid
import time
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from contextlib import contextmanager, asynccontextmanager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import psycopg2
from psycopg2 import pool
from psycopg2.extras import execute_values, RealDictCursor, Json
from pgvector.psycopg2 import register_vector
import atexit

# 异步支持
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg_pool import AsyncConnectionPool
    HAS_ASYNC_CHECKPOINTER = True
except ImportError:
    HAS_ASYNC_CHECKPOINTER = False
    AsyncPostgresSaver = None
    AsyncConnectionPool = None


@dataclass
class DBConfig:
    """数据库配置"""
    host: str
    port: int
    user: str
    password: str
    database: str

    @classmethod
    def from_env(cls) -> "DBConfig":
        """从环境变量加载配置"""
        return cls(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            database=os.getenv("POSTGRES_DB", "pesticide_db"),
        )

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


# 全局连接池实例（单例模式）
_connection_pool: Optional[pool.ThreadedConnectionPool] = None
_pool_lock = None

try:
    import threading
    _pool_lock = threading.Lock()
except ImportError:
    pass


def _get_connection_pool(config: "DBConfig") -> pool.ThreadedConnectionPool:
    """获取或创建全局连接池（线程安全）"""
    global _connection_pool
    
    if _connection_pool is not None:
        return _connection_pool
    
    if _pool_lock:
        with _pool_lock:
            # 双重检查锁定
            if _connection_pool is not None:
                return _connection_pool
            
            logger.info("[连接池] 正在初始化数据库连接池...")
            _connection_pool = pool.ThreadedConnectionPool(
                minconn=2,  # 最小连接数
                maxconn=10,  # 最大连接数
                host=config.host,
                port=config.port,
                user=config.user,
                password=config.password,
                database=config.database,
            )
            logger.info("[连接池] 数据库连接池初始化完成")
            
            # 注册程序退出时关闭连接池
            atexit.register(_close_connection_pool)
            
            return _connection_pool
    else:
        # 无线程支持时的回退
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            database=config.database,
        )
        return _connection_pool


def _close_connection_pool():
    """关闭全局连接池"""
    global _connection_pool
    if _connection_pool is not None:
        logger.info("[连接池] 正在关闭数据库连接池...")
        _connection_pool.closeall()
        _connection_pool = None


class DatabaseManager:
    """
    数据库管理器 - 处理 PostgreSQL 连接和 pgvector 操作
    
    重构版本支持:
    - sessions 表支持标题
    - recipe_chunks 用于配方检索
    
    性能优化:
    - 使用 ThreadedConnectionPool 连接池
    - 避免每次请求创建新连接
    """

    def __init__(self, config: Optional[DBConfig] = None):
        self.config = config or DBConfig.from_env()
        self._pool = None

    def _get_pool(self) -> pool.ThreadedConnectionPool:
        """获取连接池实例"""
        if self._pool is None:
            self._pool = _get_connection_pool(self.config)
        return self._pool

    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器（从连接池获取）"""
        conn_pool = self._get_pool()
        conn = conn_pool.getconn()
        
        # 注册 pgvector 类型
        register_vector(conn)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            # 归还连接到池中，而不是关闭
            conn_pool.putconn(conn)

    @contextmanager
    def get_cursor(self, dict_cursor: bool = False):
        """获取游标的上下文管理器"""
        with self.get_connection() as conn:
            cursor_factory = RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()

    def init_database(self, recreate_tables: bool = False):
        """
        初始化数据库 - 创建必要的扩展和表

        Args:
            recreate_tables: 是否重建表（会删除现有数据）
        """
        with self.get_cursor() as cursor:
            # 启用扩展
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")  # 用于模糊搜索

            if recreate_tables:
                print("正在重建所有表...")
                cursor.execute("DROP TABLE IF EXISTS chat_history CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS sessions CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS recipe_chunks CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS pesticides CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS adjuvants CASCADE;")

            # 1. 会话表 (sessions) - 新增 title 字段
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(100) UNIQUE NOT NULL,
                    title VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB DEFAULT '{}'
                );
            """)

            # 2. 聊天历史表 (chat_history)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(100) REFERENCES sessions(session_id) ON DELETE CASCADE,
                    role VARCHAR(50) NOT NULL,
                    message_type VARCHAR(50) DEFAULT 'text',
                    content TEXT NOT NULL,
                    thinking TEXT,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 聊天历史索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS chat_history_session_idx
                ON chat_history(session_id);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS chat_history_type_idx
                ON chat_history(message_type);
            """)

            # 3. 原药信息表 (pesticides)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pesticides (
                    id SERIAL PRIMARY KEY,

                    -- 基本信息（结构化，用于查询筛选）
                    name_cn VARCHAR(100) NOT NULL,
                    name_en VARCHAR(200),
                    aliases TEXT,
                    chemical_class VARCHAR(100),
                    cas_number TEXT,
                    molecular_info TEXT,

                    -- 详细内容（直接存储原文段落）
                    physicochemical TEXT,
                    bioactivity TEXT,
                    toxicology TEXT,
                    resistance_risk TEXT,
                    first_aid TEXT,
                    safety_notes TEXT,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 原药表索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pesticides_name_cn
                ON pesticides(name_cn);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pesticides_cas
                ON pesticides(cas_number);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pesticides_class
                ON pesticides(chemical_class);
            """)
            # 中文名模糊搜索索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pesticides_name_gin
                ON pesticides USING gin(name_cn gin_trgm_ops);
            """)

            # 4. 助剂信息表 (adjuvants)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS adjuvants (
                    id SERIAL PRIMARY KEY,
                    formulation_type VARCHAR(20) NOT NULL,
                    product_name VARCHAR(200) NOT NULL,
                    function VARCHAR(100),
                    adjuvant_type VARCHAR(100),
                    appearance VARCHAR(200),
                    ph_range VARCHAR(50),
                    remarks TEXT,
                    company VARCHAR(100),

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 助剂表索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_adjuvants_formulation
                ON adjuvants(formulation_type);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_adjuvants_function
                ON adjuvants(function);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_adjuvants_company
                ON adjuvants(company);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_adjuvants_product_gin
                ON adjuvants USING gin(product_name gin_trgm_ops);
            """)

            # 5. 配方分块表 (recipe_chunks) - RAG 向量存储
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recipe_chunks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    doc_id VARCHAR(100) NOT NULL,
                    chunk_index INTEGER NOT NULL,

                    -- 内容
                    content TEXT NOT NULL,
                    embedding vector(1024),

                    -- 通用元数据
                    doc_type VARCHAR(20),           -- recipe / experiment
                    title TEXT,
                    section TEXT,
                    formulation_type TEXT,          -- SC / EC / ME / WP / FS
                    active_ingredients TEXT[],      -- 数组存储
                    active_content TEXT,            -- 有效成分含量
                    source TEXT,
                    file_path TEXT,
                    summary TEXT,                   -- 配方/实验摘要

                    -- 制剂配方特定字段 (doc_type = 'recipe')
                    key_adjuvants TEXT[],           -- 关键助剂

                    -- 配方实验特定字段 (doc_type = 'experiment')
                    experiment_status VARCHAR(20),  -- success / failed / pending
                    issues_found TEXT[],            -- 发现的问题
                    optimization_notes TEXT,        -- 优化建议

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),

                    -- 唯一约束
                    UNIQUE(doc_id, chunk_index)
                );
            """)

            # 兼容历史版本：放宽可能超长的字段类型（重复执行安全）
            cursor.execute("""
                ALTER TABLE recipe_chunks
                    ALTER COLUMN title TYPE TEXT,
                    ALTER COLUMN section TYPE TEXT,
                    ALTER COLUMN formulation_type TYPE TEXT,
                    ALTER COLUMN active_content TYPE TEXT,
                    ALTER COLUMN source TYPE TEXT,
                    ALTER COLUMN file_path TYPE TEXT;
            """)

            # recipe_chunks 向量索引（IVFFlat，适合中等规模数据）
            cursor.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_indexes
                        WHERE indexname = 'idx_recipe_chunks_embedding'
                    ) THEN
                        CREATE INDEX idx_recipe_chunks_embedding ON recipe_chunks
                        USING ivfflat (embedding vector_cosine_ops)
                        WITH (lists = 100);
                    END IF;
                END $$;
            """)

            # recipe_chunks 元数据索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rc_formulation_type ON recipe_chunks(formulation_type);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rc_doc_type ON recipe_chunks(doc_type);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rc_source ON recipe_chunks(source);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rc_experiment_status ON recipe_chunks(experiment_status);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rc_active_ingredients ON recipe_chunks USING GIN(active_ingredients);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rc_key_adjuvants ON recipe_chunks USING GIN(key_adjuvants);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rc_doc_id ON recipe_chunks(doc_id);
            """)

            print("数据库初始化完成！")

    # ============ 会话管理方法 ============

    def create_session(
        self,
        session_id: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建新会话

        Args:
            session_id: 会话 ID (可选，不提供则自动生成)
            title: 会话标题 (可选)
            metadata: 元数据

        Returns:
            会话信息字典
        """
        session_id = session_id or str(uuid.uuid4())

        with self.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(
                """
                INSERT INTO sessions (session_id, title, metadata)
                VALUES (%s, %s, %s)
                RETURNING id, session_id, title, created_at, updated_at, metadata
                """,
                (session_id, title, Json(metadata or {}))
            )
            return dict(cursor.fetchone())

    def get_or_create_session(
        self,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        获取或创建会话

        Args:
            session_id: 会话 ID
            metadata: 会话元数据

        Returns:
            会话信息字典
        """
        with self.get_cursor(dict_cursor=True) as cursor:
            # 尝试获取现有会话
            cursor.execute(
                "SELECT * FROM sessions WHERE session_id = %s",
                (session_id,)
            )
            session = cursor.fetchone()

            if session:
                # 更新 updated_at
                cursor.execute(
                    "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = %s",
                    (session_id,)
                )
                return dict(session)

            # 创建新会话
            cursor.execute(
                """
                INSERT INTO sessions (session_id, metadata)
                VALUES (%s, %s)
                RETURNING id, session_id, title, created_at, updated_at, metadata
                """,
                (session_id, Json(metadata or {}))
            )
            new_session = cursor.fetchone()
            return dict(new_session)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        with self.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(
                "SELECT * FROM sessions WHERE session_id = %s",
                (session_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None

    def update_session(
        self,
        session_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        更新会话信息

        Args:
            session_id: 会话 ID
            title: 新标题 (可选)
            metadata: 新元数据 (可选)

        Returns:
            是否更新成功
        """
        with self.get_cursor() as cursor:
            updates = ["updated_at = CURRENT_TIMESTAMP"]
            params = []

            if title is not None:
                updates.append("title = %s")
                params.append(title)
            if metadata is not None:
                updates.append("metadata = %s")
                params.append(Json(metadata))

            params.append(session_id)

            cursor.execute(
                f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = %s",
                tuple(params)
            )
            return cursor.rowcount > 0

    def list_sessions(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        获取会话列表

        Args:
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            会话列表
        """
        with self.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(
                """
                SELECT
                    s.id,
                    s.session_id,
                    s.title,
                    s.created_at,
                    s.updated_at,
                    s.metadata,
                    (SELECT content FROM chat_history
                     WHERE session_id = s.session_id AND role = 'user'
                     ORDER BY created_at ASC LIMIT 1) as first_message
                FROM sessions s
                ORDER BY s.updated_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset)
            )
            sessions = cursor.fetchall()

            # 处理标题：如果没有标题，使用第一条消息
            result = []
            for session in sessions:
                session_dict = dict(session)
                if not session_dict.get("title"):
                    first_msg = session_dict.get("first_message", "")
                    session_dict["title"] = (
                        first_msg[:30] + "..." if first_msg and len(first_msg) > 30
                        else (first_msg or "新对话")
                    )
                result.append(session_dict)

            return result

    def search_sessions(
        self,
        keyword: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        按会话标题或内容模糊搜索

        Args:
            keyword: 搜索关键字
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            会话列表
        """
        with self.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(
                """
                SELECT
                    s.id,
                    s.session_id,
                    s.title,
                    s.created_at,
                    s.updated_at,
                    s.metadata,
                    (SELECT content FROM chat_history
                     WHERE session_id = s.session_id AND role = 'user'
                     ORDER BY created_at ASC LIMIT 1) as first_message
                FROM sessions s
                WHERE s.title ILIKE %s
                   OR EXISTS (
                       SELECT 1 FROM chat_history ch
                       WHERE ch.session_id = s.session_id
                       AND ch.role = 'user'
                       AND ch.content ILIKE %s
                       LIMIT 1
                   )
                ORDER BY s.updated_at DESC
                LIMIT %s OFFSET %s
                """,
                (f"%{keyword}%", f"%{keyword}%", limit, offset)
            )
            sessions = cursor.fetchall()

            # 处理标题
            result = []
            for session in sessions:
                session_dict = dict(session)
                if not session_dict.get("title"):
                    first_msg = session_dict.get("first_message", "")
                    session_dict["title"] = (
                        first_msg[:30] + "..." if first_msg and len(first_msg) > 30
                        else (first_msg or "新对话")
                    )
                result.append(session_dict)

            return result

    def delete_session(self, session_id: str) -> bool:
        """
        删除会话及其所有聊天历史

        Args:
            session_id: 会话 ID

        Returns:
            是否删除成功
        """
        with self.get_cursor() as cursor:
            # 由于外键约束，删除会话会自动删除聊天历史
            cursor.execute(
                "DELETE FROM sessions WHERE session_id = %s RETURNING id",
                (session_id,)
            )
            deleted = cursor.fetchone()
            return deleted is not None

    # ============ 消息持久化方法 ============

    def save_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        thinking: Optional[str] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        保存聊天消息

        Args:
            session_id: 会话 ID
            role: 消息角色 (user/assistant/system)
            content: 消息内容
            message_type: 消息类型 (text/thought/tool_call/tool_result/answer/error)
            thinking: 模型思考过程
            steps: 结构化执行步骤
            metadata: 额外元数据

        Returns:
            消息 ID
        """
        # 确保会话存在
        self.get_or_create_session(session_id)

        # 合并 steps 到 metadata
        final_metadata = metadata or {}
        if steps:
            final_metadata["steps"] = steps

        with self.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_history (session_id, role, message_type, content, thinking, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (session_id, role, message_type, content, thinking, Json(final_metadata))
            )
            message_id = cursor.fetchone()[0]
            return message_id

    def get_chat_history(
        self,
        session_id: str,
        limit: int = 20,
        before_id: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        分页获取聊天历史（支持向上滚动加载）

        Args:
            session_id: 会话 ID
            limit: 返回数量限制
            before_id: 在此 ID 之前的消息（用于游标分页）

        Returns:
            (消息列表, 是否还有更多)
        """
        with self.get_cursor(dict_cursor=True) as cursor:
            # 构建查询
            if before_id:
                cursor.execute(
                    """
                    SELECT id, session_id, role, message_type, content, thinking, metadata, created_at
                    FROM chat_history
                    WHERE session_id = %s AND id < %s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (session_id, before_id, limit + 1)  # 多查一条判断是否还有更多
                )
            else:
                cursor.execute(
                    """
                    SELECT id, session_id, role, message_type, content, thinking, metadata, created_at
                    FROM chat_history
                    WHERE session_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (session_id, limit + 1)
                )

            rows = cursor.fetchall()

            # 判断是否还有更多
            has_more = len(rows) > limit
            if has_more:
                rows = rows[:limit]

            # 转换为字典列表，并反转顺序（从旧到新）
            messages = [dict(row) for row in reversed(rows)]

            return messages, has_more

    def clear_chat_history(self, session_id: str) -> int:
        """
        清空会话的聊天历史

        Args:
            session_id: 会话 ID

        Returns:
            删除的消息数量
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM chat_history WHERE session_id = %s",
                (session_id,)
            )
            return cursor.rowcount

    def delete_message(self, message_id: int) -> bool:
        """
        删除单条消息

        Args:
            message_id: 消息 ID

        Returns:
            是否删除成功
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM chat_history WHERE id = %s RETURNING id",
                (message_id,)
            )
            return cursor.fetchone() is not None

    # ============ LangGraph Checkpointer 方法 ============

    @asynccontextmanager
    async def get_checkpointer(self):
        """
        获取异步 Checkpointer 上下文管理器

        用于 LangGraph 状态持久化，支持会话恢复和重新生成

        Yields:
            AsyncPostgresSaver 实例

        Raises:
            ImportError: 如果 langgraph-checkpoint-postgres 未安装
        """
        if not HAS_ASYNC_CHECKPOINTER:
            raise ImportError(
                "AsyncPostgresSaver 不可用。请安装: pip install langgraph-checkpoint-postgres psycopg[pool]"
            )

        # 构建连接字符串 (使用 psycopg3 格式)
        conninfo = f"postgresql://{self.config.user}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"

        async with AsyncConnectionPool(conninfo=conninfo) as pool:
            checkpointer = AsyncPostgresSaver(pool)
            yield checkpointer

    async def setup_checkpointer_tables(self):
        """
        初始化 Checkpointer 所需的表

        使用 from_conn_string 工厂方法，它会自动处理 autocommit 设置。
        应在应用启动时调用一次。
        """
        if not HAS_ASYNC_CHECKPOINTER:
            raise ImportError(
                "AsyncPostgresSaver 不可用。请安装: pip install langgraph-checkpoint-postgres psycopg[pool]"
            )

        conninfo = f"postgresql://{self.config.user}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"

        # 使用 from_conn_string 工厂方法，它会自动处理 autocommit 和 row_factory 设置
        async with AsyncPostgresSaver.from_conn_string(conninfo) as checkpointer:
            await checkpointer.setup()
            logger.info("Checkpointer 表初始化完成")

    def get_sync_connection_string(self) -> str:
        """获取同步连接字符串"""
        return self.config.connection_string

    def get_async_connection_string(self) -> str:
        """获取异步连接字符串 (psycopg3 格式)"""
        return f"postgresql://{self.config.user}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}"

    # ============ 原药信息管理方法 ============

    def create_pesticide(
        self,
        name_cn: str,
        name_en: Optional[str] = None,
        aliases: Optional[str] = None,
        chemical_class: Optional[str] = None,
        cas_number: Optional[str] = None,
        molecular_info: Optional[str] = None,
        physicochemical: Optional[str] = None,
        bioactivity: Optional[str] = None,
        toxicology: Optional[str] = None,
        resistance_risk: Optional[str] = None,
        first_aid: Optional[str] = None,
        safety_notes: Optional[str] = None
    ) -> int:
        """
        创建原药信息记录

        Returns:
            原药 ID
        """
        with self.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(
                """
                INSERT INTO pesticides
                    (name_cn, name_en, aliases, chemical_class, cas_number,
                     molecular_info, physicochemical,
                     bioactivity, toxicology, resistance_risk, first_aid, safety_notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (name_cn, name_en, aliases, chemical_class, cas_number,
                 molecular_info, physicochemical,
                 bioactivity, toxicology, resistance_risk, first_aid, safety_notes)
            )
            return cursor.fetchone()["id"]

    def get_pesticide(self, pesticide_id: int) -> Optional[Dict[str, Any]]:
        """获取单个原药信息"""
        with self.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(
                "SELECT * FROM pesticides WHERE id = %s",
                (pesticide_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None

    def get_pesticide_by_name(self, name_cn: str) -> Optional[Dict[str, Any]]:
        """按中文名获取原药信息"""
        with self.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(
                "SELECT * FROM pesticides WHERE name_cn = %s",
                (name_cn,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None

    def search_pesticides(
        self,
        keyword: Optional[str] = None,
        chemical_class: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        搜索原药信息

        Args:
            keyword: 关键词（匹配中文名、英文名、别名）
            chemical_class: 化学分类筛选
            page: 页码
            page_size: 每页数量

        Returns:
            (原药列表, 总数)
        """
        conditions = []
        params = []

        if keyword:
            conditions.append("(name_cn ILIKE %s OR name_en ILIKE %s OR aliases ILIKE %s)")
            params.extend([f"%{keyword}%"] * 3)
        if chemical_class:
            conditions.append("chemical_class = %s")
            params.append(chemical_class)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        offset = (page - 1) * page_size

        with self.get_cursor(dict_cursor=True) as cursor:
            # 总数
            cursor.execute(
                f"SELECT COUNT(*) as total FROM pesticides WHERE {where_clause}",
                tuple(params)
            )
            total = cursor.fetchone()["total"]

            # 数据
            cursor.execute(
                f"""
                SELECT id, name_cn, name_en, aliases, chemical_class, cas_number,
                       molecular_info, created_at
                FROM pesticides
                WHERE {where_clause}
                ORDER BY name_cn
                LIMIT %s OFFSET %s
                """,
                tuple(params) + (page_size, offset)
            )
            items = [dict(row) for row in cursor.fetchall()]

            return items, total

    def list_pesticide_classes(self) -> List[str]:
        """获取所有化学分类列表"""
        with self.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(
                """
                SELECT DISTINCT chemical_class
                FROM pesticides
                WHERE chemical_class IS NOT NULL
                ORDER BY chemical_class
                """
            )
            return [row["chemical_class"] for row in cursor.fetchall()]

    def delete_pesticide(self, pesticide_id: int) -> bool:
        """删除原药信息"""
        with self.get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM pesticides WHERE id = %s RETURNING id",
                (pesticide_id,)
            )
            return cursor.fetchone() is not None

    def clear_pesticides(self):
        """清空原药表"""
        with self.get_cursor() as cursor:
            cursor.execute("TRUNCATE TABLE pesticides RESTART IDENTITY")
            logger.info("已清空原药信息表")

    # ============ 助剂信息管理方法 ============

    def create_adjuvant(
        self,
        formulation_type: str,
        product_name: str,
        function: Optional[str] = None,
        adjuvant_type: Optional[str] = None,
        appearance: Optional[str] = None,
        ph_range: Optional[str] = None,
        remarks: Optional[str] = None,
        company: Optional[str] = None
    ) -> int:
        """
        创建助剂信息记录

        Returns:
            助剂 ID
        """
        with self.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(
                """
                INSERT INTO adjuvants
                    (formulation_type, product_name, function, adjuvant_type,
                     appearance, ph_range, remarks, company)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (formulation_type, product_name, function, adjuvant_type,
                 appearance, ph_range, remarks, company)
            )
            return cursor.fetchone()["id"]

    def get_adjuvant(self, adjuvant_id: int) -> Optional[Dict[str, Any]]:
        """获取单个助剂信息"""
        with self.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(
                "SELECT * FROM adjuvants WHERE id = %s",
                (adjuvant_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None

    def search_adjuvants(
        self,
        keyword: Optional[str] = None,
        formulation_type: Optional[str] = None,
        function: Optional[str] = None,
        company: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        搜索助剂信息

        Args:
            keyword: 关键词（匹配商品名）
            formulation_type: 剂型筛选
            function: 功能筛选
            company: 公司筛选
            page: 页码
            page_size: 每页数量

        Returns:
            (助剂列表, 总数)
        """
        conditions = []
        params = []

        if keyword:
            conditions.append("product_name ILIKE %s")
            params.append(f"%{keyword}%")
        if formulation_type:
            conditions.append("formulation_type = %s")
            params.append(formulation_type)
        if function:
            conditions.append("function = %s")
            params.append(function)
        if company:
            conditions.append("company = %s")
            params.append(company)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        offset = (page - 1) * page_size

        with self.get_cursor(dict_cursor=True) as cursor:
            # 总数
            cursor.execute(
                f"SELECT COUNT(*) as total FROM adjuvants WHERE {where_clause}",
                tuple(params)
            )
            total = cursor.fetchone()["total"]

            # 数据
            cursor.execute(
                f"""
                SELECT *
                FROM adjuvants
                WHERE {where_clause}
                ORDER BY formulation_type, product_name
                LIMIT %s OFFSET %s
                """,
                tuple(params) + (page_size, offset)
            )
            items = [dict(row) for row in cursor.fetchall()]

            return items, total

    def list_adjuvant_formulation_types(self) -> List[str]:
        """获取所有剂型列表"""
        with self.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(
                """
                SELECT DISTINCT formulation_type
                FROM adjuvants
                ORDER BY formulation_type
                """
            )
            return [row["formulation_type"] for row in cursor.fetchall()]

    def list_adjuvant_functions(self) -> List[str]:
        """获取所有功能列表"""
        with self.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(
                """
                SELECT DISTINCT function
                FROM adjuvants
                WHERE function IS NOT NULL
                ORDER BY function
                """
            )
            return [row["function"] for row in cursor.fetchall()]

    def list_adjuvant_companies(self) -> List[str]:
        """获取所有助剂公司列表"""
        with self.get_cursor(dict_cursor=True) as cursor:
            cursor.execute(
                """
                SELECT DISTINCT company
                FROM adjuvants
                WHERE company IS NOT NULL AND company != ''
                ORDER BY company
                """
            )
            return [row["company"] for row in cursor.fetchall()]

    def delete_adjuvant(self, adjuvant_id: int) -> bool:
        """删除助剂信息"""
        with self.get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM adjuvants WHERE id = %s RETURNING id",
                (adjuvant_id,)
            )
            return cursor.fetchone() is not None

    def clear_adjuvants(self):
        """清空助剂表"""
        with self.get_cursor() as cursor:
            cursor.execute("TRUNCATE TABLE adjuvants RESTART IDENTITY")
            logger.info("已清空助剂信息表")


def get_db_manager(**kwargs) -> DatabaseManager:
    """获取数据库管理器实例"""
    return DatabaseManager(**kwargs)


if __name__ == "__main__":
    # 测试数据库连接和初始化
    print("测试数据库连接...")
    db = get_db_manager()
    print(f"连接配置: {db.config.host}:{db.config.port}/{db.config.database}")

    try:
        db.init_database()
        with db.get_cursor(dict_cursor=True) as cursor:
            tables = [
                ("pesticides", "原药信息"),
                ("adjuvants", "助剂信息"),
                ("recipe_chunks", "配方分块"),
                ("sessions", "会话"),
                ("chat_history", "聊天记录"),
            ]
            for table_name, label in tables:
                cursor.execute(f"SELECT COUNT(*) AS count FROM {table_name};")
                count = cursor.fetchone()["count"]
                print(f"{label}({table_name}): {count} 条")
    except Exception as e:
        print(f"数据库连接失败: {e}")
        print("请确保 PostgreSQL 已启动，并已创建数据库和启用 pgvector 扩展")
