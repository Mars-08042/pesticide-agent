"""
统一配置模块（基础设施）
集中管理所有配置项，支持环境变量覆盖

解决问题：P2-9 配置散落各处
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from enum import Enum
from dotenv import load_dotenv

load_dotenv()


class Environment(Enum):
    """运行环境"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


def get_environment() -> Environment:
    """获取当前运行环境"""
    env_str = os.getenv("ENV", "development").lower()
    try:
        return Environment(env_str)
    except ValueError:
        return Environment.DEVELOPMENT


@dataclass
class ServerConfig:
    """服务器配置"""
    host: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    reload: bool = field(default_factory=lambda: get_environment() == Environment.DEVELOPMENT)

    # CORS 配置
    cors_origins: List[str] = field(default_factory=lambda: _get_cors_origins())
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = field(default_factory=lambda: ["*"])
    cors_allow_headers: List[str] = field(default_factory=lambda: ["*"])


def _get_cors_origins() -> List[str]:
    """根据环境获取 CORS 允许的源"""
    env = get_environment()

    # 从环境变量读取自定义配置
    custom_origins = os.getenv("CORS_ORIGINS", "")
    if custom_origins:
        return [origin.strip() for origin in custom_origins.split(",")]

    # 根据环境返回默认配置
    if env == Environment.PRODUCTION:
        # 生产环境应明确指定允许的源
        return [
            "http://localhost:3000",
            "http://localhost:5173",
        ]
    else:
        # 开发环境允许所有源
        return ["*"]


def _get_bool_env(name: str, default: str = "false") -> bool:
    """读取布尔环境变量"""
    value = os.getenv(name, default).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _get_csv_env(name: str) -> List[str]:
    """读取逗号分隔的环境变量"""
    raw_value = os.getenv(name, "")
    if not raw_value.strip():
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


@dataclass
class DatabaseConfig:
    """数据库配置"""
    host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "postgres"))
    password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", ""))
    database: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "pesticide_db"))

    # 连接池配置
    pool_min_connections: int = field(
        default_factory=lambda: int(os.getenv("DB_POOL_MIN", "2"))
    )
    pool_max_connections: int = field(
        default_factory=lambda: int(os.getenv("DB_POOL_MAX", "10"))
    )

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class TaskManagerConfig:
    """任务管理器配置"""
    # 任务状态后端：memory (默认) 或 redis
    backend: str = field(
        default_factory=lambda: os.getenv("TASK_MANAGER_BACKEND", "memory")
    )

    # Redis 配置（仅当 backend=redis 时使用）
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )

    # 任务过期时间（秒）
    task_expire_seconds: int = field(
        default_factory=lambda: int(os.getenv("TASK_EXPIRE_SECONDS", "3600"))
    )

    # 全局最大并发任务数
    max_concurrent_tasks: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONCURRENT_TASKS", "3"))
    )


@dataclass
class RAGChunkingConfig:
    """RAG 分块配置"""
    # 分块大小（词数）
    max_chunk_words: int = field(
        default_factory=lambda: int(os.getenv("RECIPE_KB_MAX_CHUNK_WORDS", "1000"))
    )
    min_chunk_words: int = field(
        default_factory=lambda: int(os.getenv("RECIPE_KB_MIN_CHUNK_WORDS", "100"))
    )
    # 按语义边界切分，无需重叠
    chunk_overlap: int = 0
    # 保留标题行
    keep_separator: bool = True


@dataclass
class RAGRetrievalConfig:
    """RAG 检索配置"""
    # 向量检索初筛数量
    vector_top_n: int = field(
        default_factory=lambda: int(os.getenv("VECTOR_SEARCH_TOP_N", "20"))
    )
    # 最终返回数量（Rerank 成功或降级时都使用）
    final_top_k: int = field(
        default_factory=lambda: int(os.getenv("RETRIEVAL_FINAL_TOP_K", "5"))
    )
    # 最低相似度阈值（宽松召回）
    similarity_threshold: float = field(
        default_factory=lambda: float(os.getenv("SIMILARITY_THRESHOLD", "0.3"))
    )


