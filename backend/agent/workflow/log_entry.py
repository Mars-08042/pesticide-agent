"""
日志条目和步骤创建

提供结构化日志条目的创建函数
"""

from datetime import datetime
from typing import Optional, Dict, Any, Literal

from .state import AgentLogEntry


def create_log_entry(
    log_type: Literal["router", "thought", "tool_req", "tool_res", "decision", "answer", "error"],
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> AgentLogEntry:
    """
    创建一个结构化日志条目

    Args:
        log_type: 日志类型
        content: 日志内容
        metadata: 元数据（可选）

    Returns:
        结构化日志条目
    """
    return AgentLogEntry(
        type=log_type,
        content=content,
        metadata=metadata or {},
        created_at=datetime.now().isoformat()
    )
