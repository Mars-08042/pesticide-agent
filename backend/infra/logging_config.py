"""
统一日志配置模块
集中管理所有日志设置

解决问题：P2-10 日志配置混乱
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import get_config, Environment


# 日志格式
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FORMAT_DETAILED = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = PROJECT_ROOT / "logs"


class DailyFileHandler(logging.Handler):
    """按日期将日志写入项目根目录 logs/YYYYMMDD.log。"""

    def __init__(self, logs_dir: Path, encoding: str = "utf-8"):
        super().__init__()
        self.logs_dir = logs_dir
        self.encoding = encoding
        self._current_date = ""
        self._file_handler: Optional[logging.FileHandler] = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            handler = self._ensure_file_handler()
            handler.emit(record)
        except Exception:
            self.handleError(record)

    def setFormatter(self, fmt: logging.Formatter) -> None:
        super().setFormatter(fmt)
        if self._file_handler is not None:
            self._file_handler.setFormatter(fmt)

    def setLevel(self, level: int) -> None:
        super().setLevel(level)
        if self._file_handler is not None:
            self._file_handler.setLevel(level)

    def close(self) -> None:
        try:
            if self._file_handler is not None:
                self._file_handler.close()
        finally:
            self._file_handler = None
            super().close()

    def _ensure_file_handler(self) -> logging.FileHandler:
        current_date = datetime.now().strftime("%Y%m%d")
        if self._file_handler is not None and self._current_date == current_date:
            return self._file_handler

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        if self._file_handler is not None:
            self._file_handler.close()

        file_handler = logging.FileHandler(
            self.logs_dir / f"{current_date}.log",
            encoding=self.encoding,
        )
        file_handler.setLevel(self.level)
        if self.formatter is not None:
            file_handler.setFormatter(self.formatter)

        self._file_handler = file_handler
        self._current_date = current_date
        return file_handler


def setup_logging(
    level: Optional[int] = None,
    detailed: bool = False
) -> None:
    """
    统一配置日志

    Args:
        level: 日志级别，默认根据环境自动选择
        detailed: 是否使用详细格式（包含文件名和行号）
    """
    config = get_config()

    # 根据环境确定日志级别
    if level is None:
        if config.is_production():
            level = logging.WARNING
        else:
            level = logging.INFO

    # 选择格式
    log_format = LOG_FORMAT_DETAILED if detailed else LOG_FORMAT

    # 配置根日志器
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            DailyFileHandler(LOGS_DIR),
        ],
        force=True  # 强制重新配置，覆盖第三方库的设置
    )

    # 配置应用日志器
    _configure_app_loggers(level)

    # 配置第三方库日志器（减少噪音）
    _configure_third_party_loggers()


def _configure_app_loggers(level: int) -> None:
    """配置应用相关的日志器"""
    app_loggers = [
        "api",
        "core",
        "infra",
        "agent",
        "tools",
        "uvicorn.access",
    ]

    for logger_name in app_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.disabled = False
        logger.propagate = True


def _configure_third_party_loggers() -> None:
    """配置第三方库日志器，减少不必要的输出"""
    # 无论什么环境都压制这些库的噪音日志
    noisy_loggers = [
        "httpx",
        "httpcore",
        "openai",
        "langchain",
        "langgraph",
        "psycopg2",
        "psycopg",
        "sentence_transformers",
        "transformers",
        "torch",
        "urllib3",
        "asyncio",
        "FlagEmbedding",
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # uvicorn access log 保留 INFO
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志器

    Args:
        name: 日志器名称，建议使用 __name__

    Returns:
        配置好的日志器
    """
    return logging.getLogger(name)


def restore_logging() -> None:
    """
    恢复日志设置

    某些第三方库可能会修改日志配置，调用此函数可恢复
    """
    logging.disable(logging.NOTSET)

    app_loggers = ["api", "core", "infra", "agent", "tools", "uvicorn.access"]
    for logger_name in app_loggers:
        logger = logging.getLogger(logger_name)
        logger.disabled = False


# 便捷的预配置日志器
api_logger = logging.getLogger("api")
core_logger = logging.getLogger("core")
infra_logger = logging.getLogger("infra")
agent_logger = logging.getLogger("agent")
tools_logger = logging.getLogger("tools")