@dataclass
class MetadataExtractorConfig:
    """元数据提取器配置"""
    api_base: str = field(
        default_factory=lambda: os.getenv("RECIPE_KB_LLM_API_BASE", "https://api.openai.com/v1")
    )
    api_key: str = field(
        default_factory=lambda: os.getenv("RECIPE_KB_LLM_API_KEY", "")
    )
    model: str = field(
        default_factory=lambda: os.getenv("RECIPE_KB_LLM_MODEL_NAME", "gpt-4o-mini")
    )
    temperature: float = field(
        default_factory=lambda: float(os.getenv("RECIPE_KB_LLM_TEMPERATURE", "0.1"))
    )
    max_tokens: int = 4096
    timeout: int = 30

    # 批处理配置
    batch_size: int = 5
    retry_times: int = 3


@dataclass
class WebSearchConfig:
    """联网搜索配置"""
    provider: str = field(default_factory=lambda: os.getenv("WEB_SEARCH_PROVIDER", "serper").lower())
    max_results: int = field(default_factory=lambda: int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5")))
    require_fulltext: bool = field(default_factory=lambda: _get_bool_env("WEB_SEARCH_REQUIRE_FULLTEXT", "false"))
    include_domains: List[str] = field(default_factory=lambda: _get_csv_env("WEB_SEARCH_INCLUDE_DOMAINS"))
    priority_domains: List[str] = field(default_factory=lambda: _get_csv_env("WEB_SEARCH_PRIORITY_DOMAINS"))
    trusted_domains: List[str] = field(default_factory=lambda: _get_csv_env("WEB_SEARCH_TRUSTED_DOMAINS"))
    exclude_domains: List[str] = field(default_factory=lambda: _get_csv_env("WEB_SEARCH_EXCLUDE_DOMAINS"))
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))
    tavily_search_retries: int = field(default_factory=lambda: max(1, int(os.getenv("TAVILY_SEARCH_RETRIES", "3"))))
    tavily_search_depth: str = field(default_factory=lambda: os.getenv("TAVILY_SEARCH_DEPTH", "advanced"))


@dataclass
class WebScraperConfig:
    """网页正文抓取配置"""
    provider: str = field(default_factory=lambda: os.getenv("WEB_SCRAPER_PROVIDER", "jina").lower())
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))
    tavily_extract_depth: str = field(default_factory=lambda: os.getenv("TAVILY_EXTRACT_DEPTH", "advanced"))
    jina_api_key: str = field(default_factory=lambda: os.getenv("JINA_API_KEYS", ""))
    timeout: int = field(default_factory=lambda: int(os.getenv("VISIT_SERVER_TIMEOUT", "60")))
    max_content_length: int = field(default_factory=lambda: int(os.getenv("WEBCONTENT_MAXLENGTH", "100000")))


@dataclass
class RecipeKBConfig:
    """配方知识库配置"""
    # 知识库根目录
    knowledge_base_dir: str = field(
        default_factory=lambda: os.getenv(
            "RECIPE_KB_DIR",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_base")
        )
    )

    # 索引文件路径
    index_file_path: str = field(
        default_factory=lambda: os.getenv(
            "RECIPE_KB_INDEX_PATH",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "recipe_index.json")
        )
    )

    # RAG 分块配置
    chunking: RAGChunkingConfig = field(default_factory=RAGChunkingConfig)
    # RAG 检索配置
    retrieval: RAGRetrievalConfig = field(default_factory=RAGRetrievalConfig)
    # 元数据提取器配置
    metadata_extractor: MetadataExtractorConfig = field(default_factory=MetadataExtractorConfig)

    # 数据类型映射
    @staticmethod
    def get_data_type_mapping() -> Dict[str, str]:
        """获取目录名到数据类型的映射"""
        return {
            "01_农药通用知识": "general",
            "02_助剂信息": "adjuvant",
            "03_制剂配方": "recipe",
            "04_工艺操作": "process",
            "05_稳定性数据": "stability",
            "06_配方实验": "experiment",
        }

    @staticmethod
    def get_types_requiring_company() -> List[str]:
        """获取需要公司字段的数据类型"""
        return ["recipe", "process", "stability", "experiment"]


@dataclass
class AppConfig:
    """应用总配置"""
    environment: Environment = field(default_factory=get_environment)
    server: ServerConfig = field(default_factory=ServerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    task_manager: TaskManagerConfig = field(default_factory=TaskManagerConfig)
    web_search: WebSearchConfig = field(default_factory=WebSearchConfig)
    web_scraper: WebScraperConfig = field(default_factory=WebScraperConfig)
    recipe_kb: RecipeKBConfig = field(default_factory=RecipeKBConfig)

    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION


# 全局配置单例
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取应用配置（单例）"""
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def reset_config():
    """重置配置（主要用于测试）"""
    global _config
    _config = None
