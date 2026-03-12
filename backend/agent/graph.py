"""
农药智能体 LangGraph 工作流
实现配方专用的 Agent 架构

重构后专注于配方领域：
- generation: 配方生成
- optimization: 配方优化

模块结构：
- agent/workflow/state.py: 状态定义
- agent/workflow/log_entry.py: 日志条目创建
- agent/workflow/nodes.py: 节点实现
- agent/workflow/builder.py: 图构建
"""

from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langchain_core.messages import HumanMessage

from infra.llm import get_llm_client
from agent.workflow import AgentState, AgentLogEntry, create_log_entry, AgentNodes, GraphBuilder


# 导出供外部使用
__all__ = [
    "AgentState",
    "AgentLogEntry",
    "create_log_entry",
    "PesticideAgent",
    "get_pesticide_agent",
]


class PesticideAgent:
    """
    农药智能体 - 配方专用版

    封装节点实现和图构建，提供统一的接口
    """

    def __init__(self):
        # 初始化 LLM
        self.llm_client = get_llm_client()

        # 创建节点实例（重构后仅需 llm_client）
        self._nodes = AgentNodes(llm_client=self.llm_client)

        # 创建图构建器（由前端显式选择模式）
        self._builder = GraphBuilder(self._nodes)

    def get_compiled_graph(
        self,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        async_mode: bool = False
    ):
        """
        获取编译后的图

        Args:
            checkpointer: 状态持久化器
            async_mode: 是否使用异步节点

        Returns:
            编译后的图
        """
        return self._builder.get_compiled_graph(
            checkpointer=checkpointer,
            async_mode=async_mode
        )

    def build_graph(
        self,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        async_mode: bool = False
    ):
        """
        构建 LangGraph 工作流

        注意：此方法保留用于向后兼容，推荐使用 get_compiled_graph()

        Args:
            checkpointer: 状态持久化器
            async_mode: 是否使用异步节点

        Returns:
            编译后的图
        """
        return self.get_compiled_graph(checkpointer=checkpointer, async_mode=async_mode)


def get_pesticide_agent() -> PesticideAgent:
    """获取农药智能体实例"""
    return PesticideAgent()


if __name__ == "__main__":
    agent = get_pesticide_agent()
    graph = agent.get_compiled_graph()

    test_query = "帮我设计一个吡唑醚菌酯 25% SC 配方"

    initial_state = {
        "messages": [HumanMessage(content=test_query)],
        "intent": "",
        "entities": {},
        "steps": [],
        "kb_ids": None,
        "session_id": None,
        "route_mode": "generation",
        "enable_web_search": False,
        "original_recipe": None,
        "optimization_targets": [],
    }

    print(f"测试问题: {test_query}")
    print("-" * 50)

    result = graph.invoke(initial_state)

    print("\n执行步骤:")
    for step in result.get("steps", []):
        step_type = step.get("type", "unknown")
        content = step.get("content", "")
        icons = {
            "router": "🔀",
            "thought": "💭",
            "tool_req": "🛠️",
            "tool_res": "📄",
            "decision": "⚖️",
            "answer": "✅",
            "error": "❌",
        }
        icon = icons.get(step_type, "•")
        print(f"  {icon} [{step_type}] {content}")

    print("\n最终回答:")
    if result["messages"]:
        print(result["messages"][-1].content)
