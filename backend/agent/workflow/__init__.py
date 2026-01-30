"""
Agent 工作流核心（workflow）

说明：
- 目标是让目录命名更贴近职责：workflow = 状态/节点/图构建/日志结构等。
- `agent/core` 作为兼容层保留（历史导入路径），内部会转发到 `agent/workflow`。
"""

from .builder import GraphBuilder
from .log_entry import create_log_entry
from .nodes import AgentNodes
from .state import AgentState, AgentLogEntry, OptimizationTarget

__all__ = [
    "AgentState",
    "AgentLogEntry",
    "OptimizationTarget",
    "create_log_entry",
    "AgentNodes",
    "GraphBuilder",
]
