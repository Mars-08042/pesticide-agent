"""
Agent 状态定义

包含 Agent 执行过程中的状态结构和日志条目类型

重构后专注于配方领域：
- generation: 配方生成
- optimization: 配方优化
"""

from typing import Annotated, List, Dict, Any, Optional, Literal, TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentLogEntry(TypedDict):
    """Agent 执行过程中的结构化日志条目"""
    type: Literal["router", "thought", "tool_req", "tool_res", "decision", "answer", "error"]
    content: str
    metadata: Dict[str, Any]
    created_at: str


# 优化目标类型
OptimizationTarget = Literal["cost", "performance", "stability", "substitution"]


class AgentState(TypedDict):
    """Agent 状态 - 配方专用版"""
    # 消息历史
    messages: Annotated[List[BaseMessage], add_messages]

    # 意图识别结果 (generation/optimization)
    intent: str

    # 提取的实体
    entities: Dict[str, str]

    # 执行步骤（用于前端展示）
    steps: List[AgentLogEntry]

    # 知识库文档 ID 列表
    kb_ids: Optional[List[str]]

    # 会话 ID（用于子图实时推送步骤事件）
    session_id: Optional[str]

    # 路由模式：auto=自动判断，generation=配方生成，optimization=配方优化
    route_mode: Literal["auto", "generation", "optimization"]

    # 原始配方文本（优化模式必填）
    original_recipe: Optional[str]

    # 优化目标列表
    optimization_targets: List[OptimizationTarget]
